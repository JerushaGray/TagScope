"""Wappalyzer ruleset adapter -- converts Wappalyzer fingerprints to TagScope schema.

Wappalyzer fingerprint data is GPL-3.0 licensed.  This module never bundles
that data; it is fetched at runtime by the user (--fetch-rulesets) into a
local cache (~/.tagscope/rulesets/).  The adapter converts the format on
the fly so the MIT-licensed TagScope package never distributes GPL content.
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import urllib.request

# Pinned Wappalyzer commit for reproducible downloads.
# Update this when you want to pull newer fingerprints.
# Pinned commit SHA for reproducible downloads.
# Update this to pull a newer snapshot of the fingerprint data.
WAPPALYZER_COMMIT = "04faf243aaa5a2bb44b81520231c9be3b306cd0e"

# The Wappalyzer repo has moved between GitHub orgs multiple times.
# Try these mirrors in order until one responds.
_REPO_URLS = [
    f"https://raw.githubusercontent.com/enthec/webappanalyzer/{WAPPALYZER_COMMIT}/src/technologies",
    f"https://raw.githubusercontent.com/AliasIO/wappalyzer/{WAPPALYZER_COMMIT}/src/technologies",
    f"https://raw.githubusercontent.com/wappalyzer/wappalyzer/{WAPPALYZER_COMMIT}/src/technologies",
]
_CATEGORIES_URLS = [
    f"https://raw.githubusercontent.com/enthec/webappanalyzer/{WAPPALYZER_COMMIT}/src/categories.json",
    f"https://raw.githubusercontent.com/AliasIO/wappalyzer/{WAPPALYZER_COMMIT}/src/categories.json",
    f"https://raw.githubusercontent.com/wappalyzer/wappalyzer/{WAPPALYZER_COMMIT}/src/categories.json",
]

# Where rulesets are cached locally
RULESETS_DIR = Path.home() / ".tagscope" / "rulesets"

# When True, Wappalyzer "html" body-level patterns are included.
# Default False because they tend toward false positives on large DOMs.
INCLUDE_HTML_BODY = False

# Wappalyzer category ID -> TagScope category string mapping.
# IDs come from Wappalyzer's categories.json.  Unmapped IDs get a
# fallback based on the category name.
_CATEGORY_MAP: Dict[int, str] = {
    1: "CMS",
    2: "CMS",            # Message boards
    6: "E-commerce",
    11: "CMS",           # Blogs
    12: "JavaScript Framework",
    18: "CMS",           # Web frameworks (close enough)
    22: "CDN",
    27: "Programming Language",
    28: "Web Server",     # Operating systems -> treat as server
    31: "CDN",           # CDN
    32: "Performance Monitoring",
    34: "Web Server",
    36: "Hosting",
    41: "Payment",
    47: "CSS Framework",
    51: "UI Library",
    52: "JavaScript Library",
    57: "JavaScript Framework",  # Static site generators
    59: "JavaScript Library",
    62: "Hosting",       # PaaS
    63: "Hosting",       # IaaS
    64: "Security",
    67: "Font Service",
    68: "Error Tracking",
    75: "E-commerce",    # E-commerce (subtypes)
    76: "Performance Monitoring",
    78: "Security",      # SEO
    86: "Headless CMS",
    92: "E-commerce",
    95: "Performance Monitoring",
}

# Fallback: map Wappalyzer category name substrings to TagScope categories
_CATEGORY_NAME_FALLBACKS = [
    ("cms", "CMS"),
    ("e-commerce", "E-commerce"),
    ("ecommerce", "E-commerce"),
    ("cart", "E-commerce"),
    ("javascript", "JavaScript Library"),
    ("framework", "JavaScript Framework"),
    ("cdn", "CDN"),
    ("hosting", "Hosting"),
    ("server", "Web Server"),
    ("analytics", "Performance Monitoring"),
    ("monitoring", "Performance Monitoring"),
    ("error", "Error Tracking"),
    ("payment", "Payment"),
    ("font", "Font Service"),
    ("security", "Security"),
    ("css", "CSS Framework"),
    ("ui", "UI Library"),
]


def fetch_rulesets(target_dir: Optional[Path] = None) -> Path:
    """Download Wappalyzer technology JSON files to local cache.

    Uses stdlib urllib only (no requests dependency).
    Returns the directory where files were saved.
    """
    dest = target_dir or RULESETS_DIR
    dest.mkdir(parents=True, exist_ok=True)

    # Wappalyzer splits technologies across multiple letter-based files
    # (technologies/a.json, technologies/b.json, ... technologies/_.json)
    letters = list("abcdefghijklmnopqrstuvwxyz") + ["_"]

    print(f"Fetching Wappalyzer rulesets to {dest}...")

    # Fetch categories.json -- try each mirror until one works
    for categories_url in _CATEGORIES_URLS:
        try:
            req = urllib.request.Request(categories_url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                categories_data = resp.read()
            (dest / "categories.json").write_bytes(categories_data)
            print("  categories.json")
            break
        except Exception:
            continue
    else:
        logging.warning("Could not fetch categories.json from any mirror")

    # Detect which repo URL works by probing 'a.json'
    base_url = None
    for candidate in _REPO_URLS:
        try:
            probe_url = f"{candidate}/a.json"
            req = urllib.request.Request(probe_url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                probe_data = resp.read()
            # Save the probe result so we don't re-fetch
            (dest / "a.json").write_bytes(probe_data)
            base_url = candidate
            break
        except Exception:
            continue

    if not base_url:
        print("Could not reach any Wappalyzer mirror.", file=sys.stderr)
        return dest

    fetched = 1  # already fetched a.json from probe
    for letter in letters:
        if letter == "a":
            continue  # already fetched during probe
        url = f"{base_url}/{letter}.json"
        out_file = dest / f"{letter}.json"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            out_file.write_bytes(data)
            fetched += 1
        except Exception as e:
            logging.debug(f"Could not fetch {letter}.json: {e}")

    print(f"Fetched {fetched} technology files to {dest}")
    return dest


def _strip_wappalyzer_suffixes(pattern: str) -> str:
    r"""Remove Wappalyzer-specific suffixes like \;version:\1 and \;confidence:50."""
    # These appear after the regex proper, separated by \;
    return re.split(r"\\;", pattern)[0]


def _is_valid_regex(pattern: str) -> bool:
    """Check if a pattern compiles as valid regex."""
    try:
        re.compile(pattern)
        return True
    except re.error:
        return False


def _map_category(
    cat_ids: List[int],
    categories_lookup: Dict[int, str],
) -> str:
    """Map Wappalyzer category IDs to a TagScope category string.

    Tries the explicit ID map first, then falls back to name-based matching,
    then defaults to 'Other'.
    """
    for cid in cat_ids:
        if cid in _CATEGORY_MAP:
            return _CATEGORY_MAP[cid]

    # Fallback: check category name from categories.json
    for cid in cat_ids:
        name = categories_lookup.get(cid, "").lower()
        for substr, mapped in _CATEGORY_NAME_FALLBACKS:
            if substr in name:
                return mapped

    return "Other"


def convert_entry(
    name: str,
    entry: Dict,
    categories_lookup: Dict[int, str],
) -> Optional[Dict]:
    """Convert a single Wappalyzer technology entry to TagScope schema.

    Returns None if the entry has no usable fingerprints after conversion.
    """
    patterns = []
    meta_tuples: List[Tuple[str, str]] = []

    # scriptSrc -> patterns (URL patterns for script elements)
    script_src = entry.get("scriptSrc")
    if script_src:
        if isinstance(script_src, str):
            script_src = [script_src]
        for p in script_src:
            cleaned = _strip_wappalyzer_suffixes(p)
            if cleaned and _is_valid_regex(cleaned):
                patterns.append(cleaned)

    # html -> patterns (body-level HTML matching, gated by INCLUDE_HTML_BODY)
    if INCLUDE_HTML_BODY:
        html_patterns = entry.get("html")
        if html_patterns:
            if isinstance(html_patterns, str):
                html_patterns = [html_patterns]
            for p in html_patterns:
                cleaned = _strip_wappalyzer_suffixes(p)
                if cleaned and _is_valid_regex(cleaned):
                    patterns.append(cleaned)

    # dom -> skip (requires JS evaluation, out of scope for regex matching)

    # meta -> meta tuples [(name, pattern), ...]
    meta_dict = entry.get("meta")
    if isinstance(meta_dict, dict):
        for meta_name, meta_pattern in meta_dict.items():
            if isinstance(meta_pattern, str):
                cleaned = _strip_wappalyzer_suffixes(meta_pattern)
                if cleaned and _is_valid_regex(cleaned):
                    meta_tuples.append((meta_name, cleaned))
            elif isinstance(meta_pattern, list):
                for mp in meta_pattern:
                    cleaned = _strip_wappalyzer_suffixes(mp)
                    if cleaned and _is_valid_regex(cleaned):
                        meta_tuples.append((meta_name, cleaned))

    # headers -> header tuples [(name, pattern), ...]
    header_tuples: List[Tuple[str, str]] = []
    headers_dict = entry.get("headers")
    if isinstance(headers_dict, dict):
        for header_name, header_pattern in headers_dict.items():
            if isinstance(header_pattern, str):
                cleaned = _strip_wappalyzer_suffixes(header_pattern)
                if cleaned and _is_valid_regex(cleaned):
                    header_tuples.append((header_name.lower(), cleaned))

    # url -> urls list (page URL matching)
    urls = []
    url_field = entry.get("url")
    if isinstance(url_field, str):
        cleaned = _strip_wappalyzer_suffixes(url_field)
        if cleaned:
            urls.append(cleaned)
    elif isinstance(url_field, list):
        for u in url_field:
            cleaned = _strip_wappalyzer_suffixes(u)
            if cleaned:
                urls.append(cleaned)

    # If nothing usable, skip
    if not patterns and not meta_tuples and not header_tuples:
        return None

    # Map categories
    cat_ids = entry.get("cats", [])
    category = _map_category(cat_ids, categories_lookup)

    result: Dict = {
        "patterns": patterns,
        "category": category,
    }

    if meta_tuples:
        result["meta"] = meta_tuples
    if header_tuples:
        result["headers"] = header_tuples
    if urls:
        result["urls"] = urls

    # Website for reference
    website = entry.get("website")
    if website:
        result["website"] = website

    return result


def load_and_convert(rulesets_dir: Optional[Path] = None) -> Dict[str, Dict]:
    """Load all cached Wappalyzer JSON files and convert to TagScope schema.

    Returns a dict of {tech_name: tech_config} in the same format as
    TECHNOLOGY_PATTERNS from patterns.py.
    """
    src = rulesets_dir or RULESETS_DIR
    if not src.exists():
        logging.warning(f"Rulesets directory not found: {src}")
        return {}

    # Load categories for name-based fallback mapping
    categories_lookup: Dict[int, str] = {}
    cats_file = src / "categories.json"
    if cats_file.exists():
        try:
            with open(cats_file, "r") as f:
                cats_raw = json.load(f)
            for cid_str, cat_info in cats_raw.items():
                try:
                    categories_lookup[int(cid_str)] = cat_info.get("name", "")
                except (ValueError, AttributeError):
                    pass
        except Exception as e:
            logging.warning(f"Could not load categories.json: {e}")

    converted: Dict[str, Dict] = {}
    letters = list("abcdefghijklmnopqrstuvwxyz") + ["_"]

    for letter in letters:
        json_file = src / f"{letter}.json"
        if not json_file.exists():
            continue
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
        except Exception as e:
            logging.warning(f"Could not parse {json_file}: {e}")
            continue

        for tech_name, tech_entry in data.items():
            if not isinstance(tech_entry, dict):
                continue

            # Normalize the key to snake_case for consistency
            key = _normalize_key(tech_name)

            result = convert_entry(tech_name, tech_entry, categories_lookup)
            if result:
                converted[key] = result

    logging.info(f"Converted {len(converted)} Wappalyzer technologies")
    return converted


def _normalize_key(name: str) -> str:
    """Convert a technology name to a snake_case dict key.

    'Google Tag Manager' -> 'google_tag_manager'
    'Next.js' -> 'next_js'
    'Vue.js' -> 'vue_js'
    """
    key = name.lower()
    key = re.sub(r"[\s.\-/]+", "_", key)
    key = re.sub(r"[^a-z0-9_]", "_", key)
    key = re.sub(r"_+", "_", key)
    return key.strip("_")


def merge_patterns(
    curated: Dict[str, Dict],
    extended: Dict[str, Dict],
) -> Dict[str, Dict]:
    """Merge curated and extended patterns with curated-wins semantics.

    For keys that exist in both dicts, the curated entry is kept as-is.
    Extended entries only fill gaps (new keys not in curated).

    Returns a new dict (neither input is mutated).
    """
    merged = dict(curated)  # shallow copy
    added = 0
    for key, entry in extended.items():
        if key not in merged:
            merged[key] = entry
            added += 1
    logging.info(
        f"Merged patterns: {len(curated)} curated + {added} extended "
        f"= {len(merged)} total"
    )
    return merged


def compile_patterns(tech_patterns: Dict[str, Dict]) -> Dict[str, Dict]:
    """Pre-compile all regex patterns in a technology patterns dict.

    Replaces string patterns with compiled re.Pattern objects for
    faster matching during crawl.  The input dict is not mutated;
    a new dict is returned.
    """
    compiled = {}
    for name, config in tech_patterns.items():
        entry = dict(config)

        # Compile patterns list
        compiled_pats = []
        for p in entry.get("patterns", []):
            if isinstance(p, str):
                try:
                    compiled_pats.append(re.compile(p, re.IGNORECASE))
                except re.error:
                    logging.debug(f"Skipping invalid pattern for {name}: {p}")
            else:
                compiled_pats.append(p)  # already compiled
        entry["patterns"] = compiled_pats

        # Compile meta patterns
        if "meta" in entry:
            compiled_meta = []
            for meta_name, meta_pat in entry["meta"]:
                if isinstance(meta_pat, str):
                    try:
                        compiled_meta.append((meta_name, re.compile(meta_pat)))
                    except re.error:
                        pass
                else:
                    compiled_meta.append((meta_name, meta_pat))
            entry["meta"] = compiled_meta

        # Compile header patterns
        if "headers" in entry:
            compiled_headers = []
            for hdr_name, hdr_pat in entry["headers"]:
                if isinstance(hdr_pat, str):
                    try:
                        compiled_headers.append(
                            (hdr_name, re.compile(hdr_pat, re.IGNORECASE))
                        )
                    except re.error:
                        pass
                else:
                    compiled_headers.append((hdr_name, hdr_pat))
            entry["headers"] = compiled_headers

        compiled[name] = entry

    return compiled
