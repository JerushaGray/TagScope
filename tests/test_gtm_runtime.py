"""Tests for the published-container decoder (src/tagscope/gtm_runtime.py).

These pass as delivered -- they lock in what the reference container ACTUALLY
contains, which is the ground truth the crawl findings got wrong.
"""
import json
from pathlib import Path

import pytest

from tagscope.gtm_runtime import decode_container

FIXTURE = Path(__file__).parent / "fixtures" / "reference_site" / "gtm_container_GTM-P6TLSZF.json"


@pytest.fixture(scope="module")
def decoded():
    return decode_container(json.loads(FIXTURE.read_text()))


def _tag(decoded, tag_id):
    return next(t for t in decoded["tags"] if t["tag_id"] == tag_id)


def test_ga4_google_tag_fires_on_all_pages(decoded):
    # Contradicts audit finding #1 ("GA4 not configured within GTM")
    assert decoded["summary"]["ga4_all_pages_ids"] == ["G-SQ4Z7H3P33"]


def test_dev_property_is_host_scoped_not_all_pages(decoded):
    assert "G-PRHV028QXT" in decoded["summary"]["ga4_measurement_ids"]
    assert "G-PRHV028QXT" not in decoded["summary"]["ga4_all_pages_ids"]


def test_event_layer_exists(decoded):
    # Contradicts audit finding #2 ("zero conversion event tracking")
    names = {e["event_name"] for e in decoded["summary"]["ga4_event_tags"]}
    assert len(decoded["summary"]["ga4_event_tags"]) == 18
    assert {"hubspot_form_submission", "form_book_demo_website", "form_book_demo_paid",
            "demo_requested", "starter_card_click", "clickPhone"} <= names


def test_consent_defaults_granted_everywhere(decoded):
    cds = decoded["summary"]["consent_defaults"]
    assert len(cds) == 1
    region = cds[0]["regions"][0]
    assert region["region"] == "(all regions)"
    assert region["defaultConsentStatistics"] == "granted"
    assert region["defaultConsentMarketing"] == "granted"


def test_paused_tags(decoded):
    assert len(decoded["summary"]["paused_tags"]) == 7
    assert not any(t["fires_on_all_pages"] for t in decoded["tags"] if t["paused"])


def test_consent_requirements_per_tag(decoded):
    assert _tag(decoded, 22)["consent_required"] == ["ad_storage"]        # Facebook Custom HTML
    assert _tag(decoded, 56)["consent_required"] == ["ad_storage"]        # LinkedIn Insight
    assert _tag(decoded, 151)["consent_required"] == ["analytics_storage"]  # ZoomInfo (obfuscated)
    no_consent_ids = {t["tag_id"] for t in decoded["summary"]["tags_without_consent_requirement"]}
    assert {20, 54, 21} <= no_consent_ids  # Bing UET, Ads remarketing, Crazy Egg


def test_obfuscated_custom_html_flagged(decoded):
    assert decoded["summary"]["obfuscated_custom_html"] == [151]


def test_vendor_hints(decoded):
    assert "vendor:bing_ads" in _tag(decoded, 20)["vendor_hints"]
    assert "tr.capterra.com" in _tag(decoded, 177)["vendor_hints"]


def test_crazy_egg_blocked_on_blog(decoded):
    ce = _tag(decoded, 21)
    assert ce["blocked_by"] and "/blog" in ce["blocked_by"][0]
    assert ce["fires_on_all_pages"] is False
