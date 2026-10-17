"""Decode a *published* GTM container runtime (the ``resource`` object inside gtm.js).

This is the format TagScope saves as ``gtm_container_<ID>.json``: top-level keys
``resource`` (macros/tags/predicates/rules), ``runtime``, ``permissions``,
``sandboxed_scripts`` ... It is NOT the GTM UI export format (no tag names, no
trigger names), so everything here is reconstructed from the compiled rules.

Reference implementation for TagScope -- stdlib only, Python 3.9+.
Suggested home: ``src/tagscope/gtm_runtime.py``.

Public API
----------
decode_container(container: dict) -> dict
    {
      "container_version": str,
      "tags": [DecodedTag, ...],
      "summary": {...},          # counts + roll-ups used by findings
    }

DecodedTag = {
    "index": int, "tag_id": int|None, "function": "__gaawe",
    "type_label": "GA4 Event", "paused": bool,
    "params": {"eventName": ..., "measurementIdOverride": ..., ...},
    "fires_on": ["{{Event}} equals 'gtm.js'", ...],     # one string per firing rule
    "blocked_by": [...],
    "fires_on_all_pages": bool,  # an unconditional page-lifecycle rule exists
    "consent_required": ["ad_storage", ...],             # GTM "additional consent" setting
    "vendor_hints": ["bat.bing.com", ...],               # from Custom HTML / template permissions
}

Notes / known limits
--------------------
* Predicate argument macros are rendered with a best-effort label
  (``{{Page Path}}``, ``{{DLV hs-form-guid}}`` ...). Unknown macro types render as
  ``{{__fn}}``.
* ``fires_on_all_pages`` is True when a firing rule consists ONLY of an
  ``{{Event}} equals gtm.js|gtm.init|gtm.init_consent|gtm.dom|gtm.load``
  predicate (with no host/path filters).
* Consent defaults are read from Consent-Mode CMP templates that expose
  ``vtp_regionSettings`` / ``vtp_defaultConsent*`` params (Cookiebot's
  community template does). Other CMPs: extend ``_extract_consent_defaults``.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

PAGE_LIFECYCLE_EVENTS = {"gtm.js", "gtm.init", "gtm.init_consent", "gtm.dom", "gtm.load"}

TAG_TYPE_LABELS = {
    "__googtag": "Google Tag",
    "__gaawc": "GA4 Configuration (legacy)",
    "__gaawe": "GA4 Event",
    "__ua": "Universal Analytics",
    "__awct": "Google Ads Conversion",
    "__awec": "Google Ads Enhanced Conversions",
    "__awud": "Google Ads User-Provided Data",
    "__sp": "Google Ads Remarketing",
    "__gclidw": "Conversion Linker",
    "__flc": "Floodlight Counter",
    "__fls": "Floodlight Sales",
    "__bzi": "LinkedIn Insight",
    "__baut": "Microsoft Ads UET",
    "__cegg": "Crazy Egg",
    "__hjtc": "Hotjar",
    "__html": "Custom HTML",
    "__img": "Custom Image",
    "__cl": "Click Listener (legacy)",
    "__lcl": "Link Click Listener (legacy)",
    "__fsl": "Form Submit Listener (legacy)",
    "__tl": "Timer Listener (legacy)",
    "__sdl": "Scroll Depth Listener",
    "__ytl": "YouTube Listener",
    "__paused": "Paused tag",
}

PREDICATE_LABELS = {
    "_eq": "equals", "_cn": "contains", "_sw": "starts with", "_ew": "ends with",
    "_re": "matches regex", "_css": "matches CSS selector", "_lt": "<", "_le": "<=",
    "_gt": ">", "_ge": ">=",
}

# Hostnames worth surfacing when they appear inside Custom HTML / template permissions.
_HOST_RE = re.compile(
    r"(?:https?:)?//([a-z0-9.-]+\.[a-z]{2,})(?=[/\"'?\\])", re.IGNORECASE)
_KNOWN_SNIPPET_MARKERS = {
    "fbq(": "facebook_pixel",
    "_linkedin_partner_id": "linkedin_insight",
    "bat.bing.com": "bing_ads",
    "clarity.ms": "microsoft_clarity",
    "hs-scripts.com": "hubspot",
    "zi-scripts.com": "zoominfo",
    "capterra.com": "capterra",
    "hotjar": "hotjar",
}
# ZoomInfo WebSights ships a char-shift + base64 obfuscated loader. Flag the shape.
_OBFUSCATION_RE = re.compile(r"atob\(|String\.fromCharCode\(.*charCodeAt", re.DOTALL)


# --------------------------------------------------------------------------- helpers
def _macro_label(macros: List[dict], idx: int) -> str:
    try:
        m = macros[idx]
    except (IndexError, TypeError):
        return f"{{{{macro {idx}}}}}"
    fn = m.get("function", "?")
    if fn == "__e":
        return "{{Event}}"
    if fn == "__u":
        comp = str(m.get("vtp_component", "URL")).title()
        return "{{Page URL}}" if comp == "Url" else f"{{{{Page {comp}}}}}"
    if fn == "__v":
        return f"{{{{DLV {m.get('vtp_name')}}}}}"
    if fn == "__k":
        return f"{{{{Cookie {m.get('vtp_name')}}}}}"
    if fn == "__c":
        return f"{{{{Const {str(m.get('vtp_value'))[:40]}}}}}"
    if fn == "__j":
        return f"{{{{JS {m.get('vtp_name')}}}}}"
    if fn == "__f":
        return "{{Referrer}}"
    return f"{{{{{fn}}}}}"


def _render(value: Any, macros: List[dict]) -> Any:
    """Render runtime value encodings: ["macro", i], ["escape", v], ["template", ...], ["list", ...], ["map", k, v, ...]."""
    if isinstance(value, list) and value:
        head = value[0]
        if head == "macro" and len(value) > 1:
            return _macro_label(macros, value[1])
        if head == "escape" and len(value) > 1:
            return _render(value[1], macros)
        if head == "template":
            return "".join(str(_render(v, macros)) for v in value[1:])
        if head == "list":
            return [_render(v, macros) for v in value[1:]]
        if head == "map":
            items = value[1:]
            return {str(_render(items[i], macros)): _render(items[i + 1], macros)
                    for i in range(0, len(items) - 1, 2)}
    return value


def _predicate_text(pred: dict, macros: List[dict]) -> str:
    fn = pred.get("function", "?")
    neg = pred.get("any_of") is not None  # rare; kept for completeness
    op = PREDICATE_LABELS.get(fn, fn)
    text = f"{_render(pred.get('arg0'), macros)} {op} {_render(pred.get('arg1'), macros)!r}"
    return ("NOT " + text) if neg else text


def _is_lifecycle_only(pred_ids: List[int], predicates: List[dict], macros: List[dict]) -> bool:
    if len(pred_ids) != 1:
        return False
    p = predicates[pred_ids[0]]
    return (p.get("function") == "_eq"
            and _render(p.get("arg0"), macros) == "{{Event}}"
            and _render(p.get("arg1"), macros) in PAGE_LIFECYCLE_EVENTS)


def _vendor_hints(tag: dict, permissions: Dict[str, Any], macros: List[dict]) -> List[str]:
    hints = set()
    blob = ""
    if tag.get("function") == "__html":
        blob = str(_render(tag.get("vtp_html"), macros))
    elif str(tag.get("function", "")).startswith("__cvt_"):
        blob = str(permissions.get(tag["function"], ""))
    for host in _HOST_RE.findall(blob):
        hints.add(host.lower())
    for marker, vendor in _KNOWN_SNIPPET_MARKERS.items():
        if marker in blob:
            hints.add(f"vendor:{vendor}")
    if tag.get("function") == "__html" and _OBFUSCATION_RE.search(blob):
        hints.add("obfuscated_script")
    return sorted(hints)


def _extract_consent_defaults(tag: dict, macros: List[dict]) -> Optional[Dict[str, Any]]:
    """Return CMP consent defaults if this tag is a consent-mode CMP template."""
    if not str(tag.get("function", "")).startswith("__cvt_"):
        return None
    if "vtp_regionSettings" not in tag and not any(k.startswith("vtp_defaultConsent") for k in tag):
        return None
    out: Dict[str, Any] = {
        "consent_mode_enabled": tag.get("vtp_consentModeEnabled"),
        "wait_for_update_ms": tag.get("vtp_waitForUpdate"),
        "regions": [],
    }
    regions = _render(tag.get("vtp_regionSettings"), macros) or []
    for r in regions if isinstance(regions, list) else []:
        if isinstance(r, dict):
            out["regions"].append({
                "region": r.get("region") or "(all regions)",
                **{k: v for k, v in r.items() if k.startswith("defaultConsent")},
            })
    return out


# --------------------------------------------------------------------------- main API
def decode_container(container: Dict[str, Any]) -> Dict[str, Any]:
    res = container.get("resource", container)
    macros = res.get("macros", [])
    tags = res.get("tags", [])
    predicates = res.get("predicates", [])
    rules = res.get("rules", [])
    permissions = container.get("permissions", {}) or {}

    fires: Dict[int, List[List[int]]] = {i: [] for i in range(len(tags))}
    blocks: Dict[int, List[List[int]]] = {i: [] for i in range(len(tags))}
    rule_text: Dict[int, List[str]] = {i: [] for i in range(len(tags))}
    block_text: Dict[int, List[str]] = {i: [] for i in range(len(tags))}

    for rule in rules:
        ifs: List[int] = []
        unless: List[int] = []
        add: List[int] = []
        block: List[int] = []
        for part in rule:
            kind, ids = part[0], list(part[1:])
            {"if": ifs, "unless": unless, "add": add, "block": block}.get(kind, []).extend(ids)
        text = " AND ".join(_predicate_text(predicates[i], macros) for i in ifs)
        if unless:
            text += " UNLESS " + " OR ".join(_predicate_text(predicates[i], macros) for i in unless)
        for t in add:
            fires[t].append(ifs if not unless else ifs + [-1])  # -1 marks a conditional rule
            rule_text[t].append(text)
        for t in block:
            blocks[t].append(ifs)
            block_text[t].append(text)

    decoded: List[Dict[str, Any]] = []
    consent_defaults = []
    for i, t in enumerate(tags):
        fn = t.get("function", "?")
        params = {k[4:]: _render(v, macros) for k, v in t.items()
                  if k.startswith("vtp_") and k not in ("vtp_html",)}
        consent = _render(t.get("consent"), macros) or []
        cd = _extract_consent_defaults(t, macros)
        if cd:
            consent_defaults.append({"tag_index": i, "tag_id": t.get("tag_id"), **cd})
        decoded.append({
            "index": i,
            "tag_id": t.get("tag_id"),
            "function": fn,
            "type_label": TAG_TYPE_LABELS.get(fn, "Custom Template" if fn.startswith("__cvt_") else fn),
            "paused": fn == "__paused",
            "params": params,
            "fires_on": rule_text[i],
            "blocked_by": block_text[i],
            "fires_on_all_pages": any(-1 not in ids and _is_lifecycle_only(ids, predicates, macros)
                                      for ids in fires[i]) and not blocks[i] and fn != "__paused",
            "consent_required": consent if isinstance(consent, list) else [consent],
            "vendor_hints": _vendor_hints(t, permissions, macros),
        })

    ga4_ids = sorted({str(d["params"].get("tagId")) for d in decoded
                      if d["function"] == "__googtag" and str(d["params"].get("tagId", "")).startswith("G-")})
    ga4_all_pages = sorted({str(d["params"].get("tagId")) for d in decoded
                            if d["function"] == "__googtag" and d["fires_on_all_pages"]
                            and str(d["params"].get("tagId", "")).startswith("G-")})
    event_tags = [
        {"tag_id": d["tag_id"], "event_name": d["params"].get("eventName"),
         "measurement_id": d["params"].get("measurementIdOverride") or d["params"].get("measurementId"),
         "fires_on": d["fires_on"]}
        for d in decoded if d["function"] == "__gaawe"
    ]
    tracking_types = {"__html", "__sp", "__bzi", "__cegg", "__baut", "__hjtc", "__img"}
    # Tracking tags with no GTM-level "additional consent" requirement. Custom HTML
    # only counts when a vendor host/marker was recognised (skips pure dataLayer helpers).
    no_consent = [
        {"tag_id": d["tag_id"], "type": d["type_label"], "vendor_hints": d["vendor_hints"]}
        for d in decoded
        if (d["function"] in tracking_types or d["function"].startswith("__cvt_"))
        and not d["consent_required"] and not d["paused"]
        and (d["function"] != "__html" or d["vendor_hints"])
    ]
    return {
        "container_version": str(res.get("version", "")),
        "tags": decoded,
        "summary": {
            "tag_count": len(decoded),
            "paused_tags": [d["tag_id"] for d in decoded if d["paused"]],
            "by_type": _count(d["type_label"] for d in decoded),
            "ga4_measurement_ids": ga4_ids,
            "ga4_all_pages_ids": ga4_all_pages,
            "ga4_event_tags": event_tags,
            "tags_without_consent_requirement": no_consent,
            "obfuscated_custom_html": [d["tag_id"] for d in decoded if "obfuscated_script" in d["vendor_hints"]],
            "consent_defaults": consent_defaults,
        },
    }


def _count(items) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys
    result = decode_container(json.load(open(sys.argv[1])))
    print(json.dumps(result["summary"], indent=2, default=str))
