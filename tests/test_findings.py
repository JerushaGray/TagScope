"""Tests for auto-generated findings in export_findings."""

import json
import os
import tempfile


def _make_page(url, tags=None, technologies=None, metadata=None,
               performance=None, datalayer=None, ga4_collect=None,
               internal_links=5, depth=1, status=200):
    return {
        'url': url, 'depth': depth, 'status': status,
        'metadata': metadata or {'title': 'Test Page', 'description': 'A test page', 'canonical': url},
        'tags': tags or {},
        'datalayer': datalayer or {'total_events': 0, 'ga4_events': {}, 'ecommerce_events': [], 'gtag_config': []},
        'ga4_collect_events': ga4_collect or {},
        'technologies': technologies or [],
        'performance': performance or {'load_time': 2000},
        'network_requests': [],
        'internal_links_found': internal_links,
        'screenshot': None,
        'crawled_at': '2025-01-01T00:00:00',
    }


def _tag(found=True, ids=None, category='Analytics', evidence=None, confidence='high'):
    return {
        'found': found,
        'ids': ids or [],
        'category': category,
        'evidence': evidence or [],
        'confidence': confidence,
    }


def _export_findings(auditor):
    # Populate stats from page_data so tag_index builds correctly
    from collections import defaultdict
    auditor.stats['tags_found'] = defaultdict(int)
    auditor.stats['technologies_found'] = defaultdict(int)
    for page in auditor.page_data:
        for tag_name, tag_data in page.get('tags', {}).items():
            if tag_data.get('found'):
                auditor.stats['tags_found'][tag_name] += 1
        for tech in page.get('technologies', []):
            auditor.stats['technologies_found'][tech.get('name', '')] += 1

    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        path = f.name
    auditor.export_findings(path)
    with open(path) as f:
        data = json.load(f)
    os.unlink(path)
    return data


def _finding_types(data):
    return [f['type'] for f in data['findings']]


class TestVendorRedundancy:
    def test_two_analytics_tools(self, auditor):
        tags = {
            'google_analytics_4': _tag(category='Analytics'),
            'mixpanel': _tag(category='Analytics'),
        }
        auditor.page_data = [_make_page('https://example.com', tags=tags)]
        data = _export_findings(auditor)
        types = _finding_types(data)
        assert 'vendor_redundancy' in types
        finding = next(f for f in data['findings'] if f['type'] == 'vendor_redundancy')
        assert 'analytics' in finding['detail'].lower()

    def test_two_heatmap_tools(self, auditor):
        tags = {
            'hotjar': _tag(category='Heatmaps'),
            'microsoft_clarity': _tag(category='Session Recording'),
        }
        auditor.page_data = [_make_page('https://example.com', tags=tags)]
        data = _export_findings(auditor)
        finding = next(f for f in data['findings'] if f['type'] == 'vendor_redundancy')
        assert 'heatmap' in finding['detail'].lower() or 'session recording' in finding['detail'].lower()

    def test_heatmap_and_session_recording_grouped(self, auditor):
        tags = {
            'hotjar': _tag(category='Heatmaps'),
            'fullstory': _tag(category='Session Recording'),
        }
        auditor.page_data = [_make_page('https://example.com', tags=tags)]
        data = _export_findings(auditor)
        finding = next(f for f in data['findings'] if f['type'] == 'vendor_redundancy')
        assert 'hotjar' in finding['tag']
        assert 'fullstory' in finding['tag']

    def test_single_tool_no_redundancy(self, auditor):
        tags = {'google_analytics_4': _tag(category='Analytics')}
        auditor.page_data = [_make_page('https://example.com', tags=tags)]
        data = _export_findings(auditor)
        assert 'vendor_redundancy' not in _finding_types(data)


class TestMissingMetadata:
    def test_missing_title(self, auditor):
        auditor.page_data = [_make_page(
            'https://example.com',
            metadata={'title': '', 'description': 'Has desc', 'canonical': 'https://example.com'},
        )]
        data = _export_findings(auditor)
        assert 'missing_title' in _finding_types(data)

    def test_missing_description(self, auditor):
        auditor.page_data = [_make_page(
            'https://example.com',
            metadata={'title': 'Has title', 'description': '', 'canonical': 'https://example.com'},
        )]
        data = _export_findings(auditor)
        assert 'missing_description' in _finding_types(data)

    def test_duplicate_titles(self, auditor):
        auditor.page_data = [
            _make_page('https://example.com/a', metadata={'title': 'Same Title', 'description': 'desc', 'canonical': '/a'}),
            _make_page('https://example.com/b', metadata={'title': 'Same Title', 'description': 'desc', 'canonical': '/b'}),
            _make_page('https://example.com/c', metadata={'title': 'Different', 'description': 'desc', 'canonical': '/c'}),
        ]
        data = _export_findings(auditor)
        assert 'duplicate_titles' in _finding_types(data)
        finding = next(f for f in data['findings'] if f['type'] == 'duplicate_titles')
        assert '2 pages' in finding['detail']

    def test_no_metadata_findings_when_complete(self, auditor):
        auditor.page_data = [_make_page('https://example.com')]
        data = _export_findings(auditor)
        types = _finding_types(data)
        assert 'missing_title' not in types
        assert 'missing_description' not in types
        assert 'duplicate_titles' not in types


class TestPerformanceFindings:
    def test_slow_pages_detected(self, auditor):
        auditor.page_data = [
            _make_page('https://example.com/fast', performance={'load_time': 1000}),
            _make_page('https://example.com/fast2', performance={'load_time': 1100}),
            _make_page('https://example.com/slow', performance={'load_time': 5000}),
        ]
        data = _export_findings(auditor)
        assert 'slow_pages' in _finding_types(data)

    def test_no_slow_pages_when_uniform(self, auditor):
        auditor.page_data = [
            _make_page('https://example.com/a', performance={'load_time': 2000}),
            _make_page('https://example.com/b', performance={'load_time': 2100}),
        ]
        data = _export_findings(auditor)
        assert 'slow_pages' not in _finding_types(data)

    def test_tag_performance_correlation(self, auditor):
        few_tags = {'ga4': _tag(category='Analytics')}
        many_tags = {
            'ga4': _tag(category='Analytics'),
            'hotjar': _tag(category='Heatmaps'),
            'fb': _tag(category='Advertising'),
            'li': _tag(category='Advertising'),
            'microsoft_clarity': _tag(category='Session Recording'),
        }
        auditor.page_data = [
            _make_page('https://example.com/a', tags=few_tags, performance={'load_time': 1000}),
            _make_page('https://example.com/b', tags=few_tags, performance={'load_time': 1100}),
            _make_page('https://example.com/c', tags=few_tags, performance={'load_time': 1050}),
            _make_page('https://example.com/d', tags=few_tags, performance={'load_time': 1020}),
            _make_page('https://example.com/e', tags=few_tags, performance={'load_time': 1080}),
            _make_page('https://example.com/f', tags=many_tags, performance={'load_time': 3000}),
            _make_page('https://example.com/g', tags=many_tags, performance={'load_time': 3200}),
            _make_page('https://example.com/h', tags=many_tags, performance={'load_time': 2900}),
            _make_page('https://example.com/i', tags=many_tags, performance={'load_time': 3100}),
            _make_page('https://example.com/j', tags=many_tags, performance={'load_time': 3050}),
        ]
        data = _export_findings(auditor)
        assert 'tag_performance_correlation' in _finding_types(data)

    def test_tag_performance_correlation_requires_group_size(self, auditor):
        few_tags = {'ga4': _tag(category='Analytics')}
        many_tags = {
            'ga4': _tag(category='Analytics'),
            'hotjar': _tag(category='Heatmaps'),
        }
        auditor.page_data = [
            _make_page('https://example.com/a', tags=few_tags, performance={'load_time': 1000}),
            _make_page('https://example.com/b', tags=few_tags, performance={'load_time': 1100}),
            _make_page('https://example.com/c', tags=many_tags, performance={'load_time': 3000}),
            _make_page('https://example.com/d', tags=many_tags, performance={'load_time': 3200}),
        ]
        data = _export_findings(auditor)
        assert 'tag_performance_correlation' not in _finding_types(data)


class TestSilentGA4:
    def test_ga4_present_no_collect(self, auditor):
        tags = {'google_analytics_4': _tag(category='Analytics')}
        auditor.page_data = [
            _make_page('https://example.com', tags=tags, ga4_collect={}),
        ]
        data = _export_findings(auditor)
        assert 'silent_ga4' in _finding_types(data)

    def test_ga4_with_collect_not_silent(self, auditor):
        tags = {'google_analytics_4': _tag(category='Analytics')}
        auditor.page_data = [
            _make_page('https://example.com', tags=tags,
                       ga4_collect={'events': {'page_view': 1}, 'measurement_ids': ['G-123']}),
        ]
        data = _export_findings(auditor)
        assert 'silent_ga4' not in _finding_types(data)


class TestDataLayerPollution:
    def test_pushes_without_events(self, auditor):
        auditor.page_data = [
            _make_page('https://example.com',
                       datalayer={'total_events': 50, 'ga4_events': {}, 'ecommerce_events': [], 'gtag_config': []}),
        ]
        data = _export_findings(auditor)
        assert 'no_event_tracking' in _finding_types(data)

    def test_no_pollution_when_events_exist(self, auditor):
        auditor.page_data = [
            _make_page('https://example.com',
                       datalayer={'total_events': 50, 'ga4_events': {'page_view': 5}, 'ecommerce_events': [], 'gtag_config': []}),
        ]
        data = _export_findings(auditor)
        assert 'no_event_tracking' not in _finding_types(data)


class TestMultipleGTMContainers:
    def test_two_containers(self, auditor):
        tags = {
            'google_tag_manager': _tag(ids=['GTM-AAAA', 'GTM-BBBB'], category='Tag Management'),
        }
        auditor.page_data = [_make_page('https://example.com', tags=tags)]
        data = _export_findings(auditor)
        assert 'multiple_gtm_containers' in _finding_types(data)

    def test_single_container_no_finding(self, auditor):
        tags = {
            'google_tag_manager': _tag(ids=['GTM-AAAA'], category='Tag Management'),
        }
        auditor.page_data = [_make_page('https://example.com', tags=tags)]
        data = _export_findings(auditor)
        assert 'multiple_gtm_containers' not in _finding_types(data)


class TestDeadEndPages:
    def test_page_with_no_links(self, auditor):
        auditor.page_data = [
            _make_page('https://example.com/orphan', internal_links=0),
            _make_page('https://example.com/ok', internal_links=10),
        ]
        data = _export_findings(auditor)
        assert 'dead_end_pages' in _finding_types(data)

    def test_all_pages_well_linked(self, auditor):
        auditor.page_data = [
            _make_page('https://example.com/a', internal_links=5),
            _make_page('https://example.com/b', internal_links=8),
        ]
        data = _export_findings(auditor)
        assert 'dead_end_pages' not in _finding_types(data)


class TestTagAliases:
    def test_clarity_alias_merges_into_microsoft_clarity(self, auditor):
        """Old JSON with 'clarity' key must be treated as 'microsoft_clarity'."""
        tags = {'clarity': _tag(category='Heatmaps')}
        auditor.page_data = [_make_page('https://example.com', tags=tags)]
        data = _export_findings(auditor)
        assert 'microsoft_clarity' in data['tag_index']
        assert 'clarity' not in data['tag_index']

    def test_no_vendor_redundancy_for_alias_merge(self, auditor):
        """A page with both 'clarity' and 'microsoft_clarity' must not trigger vendor_redundancy."""
        tags = {
            'clarity': _tag(category='Heatmaps'),
            'microsoft_clarity': _tag(category='Session Recording'),
        }
        auditor.page_data = [_make_page('https://example.com', tags=tags)]
        data = _export_findings(auditor)
        # After merge there is only one tag; no redundancy
        assert 'vendor_redundancy' not in [f['type'] for f in data['findings']]
        assert 'microsoft_clarity' in data['tag_index']
        assert 'clarity' not in data['tag_index']


class TestFindingsSortOrder:
    def test_sorted_by_severity(self, auditor):
        tags = {
            'google_analytics_4': _tag(category='Analytics'),
            'microsoft_clarity': _tag(category='Analytics'),
            'hotjar': _tag(category='Heatmaps'),
            'clarity': _tag(category='Heatmaps'),
        }
        auditor.page_data = [
            _make_page('https://example.com', tags=tags,
                       metadata={'title': '', 'description': '', 'canonical': ''},
                       internal_links=0),
        ]
        data = _export_findings(auditor)
        severities = [f['severity'] for f in data['findings']]
        order = {'high': 0, 'medium': 1, 'low': 2}
        assert severities == sorted(severities, key=lambda s: order[s])
