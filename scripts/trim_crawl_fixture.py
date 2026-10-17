"""Trim a full TagScope crawl JSON (5-6 MB) into a small per-page fixture.

Keeps only what the execution-state / findings regression tests need:
per-page tag evidence kinds, dataLayer event names, GA4 collect events,
load time, link counts and technology name/category.

Usage:
    python scripts/trim_crawl_fixture.py output/<run>/site-audit-x.json fixtures/x/passive-pages.json
"""
import json
import sys
from pathlib import Path


def trim(src: Path) -> dict:
    data = json.loads(src.read_text())
    pages = []
    for p in data["pages"]:
        tags = {}
        for name, t in p.get("tags", {}).items():
            if not t.get("found"):
                continue
            tags[name] = {
                "evidence_kinds": sorted({e.split(":", 1)[0] for e in t.get("evidence", [])}),
                "evidence": t.get("evidence", []),
                "confidence": t.get("confidence"),
                "ids": t.get("ids", []),
                "category": t.get("category"),
            }
        dl = p.get("datalayer", {}) or {}
        pages.append({
            "url": p["url"],
            "depth": p.get("depth"),
            "status": p.get("status"),
            "title": (p.get("metadata") or {}).get("title"),
            "tags": tags,
            "datalayer_total_events": dl.get("total_events", 0),
            "datalayer_event_names": sorted({e.get("event") for e in dl.get("events", []) if e.get("event")}),
            "gtag_config": dl.get("gtag_config", []),
            "ga4_collect_events": (p.get("ga4_collect_events") or {}).get("events", {}),
            "load_time_ms": round((p.get("performance") or {}).get("load_time", 0) or 0),
            "internal_links_found": p.get("internal_links_found"),
            "technologies": [{"name": t["name"], "category": t["category"]} for t in p.get("technologies", [])],
            "crawled_at": p.get("crawled_at"),
        })
    return {
        "crawl_info": data.get("crawl_info", {}),
        "broken_links": data.get("broken_links", []),
        "unidentified_third_party_hosts": data.get("unidentified_third_party_hosts", {}),
        "pages": pages,
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    out = trim(Path(sys.argv[1]))
    Path(sys.argv[2]).write_text(json.dumps(out, indent=1))
    print(f"{len(out['pages'])} pages -> {sys.argv[2]}")
