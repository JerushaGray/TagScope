"""Tests for pattern data integrity."""

from tagscope.patterns import TAG_PATTERNS, GA4_EVENTS, TECHNOLOGY_PATTERNS


class TestPatternIntegrity:
    def test_tag_pattern_count(self):
        assert len(TAG_PATTERNS) == 77

    def test_technology_pattern_count(self):
        assert len(TECHNOLOGY_PATTERNS) == 50

    def test_ga4_event_count(self):
        assert len(GA4_EVENTS) == 25

    def test_all_tags_have_required_fields(self):
        for name, config in TAG_PATTERNS.items():
            assert 'patterns' in config, f"{name} missing 'patterns'"
            assert 'urls' in config, f"{name} missing 'urls'"
            assert 'category' in config, f"{name} missing 'category'"
            assert isinstance(config['patterns'], list), f"{name} patterns not a list"
            assert isinstance(config['urls'], list), f"{name} urls not a list"

    def test_all_techs_have_required_fields(self):
        for name, config in TECHNOLOGY_PATTERNS.items():
            assert 'patterns' in config, f"{name} missing 'patterns'"
            assert 'category' in config, f"{name} missing 'category'"
            assert isinstance(config['patterns'], list), f"{name} patterns not a list"

    def test_tag_categories_are_known(self):
        known = {
            'Tag Management', 'Analytics', 'Advertising', 'Server-Side Tracking',
            'Customer Data Platform', 'Heatmaps', 'Session Recording',
            'A/B Testing', 'Consent Management', 'E-commerce', 'Retargeting',
            'Marketing Automation', 'Customer Support', 'CRM',
            'Programmatic-Advertising',
        }
        for name, config in TAG_PATTERNS.items():
            assert config['category'] in known, f"{name} has unknown category: {config['category']}"

    def test_tech_categories_are_known(self):
        known = {
            'CMS', 'Headless CMS', 'E-commerce', 'JavaScript Framework',
            'JavaScript Library', 'CSS Framework', 'UI Library',
            'CDN', 'Hosting', 'Web Server', 'Programming Language',
            'Payment', 'Performance Monitoring', 'Error Tracking',
            'Font Service', 'Security',
        }
        for name, config in TECHNOLOGY_PATTERNS.items():
            assert config['category'] in known, f"{name} has unknown category: {config['category']}"

    def test_no_duplicate_tag_names(self):
        names = list(TAG_PATTERNS.keys())
        assert len(names) == len(set(names))

    def test_no_duplicate_tech_names(self):
        names = list(TECHNOLOGY_PATTERNS.keys())
        assert len(names) == len(set(names))

    def test_ga4_events_have_labels(self):
        for event_name, label in GA4_EVENTS.items():
            assert isinstance(label, str) and len(label) > 0, f"{event_name} has empty label"
