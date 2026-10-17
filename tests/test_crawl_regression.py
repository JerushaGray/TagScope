"""TDD targets for docs/fixes/FIX_PLAN_v2.md.

Every test here is marked xfail until its FIX-xx is implemented. When a fix lands,
delete that test's xfail marker -- it must then pass. Names/signatures used here are
the contract defined in the fix plan; change both together if you rename anything.
"""
import json
from collections import defaultdict
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"
REF = FIX / "reference_site"


def _todo(fix_id):
    return pytest.mark.xfail(reason=f"{fix_id} not implemented yet", strict=False)


def _load_pages(name):
    """Rebuild page_data dicts (export_findings shape) from a trimmed fixture."""
    raw = json.loads((REF / name).read_text())
    pages = []
    for p in raw["pages"]:
        tags = {k: {"found": True, "ids": v["ids"], "category": v["category"],
                    "evidence": v["evidence"], "confidence": v["confidence"]}
                for k, v in p["tags"].items()}
        pages.append({
            "url": p["url"], "depth": p["depth"], "status": p["status"],
            "metadata": {"title": p["title"], "description": "x", "canonical": p["url"]},
            "tags": tags,
            "datalayer": {"total_events": p["datalayer_total_events"], "ga4_events": {},
                          "ecommerce_events": [], "gtag_config": p["gtag_config"],
                          "events": [{"event": e} for e in p["datalayer_event_names"]]},
            "ga4_collect_events": {"events": p["ga4_collect_events"]} if p["ga4_collect_events"] else {},
            "technologies": p["technologies"],
            "performance": {"load_time": p["load_time_ms"]},
            "network_requests": [],
            "internal_links_found": p["internal_links_found"],
            "screenshot": None, "crawled_at": p["crawled_at"],
        })
    return pages


def _findings(auditor, pages):
    import os
    import tempfile
    auditor.page_data = pages
    auditor.stats["tags_found"] = defaultdict(int)
    auditor.stats["technologies_found"] = defaultdict(int)
    for page in pages:
        for name, t in page["tags"].items():
            if t.get("found"):
                auditor.stats["tags_found"][name] += 1
        for tech in page["technologies"]:
            auditor.stats["technologies_found"][tech["name"]] += 1
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    auditor.export_findings(path)
    data = json.loads(Path(path).read_text())
    os.unlink(path)
    return data


# --------------------------------------------------------------- FIX-01 execution state
def test_classify_tag_status():
    from tagscope.auditor import classify_tag_status
    assert classify_tag_status(["html_pattern:GTM-x", "script_url:googletagmanager.com/gtm.js"]) == "declared"
    assert classify_tag_status(["request_host:www.googletagmanager.com"]) == "fired"
    assert classify_tag_status(["request_url:matomo.js"]) == "fired"


def test_detect_tags_sets_status(auditor):
    html = '<script>(function(w,d,s,l,i){})(window,document,"script","dataLayer","GTM-ABCD12");' \
           ' googletagmanager.com/gtm.js</script>'
    declared = auditor.detect_tags(html, "https://example.com", [])
    assert declared["google_tag_manager"]["status"] == "declared"
    fired = auditor.detect_tags(html, "https://example.com",
                                [{"url": "https://www.googletagmanager.com/gtm.js?id=GTM-ABCD12"}])
    assert fired["google_tag_manager"]["status"] == "fired"


def test_detect_script_deferral():
    from tagscope.auditor import detect_script_deferral
    scripts = [
        {"type": "rocketlazyloadscript", "src": "", "attrs": {"data-rocket-src": "https://www.googletagmanager.com/gtm.js"}},
        {"type": "text/plain", "src": "", "attrs": {"data-cookieconsent": "statistics"}},
        {"type": "text/javascript", "src": "https://dev.visualwebsiteoptimizer.com/j.php", "attrs": {}},
    ]
    out = detect_script_deferral(scripts)
    assert out["deferred"] is True
    assert set(out["mechanisms"]) == {"wp_rocket_delay_js", "cookiebot_autoblock"}
    assert out["count"] == 2


def test_passive_status_counts(auditor):
    data = _findings(auditor, _load_pages("passive-pages.json"))
    gtm = data["tag_index"]["google_tag_manager"]
    assert gtm["page_count"] == 147          # declared OR fired (back-compat)
    assert gtm["fired_page_count"] == 2      # pages where GTM actually executed
    types = {f["type"] for f in data["findings"]}
    assert "declared_not_executed" in types
    # coverage gaps for GTM-delivered tags must carry the explanation
    for f in data["findings"]:
        if f["type"] == "coverage_gap" and f["tag"] in {"google_analytics_4", "facebook_pixel",
                                                         "google_ads", "linkedin_insight"}:
            assert f.get("explained_by") == "declared_not_executed"


def test_interact_status_counts(auditor):
    data = _findings(auditor, _load_pages("interact-pages.json"))
    assert data["tag_index"]["google_tag_manager"]["fired_page_count"] == 20


# --------------------------------------------------------------- FIX-04 Optimize signature
def test_gtm_id_alone_is_not_google_optimize(auditor):
    html = '<script>gtm("GTM-P6TLSZF") googletagmanager.com/gtm.js</script>'
    assert "google_optimize" not in auditor.detect_tags(html, "https://example.com", [])


def test_optimize_url_still_detected(auditor):
    html = '<script src="https://www.googleoptimize.com/optimize.js?id=OPT-ABC1234"></script>'
    assert "google_optimize" in auditor.detect_tags(html, "https://example.com", [])


# --------------------------------------------------------------- FIX-05 Clarity duplicate
def test_single_clarity_signature(auditor):
    from tagscope.patterns import TAG_PATTERNS
    assert not ("clarity" in TAG_PATTERNS and "microsoft_clarity" in TAG_PATTERNS)
    reqs = [{"url": "https://www.clarity.ms/tag/abc123"}, {"url": "https://c.clarity.ms/c.gif"}]
    found = auditor.detect_tags("", "https://example.com", reqs)
    assert len([k for k in found if "clarity" in k]) == 1


# --------------------------------------------------------------- FIX-06 Wappalyzer categories
@pytest.mark.parametrize("cat_id,expected", [
    (67, "Consent Management"),   # Cookie compliance  (was "Font Service")
    (36, "Advertising"),          # Advertising        (was "Hosting")
    (32, "Marketing Automation"), # Marketing automation (was "Performance Monitoring")
    (52, "Customer Support"),     # Live chat          (was "JavaScript Library")
    (22, "Web Server"),           # Web servers        (was "CDN")
    (74, "A/B Testing"),
    (10, "Analytics"),            # via name fallback (was "Performance Monitoring")
])
def test_wappalyzer_category_map(cat_id, expected):
    from tagscope.wappalyzer_adapter import _map_category
    cats = json.loads((FIX / "wappalyzer_categories_04faf24.json").read_text())
    lookup = {int(k): v["name"] for k, v in cats.items()}
    assert _map_category([cat_id], lookup) == expected


# --------------------------------------------------------------- FIX-07 findings wording / logic
def test_no_event_tracking_is_observational(auditor):
    data = _findings(auditor, _load_pages("passive-pages.json"))
    for f in data["findings"]:
        if f["type"] in {"no_event_tracking", "no_events_observed"}:
            assert "not being measured" not in f["detail"]
            assert "No structured event tracking is in place" not in f["detail"]


def test_container_summary_suppresses_no_event_tracking(auditor):
    from tagscope.gtm_runtime import decode_container
    auditor.gtm_container_summary = decode_container(
        json.loads((REF / "gtm_container_GTM-P6TLSZF.json").read_text()))["summary"]
    data = _findings(auditor, _load_pages("passive-pages.json"))
    types = {f["type"] for f in data["findings"]}
    assert "no_event_tracking" not in types
    assert "consent_default_granted" in types
    assert data.get("gtm_container", {}).get("ga4_all_pages_ids") == ["G-SQ4Z7H3P33"]


# --------------------------------------------------------------- FIX-08 www redirect / scope
def test_adopt_www_redirect_host():
    from conftest import make_config
    from tagscope.auditor import SiteAuditor
    cfg = make_config()
    cfg["start_url"] = "https://example.com"
    a = SiteAuditor(cfg)
    a._adopt_redirect_host("https://www.example.com/")
    assert a.base_domain == "www.example.com"
    assert a.should_crawl("https://www.example.com/pricing")


def test_adopt_redirect_rejects_foreign_host():
    from conftest import make_config
    from tagscope.auditor import SiteAuditor
    cfg = make_config()
    cfg["start_url"] = "https://example.com"
    a = SiteAuditor(cfg)
    a._adopt_redirect_host("https://evil.example.net/")
    assert a.base_domain == "example.com"


def test_svg_assets_not_crawled(auditor):
    assert not auditor.should_crawl("https://example.com/assets/brand/logo.svg")


# --------------------------------------------------------------- FIX-11 perf correlation
def test_perf_correlation_requires_group_size(auditor):
    # reference passive fixture: the 0-tag group is 2 non-WordPress app pages,
    # the 11-tag group is 2 pricing pages -- both below the >=5 minimum
    data = _findings(auditor, _load_pages("passive-pages.json"))
    assert "tag_performance_correlation" not in {f["type"] for f in data["findings"]}
