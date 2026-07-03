"""MCP server exposing ChoopScoop site-auditing tools over stdio transport.

Install with the optional extra: ``pip install choopscoop[mcp]``

Run: ``choopscoop-mcp`` (console script) or ``python -m choopscoop.mcp_server``
"""

import asyncio
import json
import logging
import sys
import tempfile
import uuid
from contextlib import asynccontextmanager
from typing import Dict, List

try:
    from mcp.server.fastmcp import FastMCP
    _MISSING_MCP = False
except ImportError:
    _MISSING_MCP = True

from choopscoop.auditor import (
    SiteAuditor,
    audit_page,
    format_page_llm,
    format_site_llm,
    _extract_host,
)
from choopscoop.patterns import TAG_PATTERNS, TECHNOLOGY_PATTERNS

logging.basicConfig(level=logging.WARNING)

# ---------------------------------------------------------------------------
# Persistent browser (lazy init, shared across tool calls)
# ---------------------------------------------------------------------------

_pw_context = None
_browser = None


async def _get_browser():
    """Return a shared Chromium instance, launching on first call."""
    global _pw_context, _browser
    if _browser is None:
        from playwright.async_api import async_playwright
        _pw_context = await async_playwright().start()
        _browser = await _pw_context.chromium.launch(headless=True)
    return _browser


async def _shutdown_browser():
    """Tear down the shared browser if it was started."""
    global _pw_context, _browser
    if _browser:
        await _browser.close()
        _browser = None
    if _pw_context:
        await _pw_context.stop()
        _pw_context = None


@asynccontextmanager
async def _lifespan(server):
    """Manage browser lifecycle: clean up on server shutdown."""
    try:
        yield
    finally:
        await _shutdown_browser()


# ---------------------------------------------------------------------------
# Background site-audit management
# ---------------------------------------------------------------------------

_audits: Dict[str, Dict] = {}

_MAX_RETAINED_AUDITS = 10


def _make_audit_id() -> str:
    return uuid.uuid4().hex[:12]


def _evict_oldest_audits():
    """Remove the oldest completed/errored audits if we exceed the cap."""
    finished = [
        (aid, entry) for aid, entry in _audits.items()
        if entry['status'] in ('complete', 'error')
    ]
    while len(_audits) > _MAX_RETAINED_AUDITS and finished:
        oldest_id, _ = finished.pop(0)
        del _audits[oldest_id]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_known_hosts() -> tuple:
    """Pre-compute known hosts and owned domains from all patterns."""
    known = set()
    owned = set()
    for patterns in (TAG_PATTERNS, TECHNOLOGY_PATTERNS):
        for cfg in patterns.values():
            for frag in cfg.get('urls', []):
                h = _extract_host(frag)
                if h:
                    known.add(h)
            for d in cfg.get('owned_domains', []):
                owned.add(d)
    return known, owned


# ---------------------------------------------------------------------------
# Tool functions (defined unconditionally so they are always importable)
# ---------------------------------------------------------------------------

async def audit_page_tool(url: str) -> str:
    """Audit a single web page and return detected tags, technologies, GA4 events, and performance metrics.

    Returns a compact JSON object with tag IDs, technology stack, GA4
    measurement IDs and event counts, and core web vitals. Typically
    completes in under 15 seconds.

    Args:
        url: Full URL of the page to audit (e.g. https://example.com/pricing).
    """
    browser = await _get_browser()
    result = await audit_page(url, browser=browser)
    if result is None:
        return json.dumps({"error": f"Could not load {url} (navigation failure or HTTP error)"})
    return json.dumps(format_page_llm(result), default=str)


async def start_site_audit(
    url: str,
    max_pages: int = 50,
    max_depth: int = 3,
) -> str:
    """Start a background crawl of an entire site.

    The crawl runs asynchronously. Use get_audit_status to check progress
    and get_audit_results to retrieve the final report once complete.

    Args:
        url: Start URL for the crawl (e.g. https://example.com).
        max_pages: Maximum number of pages to crawl (default 50, max 500).
        max_depth: Maximum link-hop depth from the start URL (default 3).
    """
    max_pages = max(1, min(int(max_pages), 500))
    max_depth = max(0, min(int(max_depth), 10))

    audit_id = _make_audit_id()

    from choopscoop.cli import _default_config
    config = _default_config()
    config['start_url'] = url
    config['crawl']['max_pages'] = max_pages
    config['crawl']['max_depth'] = max_depth
    config['resume']['enabled'] = False
    config['output']['save_progress'] = False
    config['output']['prefix'] = str(
        tempfile.mkdtemp(prefix='choopscoop-') + '/audit'
    )
    config['logging']['console'] = False
    config['logging']['log_file'] = None

    auditor = SiteAuditor(config)

    _audits[audit_id] = {
        'status': 'running',
        'url': url,
        'max_pages': max_pages,
        'auditor': auditor,
        'task': None,
        'error': None,
    }

    async def _run():
        try:
            await auditor.crawl()
            _audits[audit_id]['status'] = 'complete'
        except Exception as e:
            _audits[audit_id]['status'] = 'error'
            _audits[audit_id]['error'] = str(e)

    _audits[audit_id]['task'] = asyncio.create_task(_run())
    _evict_oldest_audits()

    return json.dumps({
        'audit_id': audit_id,
        'url': url,
        'max_pages': max_pages,
        'max_depth': max_depth,
        'status': 'running',
    })


async def get_audit_status(audit_id: str) -> str:
    """Check the progress of a running site audit.

    Args:
        audit_id: The ID returned by start_site_audit.
    """
    entry = _audits.get(audit_id)
    if not entry:
        return json.dumps({"error": f"Unknown audit_id: {audit_id}"})

    auditor = entry['auditor']
    return json.dumps({
        'audit_id': audit_id,
        'url': entry['url'],
        'status': entry['status'],
        'pages_crawled': auditor.stats['pages_crawled'],
        'pages_failed': auditor.stats['pages_failed'],
        'pages_queued': len(auditor.to_visit),
        'max_pages': entry['max_pages'],
        'error': entry['error'],
    })


async def get_audit_results(audit_id: str) -> str:
    """Retrieve the results of a completed site audit in LLM-optimized format.

    Returns an error if the audit is still running. Use get_audit_status
    to check progress first.

    Args:
        audit_id: The ID returned by start_site_audit.
    """
    entry = _audits.get(audit_id)
    if not entry:
        return json.dumps({"error": f"Unknown audit_id: {audit_id}"})

    if entry['status'] == 'running':
        return json.dumps({"error": "Audit still running. Use get_audit_status to check progress."})

    if entry['status'] == 'error':
        return json.dumps({"error": f"Audit failed: {entry['error']}"})

    auditor = entry['auditor']
    _, unidentified_hosts = auditor._classify_network_requests()

    output = format_site_llm(
        auditor.page_data,
        broken_links=auditor.broken_links,
        unidentified_hosts=unidentified_hosts,
    )
    return json.dumps(output, default=str)


async def list_patterns() -> str:
    """List all marketing tags and web technologies that ChoopScoop can detect.

    Returns tag names grouped by category (Tag Management, Analytics,
    Advertising, etc.) and technology names grouped by category (CMS,
    JavaScript Framework, CDN, etc.).
    """
    tag_cats: Dict[str, list] = {}
    for name, cfg in sorted(TAG_PATTERNS.items()):
        cat = cfg.get('category', 'Other')
        tag_cats.setdefault(cat, []).append(name)

    tech_cats: Dict[str, list] = {}
    for name, cfg in sorted(TECHNOLOGY_PATTERNS.items()):
        cat = cfg.get('category', 'Other')
        tech_cats.setdefault(cat, []).append(name)

    return json.dumps({
        'tags': tag_cats,
        'tag_count': len(TAG_PATTERNS),
        'technologies': tech_cats,
        'technology_count': len(TECHNOLOGY_PATTERNS),
    })


async def identify_unknowns(hosts: List[str]) -> str:
    """Classify a list of third-party hostnames as known or unknown.

    Checks each hostname against ChoopScoop's tag and technology pattern
    databases. Returns which hosts are recognized (and which vendor they
    belong to) and which are unidentified.

    Args:
        hosts: List of hostnames to check (e.g. ["px.ads.linkedin.com", "mystery.example.com"]).
    """
    known_hosts, owned_domains = _build_known_hosts()

    recognized = []
    unknown = []

    for host in hosts:
        host = host.strip()
        if not host:
            continue

        matched_vendor = None

        # Check URL-fragment match
        if any(kh in host for kh in known_hosts):
            for name, cfg in {**TAG_PATTERNS, **TECHNOLOGY_PATTERNS}.items():
                for frag in cfg.get('urls', []):
                    h = _extract_host(frag)
                    if h and h in host:
                        matched_vendor = name
                        break
                if matched_vendor:
                    break

        # Check owned-domain match
        if not matched_vendor:
            for name, cfg in {**TAG_PATTERNS, **TECHNOLOGY_PATTERNS}.items():
                for d in cfg.get('owned_domains', []):
                    if host == d or host.endswith('.' + d):
                        matched_vendor = name
                        break
                if matched_vendor:
                    break

        if matched_vendor:
            recognized.append({'host': host, 'vendor': matched_vendor})
        else:
            unknown.append(host)

    return json.dumps({
        'recognized': recognized,
        'unknown': unknown,
        'recognized_count': len(recognized),
        'unknown_count': len(unknown),
    })


# ---------------------------------------------------------------------------
# MCP tool registration (only when the SDK is available)
# ---------------------------------------------------------------------------

if not _MISSING_MCP:
    mcp = FastMCP(
        "choopscoop",
        instructions=(
            "ChoopScoop is a Playwright-powered site auditor that detects marketing "
            "tags, analytics implementations, and web technologies. All detection is "
            "deterministic (no LLM in the detection loop). Use audit_page for fast "
            "single-page checks and start_site_audit/get_audit_status/get_audit_results "
            "for full-site crawls."
        ),
        lifespan=_lifespan,
    )

    mcp.tool()(audit_page_tool)
    mcp.tool()(start_site_audit)
    mcp.tool()(get_audit_status)
    mcp.tool()(get_audit_results)
    mcp.tool()(list_patterns)
    mcp.tool()(identify_unknowns)
else:
    mcp = None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _require_mcp():
    if _MISSING_MCP:
        print(
            "The MCP server requires the 'mcp' package.\n"
            "Install it with: pip install choopscoop[mcp]",
            file=sys.stderr,
        )
        sys.exit(1)


def main():
    """Run the ChoopScoop MCP server over stdio."""
    _require_mcp()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
