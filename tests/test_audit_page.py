"""Tests for single-page audit API (audit_page / _single_page_config)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from tagscope.auditor import audit_page, _single_page_config


# ---------------------------------------------------------------------------
# _single_page_config
# ---------------------------------------------------------------------------

class TestSinglePageConfig:
    def test_defaults(self):
        cfg = _single_page_config('https://example.com')
        assert cfg['start_url'] == 'https://example.com'
        assert cfg['crawl']['max_pages'] == 1
        assert cfg['crawl']['max_depth'] == 0
        assert cfg['crawl']['rate_limit'] == 0.0
        assert cfg['crawl']['concurrent_pages'] == 1
        assert cfg['resume']['enabled'] is False
        assert cfg['output']['save_progress'] is False
        assert cfg['logging']['console'] is False
        assert cfg['logging']['log_file'] is None

    def test_overrides_merge(self):
        cfg = _single_page_config('https://example.com', {
            'browser': {'headless': False},
            'performance': {'capture_screenshots': True},
        })
        assert cfg['browser']['headless'] is False
        assert cfg['performance']['capture_screenshots'] is True
        # other defaults still intact
        assert cfg['crawl']['max_pages'] == 1

    def test_datalayer_enabled_by_default(self):
        cfg = _single_page_config('https://example.com')
        assert cfg['datalayer']['extract'] is True

    def test_performance_metrics_enabled_by_default(self):
        cfg = _single_page_config('https://example.com')
        assert cfg['performance']['capture_metrics'] is True


# ---------------------------------------------------------------------------
# audit_page
# ---------------------------------------------------------------------------

def _make_mock_page(*, status=200, html='<html><head><title>Test</title></head><body></body></html>'):
    """Build a mock Playwright Page with the minimum surface for _crawl_page."""
    page = AsyncMock()

    # page.goto() returns a response
    response = AsyncMock()
    response.status = status
    response.headers = {'content-type': 'text/html'}
    page.goto.return_value = response

    # page.wait_for_load_state -- just resolve
    page.wait_for_load_state.return_value = None

    # page.content() returns HTML
    page.content.return_value = html

    # page.evaluate() -- return sensible defaults for metadata extraction
    async def evaluate_side_effect(script):
        if 'document.title' in script:
            return {
                'title': 'Test Page',
                'description': '',
                'keywords': '',
                'canonical': '',
                'og_title': '',
                'og_description': '',
                'og_image': '',
                'h1': [],
                'h2': [],
                'robots': '',
                'viewport': '',
                'charset': 'utf-8',
                'lang': 'en',
                'meta_tags': [],
            }
        if 'dataLayer' in script:
            return None
        if 'performance' in script.lower() or 'PerformanceNavigationTiming' in script:
            return {
                'load_time': 150.0,
                'dom_content_loaded': 80.0,
                'first_paint': 50.0,
                'first_contentful_paint': 60.0,
                'transfer_size': 1024,
                'dom_interactive': 70.0,
            }
        return None

    page.evaluate.side_effect = evaluate_side_effect

    # page.evaluate_handle() + json_value() for script elements
    handle = AsyncMock()
    handle.json_value.return_value = []
    page.evaluate_handle.return_value = handle

    # page.query_selector_all for link extraction
    page.query_selector_all.return_value = []

    # page.on -- capture the request handler but do nothing
    page.on = MagicMock()

    # page.close
    page.close.return_value = None

    return page


def _make_mock_browser(page=None):
    """Build a mock Playwright Browser that yields the given page."""
    browser = AsyncMock()
    browser.new_page.return_value = page or _make_mock_page()
    return browser


class TestAuditPage:
    """Unit tests for audit_page using mocked Playwright objects."""

    def test_returns_page_dict(self):
        page = _make_mock_page()
        browser = _make_mock_browser(page)

        result = asyncio.run(
            audit_page('https://example.com', browser=browser)
        )

        assert result is not None
        assert result['url'] == 'https://example.com'
        assert result['status'] == 200
        assert result['depth'] == 0
        assert 'metadata' in result
        assert 'tags' in result
        assert 'technologies' in result
        assert 'network_requests' in result
        assert 'crawled_at' in result

    def test_returns_none_on_404(self):
        page = _make_mock_page(status=404)
        browser = _make_mock_browser(page)

        result = asyncio.run(
            audit_page('https://example.com/missing', browser=browser)
        )

        assert result is None

    def test_caller_browser_not_closed(self):
        browser = _make_mock_browser()

        asyncio.run(
            audit_page('https://example.com', browser=browser)
        )

        browser.close.assert_not_called()

    def test_auto_browser_lifecycle(self):
        mock_page = _make_mock_page()
        mock_browser = _make_mock_browser(mock_page)
        mock_pw = AsyncMock()
        mock_pw.chromium.launch.return_value = mock_browser

        async def fake_start():
            return mock_pw

        with patch('tagscope.auditor.async_playwright') as mock_apw:
            mock_apw.return_value.start = fake_start

            asyncio.run(
                audit_page('https://example.com')
            )

            # browser launched and closed
            mock_pw.chromium.launch.assert_called_once()
            mock_browser.close.assert_called_once()
            # playwright context stopped
            mock_pw.stop.assert_called_once()

    def test_no_rate_limit_sleep(self):
        """Single-page mode should not sleep for rate limiting."""
        page = _make_mock_page()
        browser = _make_mock_browser(page)

        with patch('tagscope.auditor.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            asyncio.run(
                audit_page('https://example.com', browser=browser)
            )
            # sleep(0) is effectively a no-op yield; should not sleep > 0
            for call in mock_sleep.call_args_list:
                assert call.args[0] == 0, f"unexpected sleep({call.args[0]})"

    def test_config_overrides_applied(self):
        page = _make_mock_page()
        browser = _make_mock_browser(page)

        result = asyncio.run(
            audit_page(
                'https://example.com',
                browser=browser,
                config={'performance': {'capture_metrics': False}},
            )
        )

        assert result is not None
        # with capture_metrics=False, performance should be empty
        assert result['performance'] == {}

    def test_result_contains_expected_keys(self):
        page = _make_mock_page()
        browser = _make_mock_browser(page)

        result = asyncio.run(
            audit_page('https://example.com', browser=browser)
        )

        expected_keys = {
            'url', 'depth', 'status', 'metadata', 'tags',
            'datalayer', 'ga4_collect_events', 'technologies',
            'performance', 'network_requests', 'internal_links_found',
            'screenshot', 'crawled_at',
        }
        assert expected_keys == set(result.keys())
