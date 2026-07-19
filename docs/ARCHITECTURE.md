# Architecture and Design Decisions

## Overview

TagScope is a Playwright-powered site auditor that detects marketing tags, analytics
platforms, and web technologies across crawled pages. It runs headless Chromium to render
JavaScript-heavy sites, then applies regex and URL-signature matching against the rendered
DOM, network requests, meta tags, and response headers.

```
CLI (cli.py)
  |
  v
SiteAuditor (auditor.py)
  |-- Playwright browser (headless Chromium)
  |-- Network capture (all third-party requests, with POST data)
  |-- Detection engine
  |     |-- detect_tags: HTML patterns + URL signatures + network host matching
  |     |-- detect_technologies: HTML + meta + headers + network corroboration
  |     |-- _parse_datalayer: standard events + gtag() argument decoding
  |     `-- decode_ga4_collect_requests: /g/collect URL + POST body parsing
  |-- Pattern library (patterns.py)
  |     |-- TAG_PATTERNS (77 marketing/analytics tags, with evidence tracking)
  |     |-- TECHNOLOGY_PATTERNS (50+ platform fingerprints)
  |     `-- GA4_EVENTS (25 dataLayer event types)
  |-- Wappalyzer adapter (wappalyzer_adapter.py, optional --extended)
  |     |-- fetch_rulesets: download fingerprints to ~/.tagscope/rulesets/
  |     |-- load_and_convert: JSON -> TagScope schema conversion
  |     |-- merge_patterns: curated-wins merge with extended data
  |     `-- compile_patterns: one-time regex compilation at load
  |-- Link extraction and crawl queue
  `-- Export (JSON / CSV / HTML, matched + unidentified host split)
```

## Key Design Decisions

### Built-in detection over Wappalyzer

Early versions shelled out to `wappalyzer-next` (the npm CLI) as a subprocess for
technology detection. This was dropped in v3.0 for three reasons:

1. **Licensing conflict.** wappalyzer-next is GPL v3; TagScope is MIT. Distributing
   them together creates a license compatibility issue.
2. **Performance.** Spawning a Node subprocess per page added 2-4 seconds of overhead
   on top of the Playwright crawl. Built-in regex matching against already-fetched HTML
   is effectively free.
3. **Reliability.** The subprocess introduced a hard dependency on Node.js and npm, plus
   version-specific bugs. Removing it means the only runtime dependency is Python +
   Playwright.

The trade-off is maintaining patterns manually, but for the MarTech/analytics domain this
is manageable -- the tag ecosystem changes slowly and the patterns are straightforward
(CDN hostnames, SDK init calls, meta generator tags).

### domcontentloaded over networkidle

Playwright's `goto()` supports several wait strategies. The original code used
`networkidle` (wait until no network connections for 500ms), which sounds ideal for
capturing all tag-firing activity. In practice, modern sites with analytics pixels,
chat widgets, websockets, and ad exchanges never reach network idle -- the page times
out at 30 seconds.

The current approach:

1. Wait for `domcontentloaded` (fast, reliable -- the HTML is parsed and scripts are
   loaded).
2. Best-effort `networkidle` with a 5-second timeout. If it settles, great. If not,
   proceed with what we have.

This captures the vast majority of tags because marketing scripts typically fire within
1-2 seconds of DOM ready. The few that load later (lazy-loaded chat widgets, deferred
pixels) are still caught if they appear in the static HTML source.

### Three-layer detection: patterns + URL signatures + network requests

Each tag entry supports three detection methods:

- **Regex patterns** match against the full page HTML (e.g., `GTM-[A-Z0-9]{4,}` for
  Google Tag Manager container IDs).
- **URL signatures** match against the page source as substring checks (e.g.,
  `js.hs-scripts.com` for HubSpot).
- **Network request host matching** (added in v3.1) compares tag URL signatures against
  the parsed host of every captured third-party request using `urllib.parse`.

The network layer was added because some tags (LinkedIn Insight Tag, Google Ads/DoubleClick)
fire hundreds of network requests but have no inline HTML signature. Prior to v3.1, these
were invisible because detection only ran against the rendered DOM. Network requests are
now the primary evidence source for tags that operate via pixel/beacon requests.

The `log_request` handler captures all third-party requests (any host that differs from
the crawled page's domain), not a curated allowlist. This ensures unknown vendors are
never silently dropped. At export time, requests are split into matched (known pattern)
and unidentified third-party hosts with counts, keeping file size manageable while
surfacing unknown vendors for competitive recon.

### Technology detection via response headers and network corroboration

CMS and platform detection originally relied only on HTML patterns and meta tags. This
misses server-side technologies that leave no trace in the DOM. v3.0 added header-based
detection:

- `server: nginx` / `server: Apache` / `server: cloudflare`
- `x-powered-by: PHP` / `x-powered-by: ASP.NET`
- `x-vercel-id` / `x-nf-request-id` (Netlify)
- `via: CloudFront` / `x-amz-cf-id`

Headers are checked with the same regex engine as HTML patterns, using a separate
`headers` field in `TECHNOLOGY_PATTERNS` entries.

v3.1 added network request corroboration: technology patterns with a `urls` field are
also matched against captured third-party request hosts. This provides independent
confirmation and enables detection of technologies that load assets from known CDNs
(e.g., `cdn.shopify.com`) even when the HTML pattern does not match.

### False-positive hardening (v3.1)

Several technology patterns were tightened after field testing showed false positives:

- **Magento**: bare `Magento` (case-insensitive) matched any text mention. Replaced with
  specific patterns (`Magento_Ui`, `mage/cookies`, `/skin/frontend/.*Magento`).
- **WooCommerce**: bare `woocommerce` matched blog posts about WooCommerce. Replaced with
  `wc-cart-fragments`, `class="woocommerce`, `wp-content/plugins/woocommerce`.
- **Bootstrap/Tailwind**: CSS class-name patterns (`container`, `row`, `col-md`, `flex`,
  `text-sm`) matched nearly every site. Removed entirely, kept only versioned filename
  patterns. Tailwind carries a `detection_note` because purged/bundled builds are
  undetectable from filename alone -- this is a conscious false-negative trade-off.

### Crawl state and resume

Long crawls (100+ pages) can fail mid-run due to network issues, rate limiting, or
resource constraints. The `CrawlState` class persists visited URLs, the remaining queue,
and collected page data to a JSON file. On restart, the auditor picks up where it left
off instead of re-crawling.

State files are domain-specific (`output/crawl_state_example_com.json`) so multiple audits can
coexist. The `--no-resume` flag forces a fresh start.

### Evidence and confidence model (v3.1)

Every detection (tag or technology) now records what it matched on and a confidence level:

```python
{
    'found': True,
    'ids': ['GTM-ABC123'],
    'category': 'Tag Management',
    'evidence': ['html_pattern:GTM-[A-Z0-9]{4,}', 'request_host:www.googletagmanager.com'],
    'confidence': 'high'
}
```

Evidence types: `html_pattern`, `script_url`, `request_host`, `request_url`, `meta`,
`header`. Confidence is derived from evidence, not assigned separately:

- **high**: network request, response header, meta generator tag
- **medium**: specific JS API pattern or script src URL in HTML
- **low**: generic regex (reserved for future use; currently all shipped patterns are
  medium or higher after the false-positive hardening pass)

The model is for reporting -- it does not gate detections at runtime.

### GA4 event decoding (v3.1)

GA4 events reach the tool through two channels that are now both decoded:

1. **dataLayer parser** (`_parse_datalayer`): handles standard `dataLayer.push` events
   and gtag() argument objects. A `gtag('event','purchase',{value:99})` call serializes
   as `{"0":"event","1":"purchase","2":{"value":99}}` -- the parser detects numeric-key
   objects and routes `event` commands to the events list, while `config`/`consent`/`set`/
   `js`/`get` go to a separate `gtag_config` summary.

2. **Measurement Protocol decoder** (`decode_ga4_collect_requests`): parses
   `google-analytics.com/g/collect` request URLs and POST bodies. Extracts `en=` (event
   name), `tid=` (measurement ID), `ep.*`/`epn.*` (event/numeric params). Deduplicates
   retransmissions (`_s=1` vs `_s=2`) on a stable key before counting.

Both layers intentionally surface the same events. The dataLayer shows what the page
intends to send; collect requests show what GA4 actually received after consent filtering.
They are stored under separate keys (`datalayer` and `ga4_collect_events`) and are not
collapsed.

### Why not async HTTP (httpx/aiohttp) instead of Playwright?

Many tag detection tools use plain HTTP requests. TagScope uses a real browser because:

- **JavaScript rendering.** Most marketing tags are injected by JavaScript (GTM, HubSpot,
  Segment). A plain HTTP fetch sees none of them.
- **DataLayer access.** GA4 events are pushed to `window.dataLayer` at runtime. Extracting
  them requires JS execution.
- **Network request logging.** Playwright intercepts all outbound third-party requests,
  providing the primary evidence source for tag detection beyond pattern matching.

The cost is higher resource usage and slower crawl speed. For the typical use case
(auditing a single site, 50-500 pages), this is an acceptable trade-off.

### Extended detection via Wappalyzer adapter (v3.2)

The curated TECHNOLOGY_PATTERNS library covers ~50 technologies -- the ones most
relevant to MarTech auditing.  For broader coverage (~5000 technologies), TagScope
can optionally load fingerprints from the Wappalyzer open-source project.

**Why not bundle them?**  Wappalyzer fingerprint data is GPL-3.0; TagScope is MIT.
Bundling the data would create a license compatibility issue.  Instead, the user
downloads the data themselves (`--fetch-rulesets`) to a local cache
(`~/.tagscope/rulesets/`), and the adapter converts the format at runtime.  The
package never distributes GPL content.

**Format conversion.**  Wappalyzer entries use a different schema than TagScope:

| Wappalyzer field | TagScope equivalent |
|---|---|
| `scriptSrc` (list of regex) | `patterns` (list of regex) |
| `html` (body-level regex) | `patterns` (disabled by default -- too noisy) |
| `meta` (dict of `{name: pattern}`) | `meta` (list of `(name, pattern)` tuples) |
| `headers` (dict of `{name: pattern}`) | `headers` (list of `(name, pattern)` tuples) |
| `cats` (list of category IDs) | `category` (single string) |

Wappalyzer patterns carry suffixes like `\;version:\1` and `\;confidence:50` that
are stripped during conversion.  Invalid regexes are silently dropped.

**Curated-wins merge.**  When `--extended` is used, the 50 curated patterns are
merged with the converted Wappalyzer entries.  For any key that exists in both dicts,
the curated entry is kept.  This preserves the false-positive hardening work (Magento,
WooCommerce, Bootstrap, Tailwind) and evidence/confidence tuning from v3.1.

**One-time compilation.**  With ~5000 patterns, per-page `re.compile` would add
significant overhead.  All patterns (regex, meta, headers) are compiled to
`re.Pattern` objects once at load.  The detection engine transparently handles both
compiled and string patterns, so curated-only mode (default) is unaffected.

**Mirror resilience.**  The Wappalyzer repo has moved between GitHub organizations
multiple times.  `fetch_rulesets` probes three known mirrors in order and uses the
first one that responds.

## Project Layout

```
src/tagscope/
  __init__.py              # Package version
  __main__.py              # python -m tagscope entry point
  auditor.py               # SiteAuditor class, crawl logic, export
  cli.py                   # Argument parsing, config loading, dependency checks
  patterns.py              # TAG_PATTERNS, TECHNOLOGY_PATTERNS, GA4_EVENTS
  wappalyzer_adapter.py    # Wappalyzer fingerprint conversion and caching

tests/
  conftest.py              # Shared fixtures (config, auditor instance)
  test_tag_detection.py
  test_technology_detection.py
  test_datalayer.py
  test_url_handling.py
  test_config.py
  test_export.py
  test_patterns.py
  test_wappalyzer_adapter.py
```

Tests cover all non-Playwright logic (pattern matching, config loading, URL filtering,
data export). The browser-dependent crawl path is tested via live runs rather than mocked
browser sessions, keeping tests fast and deterministic.
