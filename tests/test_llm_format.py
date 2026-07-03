"""Tests for LLM-optimized format projections."""

from choopscoop.auditor import format_page_llm, format_site_llm


def _sample_page(url='https://example.com', **overrides):
    """Build a realistic page_data dict for testing."""
    page = {
        'url': url,
        'depth': 0,
        'status': 200,
        'metadata': {
            'title': 'Example Page',
            'description': 'A test page for unit tests.',
            'keywords': '',
            'canonical': 'https://example.com',
            'og_title': '',
            'og_description': '',
            'og_image': '',
            'h1': ['Welcome'],
            'h2': ['About', 'Contact'],
            'robots': '',
            'viewport': 'width=device-width',
            'charset': 'utf-8',
            'lang': 'en',
            'meta_tags': [
                {'name': 'viewport', 'content': 'width=device-width'},
                {'name': 'generator', 'content': 'WordPress 6.4'},
            ],
        },
        'tags': {
            'google_tag_manager': {
                'found': True,
                'ids': ['GTM-ABC123'],
                'category': 'Tag Management',
                'evidence': ['html_pattern:GTM-[A-Z0-9]+', 'request_host:www.googletagmanager.com'],
                'confidence': 'high',
            },
            'google_analytics_4': {
                'found': True,
                'ids': ['G-XYZ789'],
                'category': 'Analytics',
                'evidence': ['html_pattern:G-[A-Z0-9]+'],
                'confidence': 'medium',
            },
        },
        'technologies': [
            {
                'name': 'wordpress',
                'category': 'CMS',
                'evidence': ['html_pattern:wp-content', 'meta:generator'],
                'confidence': 'high',
                'detection_note': 'Detected via wp-content paths.',
            },
            {
                'name': 'jquery',
                'category': 'JavaScript Library',
                'evidence': ['html_pattern:jquery'],
                'confidence': 'medium',
            },
        ],
        'datalayer': {
            'total_events': 3,
            'events': [
                {'event': 'gtm.js', 'data': {}, 'type': 'custom'},
                {'event': 'page_view', 'data': {}, 'type': 'ga4', 'description': 'Page View'},
            ],
            'ga4_events': {'Page View': 1},
            'ecommerce_events': [],
            'custom_events': ['form_submit'],
            'gtag_config': [
                {'command': 'config', 'target': 'G-XYZ789', 'params': {'send_page_view': True}},
            ],
        },
        'ga4_collect_events': {
            'measurement_ids': ['G-XYZ789'],
            'events': {'page_view': 1, 'scroll': 1},
            'event_details': [
                {'name': 'page_view', 'params': {}, 'source': 'collect_request',
                 'description': 'Page View', 'measurement_id': 'G-XYZ789'},
            ],
            'raw_request_count': 2,
        },
        'performance': {
            'load_time': 1200.0,
            'dom_content_loaded': 400.0,
            'first_paint': 200.0,
            'first_contentful_paint': 250.0,
            'transfer_size': 524288,
            'dom_interactive': 350.0,
        },
        'network_requests': [
            {'url': 'https://www.googletagmanager.com/gtm.js?id=GTM-ABC123',
             'method': 'GET', 'type': 'script', 'post_data': None,
             'timestamp': '2026-07-02T10:00:00'},
            {'url': 'https://www.google-analytics.com/g/collect?v=2&tid=G-XYZ789&en=page_view',
             'method': 'GET', 'type': 'ping', 'post_data': None,
             'timestamp': '2026-07-02T10:00:01'},
        ],
        'internal_links_found': 5,
        'screenshot': '/tmp/screenshots/index.png',
        'crawled_at': '2026-07-02T10:00:00',
    }
    page.update(overrides)
    return page


# ---------------------------------------------------------------------------
# format_page_llm
# ---------------------------------------------------------------------------

class TestFormatPageLlm:
    def test_strips_evidence(self):
        result = format_page_llm(_sample_page())
        for tag in result.get('tags', {}).values():
            assert 'evidence' not in tag

    def test_strips_found_bool(self):
        result = format_page_llm(_sample_page())
        for tag in result.get('tags', {}).values():
            assert 'found' not in tag

    def test_strips_network_requests(self):
        result = format_page_llm(_sample_page())
        assert 'network_requests' not in result

    def test_strips_meta_tags(self):
        result = format_page_llm(_sample_page())
        assert 'meta_tags' not in result
        assert 'metadata' not in result

    def test_strips_screenshot(self):
        result = format_page_llm(_sample_page())
        assert 'screenshot' not in result

    def test_strips_depth(self):
        result = format_page_llm(_sample_page())
        assert 'depth' not in result

    def test_strips_internal_links_found(self):
        result = format_page_llm(_sample_page())
        assert 'internal_links_found' not in result

    def test_strips_detection_note(self):
        result = format_page_llm(_sample_page())
        for tech in result.get('technologies', []):
            assert 'detection_note' not in tech

    def test_flattens_metadata(self):
        result = format_page_llm(_sample_page())
        assert result['title'] == 'Example Page'
        assert result['description'] == 'A test page for unit tests.'
        assert result['canonical'] == 'https://example.com'
        assert result['lang'] == 'en'
        assert result['h1'] == ['Welcome']

    def test_omits_empty_metadata(self):
        page = _sample_page()
        page['metadata']['description'] = ''
        page['metadata']['canonical'] = ''
        result = format_page_llm(page)
        assert 'description' not in result
        assert 'canonical' not in result

    def test_keeps_tag_ids_and_category(self):
        result = format_page_llm(_sample_page())
        gtm = result['tags']['google_tag_manager']
        assert gtm['ids'] == ['GTM-ABC123']
        assert gtm['category'] == 'Tag Management'
        assert gtm['confidence'] == 'high'

    def test_tags_without_ids_omit_field(self):
        page = _sample_page()
        page['tags']['google_tag_manager']['ids'] = []
        result = format_page_llm(page)
        assert 'ids' not in result['tags']['google_tag_manager']

    def test_technologies_simplified(self):
        result = format_page_llm(_sample_page())
        techs = result['technologies']
        assert len(techs) == 2
        assert techs[0] == {'name': 'jquery', 'category': 'JavaScript Library', 'confidence': 'medium'}
        assert techs[1] == {'name': 'wordpress', 'category': 'CMS', 'confidence': 'high'}

    def test_ga4_merged(self):
        result = format_page_llm(_sample_page())
        ga4 = result['ga4']
        assert ga4['measurement_ids'] == ['G-XYZ789']
        assert ga4['events']['page_view'] == 1
        assert ga4['events']['scroll'] == 1
        assert ga4['custom_events'] == ['form_submit']
        assert len(ga4['gtag_config']) == 1

    def test_ga4_no_event_details(self):
        result = format_page_llm(_sample_page())
        assert 'event_details' not in result.get('ga4', {})
        assert 'raw_request_count' not in result.get('ga4', {})

    def test_performance_preserved(self):
        result = format_page_llm(_sample_page())
        assert result['performance']['load_time'] == 1200.0

    def test_stable_key_order(self):
        result = format_page_llm(_sample_page())
        keys = list(result.keys())
        assert keys[0] == 'url'
        assert keys[1] == 'status'
        assert keys[-1] == 'crawled_at'

    def test_tags_sorted_alphabetically(self):
        result = format_page_llm(_sample_page())
        tag_names = list(result['tags'].keys())
        assert tag_names == sorted(tag_names)

    def test_technologies_sorted_by_name(self):
        result = format_page_llm(_sample_page())
        names = [t['name'] for t in result['technologies']]
        assert names == sorted(names)

    def test_no_tags_omits_key(self):
        page = _sample_page()
        page['tags'] = {}
        result = format_page_llm(page)
        assert 'tags' not in result

    def test_no_technologies_omits_key(self):
        page = _sample_page()
        page['technologies'] = []
        result = format_page_llm(page)
        assert 'technologies' not in result

    def test_no_ga4_data_omits_key(self):
        page = _sample_page()
        page['datalayer'] = {}
        page['ga4_collect_events'] = {}
        result = format_page_llm(page)
        assert 'ga4' not in result

    def test_no_performance_omits_key(self):
        page = _sample_page()
        page['performance'] = {}
        result = format_page_llm(page)
        assert 'performance' not in result


# ---------------------------------------------------------------------------
# format_site_llm
# ---------------------------------------------------------------------------

class TestFormatSiteLlm:
    def test_empty_pages(self):
        result = format_site_llm([])
        assert result == {'pages_audited': 0}

    def test_basic_structure(self):
        pages = [_sample_page('https://example.com/'), _sample_page('https://example.com/about')]
        result = format_site_llm(pages)
        assert result['url'] == 'https://example.com/'
        assert result['pages_audited'] == 2
        assert 'tags' in result
        assert 'technologies' in result
        assert 'pages' in result

    def test_tag_coverage(self):
        p1 = _sample_page('https://example.com/')
        p2 = _sample_page('https://example.com/about')
        # Remove GA4 from page 2
        del p2['tags']['google_analytics_4']
        result = format_site_llm([p1, p2])

        gtm = result['tags']['google_tag_manager']
        assert gtm['pages'] == 2
        assert gtm['coverage_pct'] == 100.0
        assert gtm['ids'] == ['GTM-ABC123']

        ga4 = result['tags']['google_analytics_4']
        assert ga4['pages'] == 1
        assert ga4['coverage_pct'] == 50.0

    def test_confidence_promotes_to_high(self):
        p1 = _sample_page('https://example.com/')
        p2 = _sample_page('https://example.com/about')
        p2['tags']['google_analytics_4']['confidence'] = 'high'
        result = format_site_llm([p1, p2])
        assert result['tags']['google_analytics_4']['confidence'] == 'high'

    def test_technology_aggregation(self):
        pages = [_sample_page('https://example.com/'), _sample_page('https://example.com/about')]
        result = format_site_llm(pages)
        wp = next(t for t in result['technologies'] if t['name'] == 'wordpress')
        assert wp['pages'] == 2

    def test_ga4_aggregate(self):
        pages = [_sample_page('https://example.com/'), _sample_page('https://example.com/about')]
        result = format_site_llm(pages)
        assert result['ga4']['measurement_ids'] == ['G-XYZ789']
        assert result['ga4']['events']['page_view'] == 2
        assert result['ga4']['events']['scroll'] == 2

    def test_performance_averages(self):
        p1 = _sample_page('https://example.com/')
        p2 = _sample_page('https://example.com/about')
        p2['performance']['load_time'] = 800.0
        result = format_site_llm([p1, p2])
        assert result['performance_avg']['load_time'] == 1000.0

    def test_broken_links_count(self):
        result = format_site_llm(
            [_sample_page()],
            broken_links=[{'url': 'https://example.com/404', 'status': 404, 'depth': 1}],
        )
        assert result['broken_links'] == 1

    def test_unidentified_hosts_capped(self):
        hosts = {f'vendor-{i}.example.com': 10 - i for i in range(25)}
        result = format_site_llm([_sample_page()], unidentified_hosts=hosts)
        assert len(result['unidentified_hosts']) == 20

    def test_per_page_records_are_llm_format(self):
        result = format_site_llm([_sample_page()])
        page_rec = result['pages'][0]
        # Should be LLM-projected (no network_requests, no evidence, etc.)
        assert 'network_requests' not in page_rec
        assert 'depth' not in page_rec
        assert 'title' in page_rec

    def test_no_broken_links_omits_key(self):
        result = format_site_llm([_sample_page()])
        assert 'broken_links' not in result

    def test_no_unidentified_hosts_omits_key(self):
        result = format_site_llm([_sample_page()])
        assert 'unidentified_hosts' not in result

    def test_ga4_per_page_dedup_not_global(self):
        """Datalayer events on page 2 should not be dropped just because
        page 1 had a collect event with the same name."""
        p1 = _sample_page('https://example.com/')
        # page 1: collect has page_view, datalayer also has Page View
        # (collect wins for page 1 -- count = 1)

        p2 = _sample_page('https://example.com/about')
        # page 2: NO collect events, but datalayer has Page View
        p2['ga4_collect_events'] = {'measurement_ids': [], 'events': {},
                                    'event_details': [], 'raw_request_count': 0}
        # datalayer still has Page View: 1

        result = format_site_llm([p1, p2])
        # page_view should be 1 (from p1 collect) + 1 (from p2 datalayer) = 2
        assert result['ga4']['events']['page_view'] == 2
