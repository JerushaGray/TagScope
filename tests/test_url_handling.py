"""Tests for URL normalization and crawl filtering."""

import pytest


class TestNormalizeUrl:
    def test_strips_fragment(self, auditor):
        assert auditor.normalize_url('https://example.com/page#section') == 'https://example.com/page'

    def test_strips_trailing_slash(self, auditor):
        assert auditor.normalize_url('https://example.com/page/') == 'https://example.com/page'

    def test_preserves_root_slash(self, auditor):
        assert auditor.normalize_url('https://example.com/') == 'https://example.com/'

    def test_preserves_query(self, auditor):
        assert auditor.normalize_url('https://example.com/search?q=test') == 'https://example.com/search?q=test'

    def test_basic_url(self, auditor):
        assert auditor.normalize_url('https://example.com/about') == 'https://example.com/about'


class TestShouldCrawl:
    def test_same_domain_allowed(self, auditor):
        assert auditor.should_crawl('https://example.com/page') is True

    def test_different_domain_rejected(self, auditor):
        assert auditor.should_crawl('https://other.com/page') is False

    def test_skip_pdf(self, auditor):
        assert auditor.should_crawl('https://example.com/doc.pdf') is False

    def test_skip_jpg(self, auditor):
        assert auditor.should_crawl('https://example.com/photo.jpg') is False

    def test_skip_zip(self, auditor):
        assert auditor.should_crawl('https://example.com/archive.zip') is False

    def test_allow_html_page(self, auditor):
        assert auditor.should_crawl('https://example.com/page.html') is True

    def test_exclude_pattern(self, auditor):
        auditor.config['filters']['exclude_patterns'] = [r'/admin.*']
        assert auditor.should_crawl('https://example.com/admin/dashboard') is False
        assert auditor.should_crawl('https://example.com/about') is True

    def test_include_pattern(self, auditor):
        auditor.config['filters']['include_patterns'] = [r'/blog/.*']
        assert auditor.should_crawl('https://example.com/blog/post-1') is True
        assert auditor.should_crawl('https://example.com/about') is False

    def test_no_include_means_all(self, auditor):
        auditor.config['filters']['include_patterns'] = []
        assert auditor.should_crawl('https://example.com/anything') is True

    def test_case_insensitive_extension(self, auditor):
        assert auditor.should_crawl('https://example.com/image.PNG') is False
        assert auditor.should_crawl('https://example.com/image.Jpg') is False


class TestAuditorInit:
    def test_max_pages_floor(self, default_config):
        from tagscope.auditor import SiteAuditor
        default_config['crawl']['max_pages'] = -5
        a = SiteAuditor(default_config)
        assert a.max_pages == 1

    def test_max_depth_floor(self, default_config):
        from tagscope.auditor import SiteAuditor
        default_config['crawl']['max_depth'] = -1
        a = SiteAuditor(default_config)
        assert a.max_depth == 0

    def test_rate_limit_floor(self, default_config):
        from tagscope.auditor import SiteAuditor
        default_config['crawl']['rate_limit'] = 0.01
        a = SiteAuditor(default_config)
        assert a.rate_limit == 0.1

    def test_concurrent_capped_at_10(self, default_config):
        from tagscope.auditor import SiteAuditor
        default_config['crawl']['concurrent_pages'] = 50
        a = SiteAuditor(default_config)
        assert a.concurrent_pages == 10

    def test_invalid_concurrent_defaults_to_3(self, default_config):
        from tagscope.auditor import SiteAuditor
        default_config['crawl']['concurrent_pages'] = 'bad'
        a = SiteAuditor(default_config)
        assert a.concurrent_pages == 3

    def test_timeout_converted_to_ms(self, default_config):
        from tagscope.auditor import SiteAuditor
        default_config['crawl']['timeout'] = 45
        a = SiteAuditor(default_config)
        assert a.timeout == 45000

    def test_base_domain_extracted(self, auditor):
        assert auditor.base_domain == 'example.com'
