# Roadmap

## v3.0 (current)

- [x] Proper Python package layout (`src/tagscope/`)
- [x] 48 marketing/analytics tag patterns
- [x] 50 built-in technology detection patterns (no external dependencies)
- [x] Response header fingerprinting (web servers, CDNs, hosting platforms)
- [x] DataLayer and GA4 event parsing
- [x] Performance metric collection
- [x] JSON, CSV, and HTML export
- [x] State management and crawl resume
- [x] Cross-platform support

## Next (planned)

- [ ] Test suite (pytest, tag detection and config loading coverage)
- [ ] CI pipeline (GitHub Actions, Python 3.9-3.13)
- [ ] Streamlined configuration (auto-detect crawl patterns)
- [ ] Network request analysis for tag verification (compare HTML patterns against actual outbound requests)
- [ ] Modular tag definition import (external YAML or JSON)

## Future ideas

- Optional Streamlit dashboard for visual audit review
- Privacy and consent tag compliance checks
- Domain-based crawl presets (marketing sites, e-commerce, SaaS)
- Integration with GA4 and GTM APIs for cross-referencing
