# Roadmap

## Released

### v3.0

- [x] Proper Python package layout (`src/tagscope/`)
- [x] 48 marketing/analytics tag patterns
- [x] 50 built-in technology detection patterns
- [x] Response header fingerprinting (web servers, CDNs, hosting platforms)
- [x] DataLayer and GA4 event parsing
- [x] Performance metric collection
- [x] JSON, CSV, and HTML export
- [x] State management and crawl resume
- [x] Cross-platform support
- [x] Test suite (pytest) and CI pipeline (GitHub Actions, Python 3.9-3.13)

### v3.1

- [x] Network request interception as primary detection source
- [x] Evidence and confidence model for every tag/technology detection
- [x] GA4 Measurement Protocol collect request decoder
- [x] gtag() argument object decoding in dataLayer parser
- [x] Unidentified third-party host inventory
- [x] Vendor-owned domain attribution
- [x] 77 tag patterns total (added programmatic-ad supply chain vendors)

### v3.2

- [x] Wappalyzer adapter (~5000 extended technology patterns, opt-in)
- [x] `--fetch-rulesets` and `--extended` CLI flags
- [x] One-time pattern compilation for performance

### v3.3

- [x] Findings engine: 17 auto-generated finding types with severity ratings
- [x] Tag coverage matrix export (CSV)
- [x] Per-run output directories
- [x] Audit-report Claude skill (`/audit-report`)

### v3.4

- [x] Single-page audit API (`audit_page()`)
- [x] LLM-optimized output format (`format_page_llm`, `format_site_llm`, `--format llm`)
- [x] MCP server with 6 tools (`tagscope[mcp]`, `tagscope-mcp`)
- [x] PyPI packaging (PEP 639, `tagscope[mcp]` optional extra)

## Planned

- [ ] MCP client connection docs: Claude Desktop config block, `mcp.json` at repo root
- [ ] End-to-end MCP validation against a live Claude Desktop session
- [ ] PyPI publish (`twine upload dist/*`)

## Future ideas

- Drift comparison: diff two crawl JSONs to surface tag changes between runs
- Raw-fetch mode: lightweight requests-based crawl for sites that don't require JS
- GA4 and GTM API integration for cross-referencing configured vs. detected events
- Streamlit dashboard for visual audit review
- Domain-based crawl presets (marketing sites, e-commerce, SaaS)
