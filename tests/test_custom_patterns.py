"""Tests for custom tag patterns merged from config."""

import pytest
from tagscope.auditor import SiteAuditor
from tagscope.patterns import TAG_PATTERNS
from tests.conftest import make_config


def _auditor_with_custom(custom_patterns):
    config = make_config()
    config['tags']['custom_patterns'] = custom_patterns
    return SiteAuditor(config)


class TestCustomPatternsLoaded:
    def test_custom_pattern_added_to_tag_patterns(self):
        auditor = _auditor_with_custom({
            'my_vendor': {'patterns': [r'myvendor\.init\('], 'category': 'Analytics'}
        })
        assert 'my_vendor' in auditor._tag_patterns

    def test_builtin_patterns_preserved(self):
        auditor = _auditor_with_custom({
            'my_vendor': {'patterns': [r'myvendor\.init\('], 'category': 'Analytics'}
        })
        for builtin in TAG_PATTERNS:
            assert builtin in auditor._tag_patterns

    def test_no_custom_patterns_uses_builtins_only(self):
        auditor = _auditor_with_custom({})
        assert auditor._tag_patterns == TAG_PATTERNS

    def test_custom_does_not_mutate_module_level_tag_patterns(self):
        _auditor_with_custom({
            'my_vendor': {'patterns': [r'myvendor\.init\('], 'category': 'Analytics'}
        })
        assert 'my_vendor' not in TAG_PATTERNS

    def test_custom_pattern_can_override_builtin(self):
        """A custom entry with the same key as a builtin overwrites it."""
        auditor = _auditor_with_custom({
            'google_tag_manager': {'patterns': [r'CUSTOM-GTM'], 'category': 'Tag Management'}
        })
        assert auditor._tag_patterns['google_tag_manager']['patterns'] == [r'CUSTOM-GTM']

    def test_custom_pattern_optional_fields_preserved(self):
        auditor = _auditor_with_custom({
            'my_vendor': {
                'patterns': [r'myvendor\.js'],
                'urls': ['cdn.myvendor.com/tag.js'],
                'category': 'Advertising',
            }
        })
        entry = auditor._tag_patterns['my_vendor']
        assert entry['urls'] == ['cdn.myvendor.com/tag.js']


class TestCustomPatternValidation:
    def test_missing_patterns_skipped(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            auditor = _auditor_with_custom({
                'bad_entry': {'category': 'Analytics'}  # no 'patterns'
            })
        assert 'bad_entry' not in auditor._tag_patterns
        assert 'bad_entry' in caplog.text

    def test_missing_category_skipped(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            auditor = _auditor_with_custom({
                'bad_entry': {'patterns': [r'foo']}  # no 'category'
            })
        assert 'bad_entry' not in auditor._tag_patterns
        assert 'bad_entry' in caplog.text

    def test_patterns_not_a_list_skipped(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            auditor = _auditor_with_custom({
                'bad_entry': {'patterns': r'foo', 'category': 'Analytics'}  # string not list
            })
        assert 'bad_entry' not in auditor._tag_patterns


class TestCustomPatternDetection:
    def test_custom_pattern_detected_in_html(self):
        auditor = _auditor_with_custom({
            'my_vendor': {'patterns': [r'myvendor\.init\('], 'category': 'Analytics'}
        })
        html = '<script>myvendor.init("acct-123")</script>'
        result = auditor.detect_tags(html, 'https://example.com/')
        assert 'my_vendor' in result
        assert result['my_vendor']['found'] is True
        assert result['my_vendor']['category'] == 'Analytics'

    def test_custom_pattern_not_detected_when_absent(self):
        auditor = _auditor_with_custom({
            'my_vendor': {'patterns': [r'myvendor\.init\('], 'category': 'Analytics'}
        })
        html = '<script>otherlib.init()</script>'
        result = auditor.detect_tags(html, 'https://example.com/')
        assert 'my_vendor' not in result

    def test_custom_url_detected_via_network(self):
        auditor = _auditor_with_custom({
            'my_vendor': {
                'patterns': [],
                'urls': ['cdn.myvendor.com/tag.js'],
                'category': 'Advertising',
            }
        })
        network = [{'url': 'https://cdn.myvendor.com/tag.js', 'method': 'GET', 'type': 'script', 'post_data': None}]
        result = auditor.detect_tags('', 'https://example.com/', network_requests=network)
        assert 'my_vendor' in result
        assert result['my_vendor']['confidence'] == 'high'
