"""Shared fixtures for the TagScope test suite."""

import pytest
from tagscope.cli import _default_config


def make_config():
    """Return a test-ready config dict (non-fixture, for direct import)."""
    config = _default_config()
    config['start_url'] = 'https://example.com'
    config['resume']['enabled'] = False
    config['logging']['console'] = False
    config['logging']['log_file'] = None
    return config


@pytest.fixture
def default_config():
    """A default config dict with a start_url set."""
    return make_config()


@pytest.fixture
def auditor(default_config):
    """A SiteAuditor instance configured for testing (no Playwright needed)."""
    from tagscope.auditor import SiteAuditor
    return SiteAuditor(default_config)


@pytest.fixture
def sample_network_requests():
    """Synthetic network requests mimicking a HubSpot CMS site with
    LinkedIn/GA4/DoubleClick traffic."""
    return [
        {'url': 'https://px.ads.linkedin.com/collect/?pid=12345&fmt=gif',
         'method': 'GET', 'type': 'image', 'post_data': None},
        {'url': 'https://platform.linkedin.com/in.js',
         'method': 'GET', 'type': 'script', 'post_data': None},
        {'url': 'https://cm.g.doubleclick.net/pixel?google_nid=abc',
         'method': 'GET', 'type': 'image', 'post_data': None},
        {'url': 'https://www.google-analytics.com/g/collect?v=2&tid=G-ABC123&en=page_view&dl=https://example.com/',
         'method': 'GET', 'type': 'ping', 'post_data': None},
        {'url': 'https://www.google-analytics.com/g/collect?v=2&tid=G-ABC123&en=scroll&ep.percent_scrolled=90',
         'method': 'GET', 'type': 'ping', 'post_data': None},
        {'url': 'https://www.google-analytics.com/g/collect',
         'method': 'POST', 'type': 'ping',
         'post_data': 'v=2&tid=G-ABC123&en=conversion_event_submit_lead_form&ep.form_id=abc'},
        {'url': 'https://js.hs-scripts.com/12345.js',
         'method': 'GET', 'type': 'script', 'post_data': None},
        {'url': 'https://unknown-vendor.example.com/pixel.gif',
         'method': 'GET', 'type': 'image', 'post_data': None},
    ]
