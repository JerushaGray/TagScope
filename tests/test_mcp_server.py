"""Tests for the MCP server tool functions.

Tests call the tool functions directly (not over stdio transport) to verify
argument handling, output shape, and error cases without needing Playwright.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

from tagscope.mcp_server import (
    audit_page_tool,
    get_audit_status,
    get_audit_results,
    identify_unknowns,
    list_patterns,
    start_site_audit,
    _audits,
    _build_known_hosts,
    _evict_oldest_audits,
    _MAX_RETAINED_AUDITS,
    _require_mcp,
)


# ---------------------------------------------------------------------------
# list_patterns (no mocking needed -- pure data)
# ---------------------------------------------------------------------------

class TestListPatterns:
    def test_returns_valid_json(self):
        result = json.loads(asyncio.run(list_patterns()))
        assert 'tags' in result
        assert 'technologies' in result

    def test_tag_count_matches(self):
        result = json.loads(asyncio.run(list_patterns()))
        total = sum(len(v) for v in result['tags'].values())
        assert total == result['tag_count']

    def test_technology_count_matches(self):
        result = json.loads(asyncio.run(list_patterns()))
        total = sum(len(v) for v in result['technologies'].values())
        assert total == result['technology_count']

    def test_known_tags_present(self):
        result = json.loads(asyncio.run(list_patterns()))
        all_tags = []
        for names in result['tags'].values():
            all_tags.extend(names)
        assert 'google_tag_manager' in all_tags
        assert 'google_analytics_4' in all_tags

    def test_known_technologies_present(self):
        result = json.loads(asyncio.run(list_patterns()))
        all_techs = []
        for names in result['technologies'].values():
            all_techs.extend(names)
        assert 'wordpress' in all_techs


# ---------------------------------------------------------------------------
# identify_unknowns (no mocking needed -- pure pattern matching)
# ---------------------------------------------------------------------------

class TestIdentifyUnknowns:
    def test_known_host_recognized(self):
        result = json.loads(asyncio.run(
            identify_unknowns(['www.googletagmanager.com'])
        ))
        assert result['recognized_count'] == 1
        assert result['unknown_count'] == 0
        assert result['recognized'][0]['host'] == 'www.googletagmanager.com'

    def test_unknown_host(self):
        result = json.loads(asyncio.run(
            identify_unknowns(['totally-unknown-vendor.example.com'])
        ))
        assert result['unknown_count'] == 1
        assert 'totally-unknown-vendor.example.com' in result['unknown']

    def test_mixed_hosts(self):
        result = json.loads(asyncio.run(
            identify_unknowns([
                'www.googletagmanager.com',
                'mystery.example.com',
                'px.ads.linkedin.com',
            ])
        ))
        assert result['recognized_count'] == 2
        assert result['unknown_count'] == 1

    def test_empty_list(self):
        result = json.loads(asyncio.run(identify_unknowns([])))
        assert result['recognized_count'] == 0
        assert result['unknown_count'] == 0

    def test_blank_hosts_skipped(self):
        result = json.loads(asyncio.run(identify_unknowns(['', '  '])))
        assert result['recognized_count'] == 0
        assert result['unknown_count'] == 0

    def test_owned_domain_match(self):
        """Hosts under a vendor's owned_domains should be recognized."""
        result = json.loads(asyncio.run(
            identify_unknowns(['subdomain.quantserve.com'])
        ))
        assert result['recognized_count'] == 1


# ---------------------------------------------------------------------------
# _build_known_hosts (helper)
# ---------------------------------------------------------------------------

class TestBuildKnownHosts:
    def test_returns_sets(self):
        known, owned = _build_known_hosts()
        assert isinstance(known, set)
        assert isinstance(owned, set)
        assert len(known) > 0
        assert len(owned) > 0


# ---------------------------------------------------------------------------
# audit_page_tool (mocked Playwright)
# ---------------------------------------------------------------------------

def _mock_audit_page_result():
    return {
        'url': 'https://example.com',
        'depth': 0,
        'status': 200,
        'metadata': {'title': 'Test', 'description': '', 'keywords': '',
                     'canonical': '', 'og_title': '', 'og_description': '',
                     'og_image': '', 'h1': [], 'h2': [], 'robots': '',
                     'viewport': '', 'charset': '', 'lang': '', 'meta_tags': []},
        'tags': {},
        'datalayer': {},
        'ga4_collect_events': {},
        'technologies': [],
        'performance': {},
        'network_requests': [],
        'internal_links_found': 0,
        'screenshot': None,
        'crawled_at': '2026-07-02T12:00:00',
    }


class TestAuditPageTool:
    def test_success_returns_llm_format(self):
        mock_browser = AsyncMock()
        with patch('tagscope.mcp_server._get_browser', return_value=mock_browser), \
             patch('tagscope.mcp_server.audit_page', return_value=_mock_audit_page_result()):
            result = json.loads(asyncio.run(audit_page_tool('https://example.com')))
        assert result['url'] == 'https://example.com'
        assert result['status'] == 200
        # Should be LLM-projected (no network_requests, depth, etc.)
        assert 'network_requests' not in result
        assert 'depth' not in result

    def test_navigation_failure_returns_error(self):
        mock_browser = AsyncMock()
        with patch('tagscope.mcp_server._get_browser', return_value=mock_browser), \
             patch('tagscope.mcp_server.audit_page', return_value=None):
            result = json.loads(asyncio.run(audit_page_tool('https://example.com/404')))
        assert 'error' in result


# ---------------------------------------------------------------------------
# start_site_audit / get_audit_status / get_audit_results
# ---------------------------------------------------------------------------

class TestSiteAuditLifecycle:
    def setup_method(self):
        _audits.clear()

    def test_start_returns_audit_id(self):
        with patch('tagscope.mcp_server.SiteAuditor') as MockAuditor:
            mock_instance = MockAuditor.return_value
            mock_instance.stats = {'pages_crawled': 0, 'pages_failed': 0}
            mock_instance.to_visit = []
            mock_instance.crawl = AsyncMock()
            result = json.loads(asyncio.run(start_site_audit('https://example.com', max_pages=10)))

        assert 'audit_id' in result
        assert result['url'] == 'https://example.com'
        assert result['max_pages'] == 10
        assert result['status'] == 'running'

    def test_max_pages_clamped(self):
        with patch('tagscope.mcp_server.SiteAuditor') as MockAuditor:
            mock_instance = MockAuditor.return_value
            mock_instance.stats = {'pages_crawled': 0, 'pages_failed': 0}
            mock_instance.to_visit = []
            mock_instance.crawl = AsyncMock()
            result = json.loads(asyncio.run(start_site_audit('https://example.com', max_pages=9999)))
        assert result['max_pages'] == 500

    def test_get_status_unknown_id(self):
        result = json.loads(asyncio.run(get_audit_status('nonexistent')))
        assert 'error' in result

    def test_get_results_unknown_id(self):
        result = json.loads(asyncio.run(get_audit_results('nonexistent')))
        assert 'error' in result

    def test_get_results_still_running(self):
        _audits['test123'] = {
            'status': 'running',
            'url': 'https://example.com',
            'max_pages': 10,
            'auditor': AsyncMock(),
            'task': None,
            'error': None,
        }
        result = json.loads(asyncio.run(get_audit_results('test123')))
        assert 'error' in result
        assert 'still running' in result['error']

    def test_get_results_error(self):
        _audits['test456'] = {
            'status': 'error',
            'url': 'https://example.com',
            'max_pages': 10,
            'auditor': AsyncMock(),
            'task': None,
            'error': 'Connection refused',
        }
        result = json.loads(asyncio.run(get_audit_results('test456')))
        assert 'error' in result
        assert 'Connection refused' in result['error']


# ---------------------------------------------------------------------------
# Audit eviction
# ---------------------------------------------------------------------------

class TestAuditEviction:
    def setup_method(self):
        _audits.clear()

    def test_evicts_oldest_completed(self):
        for i in range(_MAX_RETAINED_AUDITS + 5):
            _audits[f'audit-{i}'] = {
                'status': 'complete',
                'url': f'https://example.com/{i}',
                'max_pages': 10,
                'auditor': AsyncMock(),
                'task': None,
                'error': None,
            }
        _evict_oldest_audits()
        assert len(_audits) <= _MAX_RETAINED_AUDITS

    def test_does_not_evict_running(self):
        for i in range(_MAX_RETAINED_AUDITS + 3):
            _audits[f'audit-{i}'] = {
                'status': 'running',
                'url': f'https://example.com/{i}',
                'max_pages': 10,
                'auditor': AsyncMock(),
                'task': None,
                'error': None,
            }
        _evict_oldest_audits()
        # All running, nothing evicted
        assert len(_audits) == _MAX_RETAINED_AUDITS + 3
