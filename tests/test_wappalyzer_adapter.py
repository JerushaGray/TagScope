"""Tests for Wappalyzer adapter module."""

import re
from tagscope.wappalyzer_adapter import (
    _strip_wappalyzer_suffixes,
    _is_valid_regex,
    _normalize_key,
    _map_category,
    convert_entry,
    merge_patterns,
    compile_patterns,
    load_and_convert,
)


class TestStripSuffixes:
    def test_version_suffix(self):
        assert _strip_wappalyzer_suffixes(r"jquery[\.-]([\d.]+)\.min\.js\;version:\1") == r"jquery[\.-]([\d.]+)\.min\.js"

    def test_confidence_suffix(self):
        assert _strip_wappalyzer_suffixes(r"Shopify\;confidence:50") == "Shopify"

    def test_version_and_confidence(self):
        assert _strip_wappalyzer_suffixes(r"Bootstrap v([\d.]+)\;version:\1\;confidence:50") == r"Bootstrap v([\d.]+)"

    def test_no_suffix(self):
        assert _strip_wappalyzer_suffixes("wp-content/") == "wp-content/"

    def test_empty_string(self):
        assert _strip_wappalyzer_suffixes("") == ""


class TestValidRegex:
    def test_valid(self):
        assert _is_valid_regex(r"wp-content/") is True

    def test_invalid(self):
        assert _is_valid_regex(r"[invalid") is False


class TestNormalizeKey:
    def test_spaces(self):
        assert _normalize_key("Google Tag Manager") == "google_tag_manager"

    def test_dots(self):
        assert _normalize_key("Next.js") == "next_js"

    def test_hyphens(self):
        assert _normalize_key("vue-router") == "vue_router"

    def test_special_chars(self):
        assert _normalize_key("ASP.NET (v4)") == "asp_net_v4"


class TestMapCategory:
    def test_known_id(self):
        assert _map_category([1], {}) == "CMS"

    def test_ecommerce_id(self):
        assert _map_category([6], {}) == "E-commerce"

    def test_name_fallback(self):
        assert _map_category([9999], {9999: "E-commerce platform"}) == "E-commerce"

    def test_unknown(self):
        assert _map_category([9999], {9999: "Quantum Computing"}) == "Other"

    def test_first_match_wins(self):
        assert _map_category([6, 1], {}) == "E-commerce"


class TestConvertEntry:
    def test_script_src_only(self):
        entry = {
            "scriptSrc": ["jquery\\.js"],
            "cats": [59],
        }
        result = convert_entry("jQuery", entry, {})
        assert result is not None
        assert "jquery\\.js" in result["patterns"]
        assert result["category"] == "JavaScript Library"

    def test_meta_dict(self):
        entry = {
            "scriptSrc": [],
            "meta": {"generator": r"WordPress\;version:\1"},
            "cats": [1],
        }
        result = convert_entry("WordPress", entry, {})
        assert result is not None
        assert ("generator", "WordPress") in result["meta"]

    def test_headers_dict(self):
        entry = {
            "scriptSrc": [],
            "headers": {"Server": r"nginx"},
            "cats": [34],
        }
        result = convert_entry("nginx", entry, {})
        assert result is not None
        assert ("server", "nginx") in result["headers"]

    def test_strips_version_suffix(self):
        entry = {
            "scriptSrc": [r"react[\.-]([\d.]+)\;version:\1"],
            "cats": [12],
        }
        result = convert_entry("React", entry, {})
        assert result is not None
        assert r"react[\.-]([\d.]+)" in result["patterns"]

    def test_no_fingerprints_returns_none(self):
        entry = {"cats": [1], "website": "https://example.com"}
        result = convert_entry("Empty", entry, {})
        assert result is None

    def test_invalid_regex_skipped(self):
        entry = {
            "scriptSrc": [r"[invalid", r"valid\.js"],
            "cats": [52],
        }
        result = convert_entry("Test", entry, {})
        assert result is not None
        assert len(result["patterns"]) == 1
        assert result["patterns"][0] == r"valid\.js"

    def test_url_field(self):
        entry = {
            "scriptSrc": ["example\\.js"],
            "url": "example\\.com",
            "cats": [1],
        }
        result = convert_entry("Example", entry, {})
        assert result is not None
        assert "example\\.com" in result["urls"]


class TestMergePatterns:
    def test_curated_wins(self):
        curated = {"wordpress": {"patterns": ["curated"], "category": "CMS"}}
        extended = {"wordpress": {"patterns": ["extended"], "category": "CMS"}}
        merged = merge_patterns(curated, extended)
        assert merged["wordpress"]["patterns"] == ["curated"]

    def test_new_entries_added(self):
        curated = {"wordpress": {"patterns": ["wp"], "category": "CMS"}}
        extended = {"drupal": {"patterns": ["drupal"], "category": "CMS"}}
        merged = merge_patterns(curated, extended)
        assert "wordpress" in merged
        assert "drupal" in merged
        assert len(merged) == 2

    def test_neither_mutated(self):
        curated = {"a": {"patterns": []}}
        extended = {"b": {"patterns": []}}
        curated_copy = dict(curated)
        extended_copy = dict(extended)
        merge_patterns(curated, extended)
        assert curated == curated_copy
        assert extended == extended_copy


class TestCompilePatterns:
    def test_compiles_string_patterns(self):
        patterns = {"test": {"patterns": [r"wp-content/"], "category": "CMS"}}
        compiled = compile_patterns(patterns)
        assert hasattr(compiled["test"]["patterns"][0], "search")

    def test_compiles_meta_patterns(self):
        patterns = {
            "test": {
                "patterns": [],
                "meta": [("generator", r"WordPress")],
                "category": "CMS",
            }
        }
        compiled = compile_patterns(patterns)
        name, pat = compiled["test"]["meta"][0]
        assert name == "generator"
        assert hasattr(pat, "search")

    def test_compiles_header_patterns(self):
        patterns = {
            "test": {
                "patterns": [],
                "headers": [("server", r"nginx")],
                "category": "Web Server",
            }
        }
        compiled = compile_patterns(patterns)
        name, pat = compiled["test"]["headers"][0]
        assert name == "server"
        assert hasattr(pat, "search")

    def test_skips_invalid_patterns(self):
        patterns = {"test": {"patterns": [r"[invalid"], "category": "CMS"}}
        compiled = compile_patterns(patterns)
        assert len(compiled["test"]["patterns"]) == 0

    def test_already_compiled_passed_through(self):
        compiled_pat = re.compile(r"test")
        patterns = {"test": {"patterns": [compiled_pat], "category": "CMS"}}
        result = compile_patterns(patterns)
        assert result["test"]["patterns"][0] is compiled_pat

    def test_does_not_mutate_input(self):
        patterns = {"test": {"patterns": ["wp-content/"], "category": "CMS"}}
        compile_patterns(patterns)
        assert isinstance(patterns["test"]["patterns"][0], str)


class TestLoadAndConvert:
    def test_missing_directory_returns_empty(self, tmp_path):
        result = load_and_convert(tmp_path / "nonexistent")
        assert result == {}


class TestCompiledPatternsWithAuditor:
    """Verify that compiled patterns work correctly with auditor detection."""

    def test_compiled_patterns_match_html(self):
        from tagscope.auditor import SiteAuditor
        from conftest import make_config

        compiled = compile_patterns({
            "test_tech": {
                "patterns": [r"test-framework-v\d+"],
                "category": "JavaScript Framework",
            }
        })
        config = make_config()
        auditor = SiteAuditor(config, extended_tech_patterns=compiled)
        result = auditor.detect_technologies(
            "<script src='test-framework-v3.js'></script>",
            [], {}
        )
        assert len(result) == 1
        assert result[0]["name"] == "test_tech"

    def test_compiled_meta_patterns_match(self):
        from tagscope.auditor import SiteAuditor
        from conftest import make_config

        compiled = compile_patterns({
            "test_cms": {
                "patterns": [],
                "meta": [("generator", r"TestCMS")],
                "category": "CMS",
            }
        })
        config = make_config()
        auditor = SiteAuditor(config, extended_tech_patterns=compiled)
        result = auditor.detect_technologies(
            "", [{"name": "generator", "content": "TestCMS 5.0"}], {}
        )
        assert len(result) == 1
        assert result[0]["name"] == "test_cms"

    def test_compiled_header_patterns_match(self):
        from tagscope.auditor import SiteAuditor
        from conftest import make_config

        compiled = compile_patterns({
            "test_server": {
                "patterns": [],
                "headers": [("server", r"TestServer")],
                "category": "Web Server",
            }
        })
        config = make_config()
        auditor = SiteAuditor(config, extended_tech_patterns=compiled)
        result = auditor.detect_technologies(
            "", [], {"server": "TestServer/2.0"}
        )
        assert len(result) == 1
        assert result[0]["name"] == "test_server"
