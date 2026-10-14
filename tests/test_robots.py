"""Tests for respect_robots / robots.txt enforcement."""

import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
from urllib.error import URLError
from urllib.robotparser import RobotFileParser
from tagscope.auditor import SiteAuditor
from conftest import make_config


def _auditor(respect_robots=True, start_url='https://example.com'):
    config = make_config()
    config['start_url'] = start_url
    config['filters']['respect_robots'] = respect_robots
    return config


def _make_robots_response(content: str):
    """Fake urllib response returning robots.txt content."""
    encoded = content.encode('utf-8')
    mock_resp = MagicMock()
    mock_resp.read.return_value = encoded
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


ROBOTS_BASIC = """\
User-agent: *
Disallow: /private/
Disallow: /admin/
Allow: /
"""

ROBOTS_ALLOW_ALL = """\
User-agent: *
Allow: /
"""

ROBOTS_BLOCK_ALL = """\
User-agent: *
Disallow: /
"""


class TestRobotsLoading:
    def test_robots_loaded_when_respect_true(self):
        with patch('tagscope.auditor.urlopen', return_value=_make_robots_response(ROBOTS_BASIC)):
            auditor = SiteAuditor(_auditor(respect_robots=True))
        assert auditor._robots is not None
        assert isinstance(auditor._robots, RobotFileParser)

    def test_robots_none_when_respect_false(self):
        config = _auditor(respect_robots=False)
        # urlopen should never be called
        with patch('tagscope.auditor.urlopen', side_effect=AssertionError("should not fetch")):
            auditor = SiteAuditor(config)
        assert auditor._robots is None

    def test_robots_none_on_url_error(self):
        with patch('tagscope.auditor.urlopen', side_effect=URLError("connection refused")):
            auditor = SiteAuditor(_auditor(respect_robots=True))
        assert auditor._robots is None

    def test_robots_none_on_404(self):
        with patch('tagscope.auditor.urlopen', side_effect=URLError("HTTP Error 404")):
            auditor = SiteAuditor(_auditor(respect_robots=True))
        assert auditor._robots is None

    def test_robots_none_on_parse_error(self):
        with patch('tagscope.auditor.urlopen', return_value=_make_robots_response('\x00\xff\xfe')):
            with patch.object(RobotFileParser, 'parse', side_effect=Exception("bad parse")):
                auditor = SiteAuditor(_auditor(respect_robots=True))
        assert auditor._robots is None

    def test_robots_fetched_from_correct_url(self):
        fetched_urls = []

        def fake_urlopen(url, timeout=None):
            fetched_urls.append(url)
            return _make_robots_response(ROBOTS_ALLOW_ALL)

        with patch('tagscope.auditor.urlopen', side_effect=fake_urlopen):
            SiteAuditor(_auditor(start_url='https://example.com/some/path'))

        assert fetched_urls == ['https://example.com/robots.txt']


class TestShouldCrawlWithRobots:
    def _auditor_with_robots(self, robots_content, respect=True):
        with patch('tagscope.auditor.urlopen', return_value=_make_robots_response(robots_content)):
            return SiteAuditor(_auditor(respect_robots=respect))

    def test_disallowed_path_blocked(self):
        auditor = self._auditor_with_robots(ROBOTS_BASIC)
        assert auditor.should_crawl('https://example.com/private/data') is False

    def test_disallowed_admin_blocked(self):
        auditor = self._auditor_with_robots(ROBOTS_BASIC)
        assert auditor.should_crawl('https://example.com/admin/') is False

    def test_allowed_path_passes(self):
        auditor = self._auditor_with_robots(ROBOTS_BASIC)
        assert auditor.should_crawl('https://example.com/about') is True

    def test_block_all_blocks_every_path(self):
        auditor = self._auditor_with_robots(ROBOTS_BLOCK_ALL)
        assert auditor.should_crawl('https://example.com/') is False
        assert auditor.should_crawl('https://example.com/about') is False

    def test_allow_all_passes_every_path(self):
        auditor = self._auditor_with_robots(ROBOTS_ALLOW_ALL)
        assert auditor.should_crawl('https://example.com/anything') is True

    def test_respect_false_ignores_disallow(self):
        """With respect_robots=False, disallowed paths are still crawled."""
        config = _auditor(respect_robots=False)
        with patch('tagscope.auditor.urlopen', side_effect=AssertionError("should not fetch")):
            auditor = SiteAuditor(config)
        # Private path would be blocked if robots were respected
        assert auditor.should_crawl('https://example.com/private/data') is True

    def test_fetch_failure_allows_all(self):
        """If robots.txt can't be fetched, no URLs are blocked."""
        with patch('tagscope.auditor.urlopen', side_effect=URLError("timeout")):
            auditor = SiteAuditor(_auditor(respect_robots=True))
        assert auditor.should_crawl('https://example.com/private/anything') is True

    def test_existing_filters_still_apply_with_robots(self):
        """robots.txt enforcement does not bypass exclude_patterns."""
        config = _auditor(respect_robots=True)
        config['filters']['exclude_patterns'] = [r'/excluded/']
        with patch('tagscope.auditor.urlopen', return_value=_make_robots_response(ROBOTS_ALLOW_ALL)):
            auditor = SiteAuditor(config)
        assert auditor.should_crawl('https://example.com/excluded/page') is False
