"""Tests for retry_on_status behaviour in _crawl_page_with_retry."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tagscope.auditor import SiteAuditor, RetriableStatusError
from tests.conftest import make_config


def _auditor(retry_on_status=None, max_retries=2, retry_delay=0.0):
    config = make_config()
    config['retry']['max_retries'] = max_retries
    config['retry']['retry_delay'] = retry_delay
    if retry_on_status is not None:
        config['retry']['retry_on_status'] = retry_on_status
    return SiteAuditor(config)


def _mock_browser():
    return MagicMock()


class TestRetriableStatusError:
    def test_attributes(self):
        err = RetriableStatusError(503, 'https://example.com/')
        assert err.status == 503
        assert err.url == 'https://example.com/'
        assert '503' in str(err)

    def test_is_exception(self):
        assert isinstance(RetriableStatusError(429, 'https://example.com/'), Exception)


class TestRetryOnStatus:
    @pytest.mark.asyncio
    async def test_retries_on_503_then_succeeds(self):
        """Page returns 503 twice then succeeds — should be crawled, not a broken link."""
        auditor = _auditor(retry_on_status=[503], max_retries=2)
        browser = _mock_browser()
        page_data = {'url': 'https://example.com/', 'status': 200}

        call_count = 0

        async def fake_crawl_page(browser, url, depth):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetriableStatusError(503, url)
            return page_data

        with patch.object(auditor, '_crawl_page', side_effect=fake_crawl_page):
            result = await auditor._crawl_page_with_retry(browser, 'https://example.com/', 0)

        assert result == page_data
        assert call_count == 3
        assert auditor.stats['pages_crawled'] == 1
        assert auditor.broken_links == []

    @pytest.mark.asyncio
    async def test_retries_on_429_exhausted_becomes_broken_link(self):
        """Page always returns 429 — after retries exhausted, added to broken_links."""
        auditor = _auditor(retry_on_status=[429], max_retries=2)
        browser = _mock_browser()

        async def fake_crawl_page(browser, url, depth):
            raise RetriableStatusError(429, url)

        with patch.object(auditor, '_crawl_page', side_effect=fake_crawl_page):
            result = await auditor._crawl_page_with_retry(browser, 'https://example.com/', 1)

        assert result is None
        assert auditor.stats['pages_failed'] == 1
        assert len(auditor.broken_links) == 1
        assert auditor.broken_links[0]['status'] == 429
        assert auditor.broken_links[0]['url'] == 'https://example.com/'
        assert auditor.broken_links[0]['depth'] == 1

    @pytest.mark.asyncio
    async def test_non_retriable_status_goes_straight_to_broken_links(self):
        """404 is not in retry_on_status — no retries, straight to broken_links."""
        auditor = _auditor(retry_on_status=[500, 503], max_retries=2)
        browser = _mock_browser()

        call_count = 0

        async def fake_crawl_page(browser, url, depth):
            nonlocal call_count
            call_count += 1
            return None  # _crawl_page returns None for non-retriable 4xx

        with patch.object(auditor, '_crawl_page', side_effect=fake_crawl_page):
            result = await auditor._crawl_page_with_retry(browser, 'https://example.com/missing', 0)

        assert result is None
        assert call_count == 1  # no retries
        assert auditor.stats['pages_failed'] == 1

    @pytest.mark.asyncio
    async def test_broken_link_not_added_on_intermediate_retry(self):
        """A retried URL must not accumulate duplicate broken_link entries."""
        auditor = _auditor(retry_on_status=[503], max_retries=3)
        browser = _mock_browser()

        async def fake_crawl_page(browser, url, depth):
            raise RetriableStatusError(503, url)

        with patch.object(auditor, '_crawl_page', side_effect=fake_crawl_page):
            await auditor._crawl_page_with_retry(browser, 'https://example.com/', 0)

        assert len(auditor.broken_links) == 1  # exactly one, not one per attempt

    @pytest.mark.asyncio
    async def test_default_config_includes_retriable_statuses(self):
        """Smoke test: default retry_on_status covers 429 and 5xx."""
        config = make_config()
        retriable = config['retry']['retry_on_status']
        assert 429 in retriable
        assert 500 in retriable
        assert 503 in retriable
