# Changelog

## v3.4.0

Single-page audit API, LLM-optimized output format, and MCP server.

### Added

- **Single-page audit API** (`audit_page`).  Standalone async function that
  runs the full per-page analysis pipeline (metadata, tags, dataLayer, GA4
  collect decoding, performance, technology detection) without crawl
  orchestration.  Accepts an optional `browser` argument for persistent
  browser reuse.  Exported from the `choopscoop` package via lazy import.
- **LLM-optimized output format** (`format_page_llm`, `format_site_llm`).
  Compact projection of the JSON data model: strips detection internals
  (evidence, found bools, detection notes), raw network request logs, full
  meta tag lists, and screenshot paths.  Flattens metadata into top-level
  fields and merges datalayer and GA4 collect data into a single `ga4` key.
  Stable field order, empty sections omitted.
- **`--format llm` CLI flag.**  Exports site-level LLM format to
  `{prefix}-llm.json` alongside other export formats.
- **MCP server** (`choopscoop.mcp_server`).  Stdio-transport MCP server
  with six tools: `audit_page_tool`, `start_site_audit`,
  `get_audit_status`, `get_audit_results`, `list_patterns`, and
  `identify_unknowns`.  Features persistent browser with lazy init,
  lifespan shutdown hook, background crawl management with audit eviction,
  and a guarded import that prints a clear install message when the `mcp`
  extra is missing.
- **`choopscoop[mcp]` optional dependency** for the MCP SDK.
- **`choopscoop-mcp` console script** to launch the MCP server.

## v3.3.0

Findings engine and structured analysis exports.  ChoopScoop now
auto-generates a findings report with 17 issue types, a tag coverage
matrix, and organizes all output into per-run subdirectories.

### Added

- **Findings report export** (`export_findings`).  Produces a structured
  JSON analysis layer alongside the raw crawl data, containing:
  - Tag index with per-tag coverage, confidence, extracted IDs, evidence
    types, and absent-from page lists.
  - Technology index with per-technology coverage and evidence.
  - Category breakdown grouping tags by functional category.
  - GA4 summary aggregating measurement IDs, collect events, dataLayer
    events, and deduplicated gtag configuration.
  - Coverage profiles grouping pages by their exact tag fingerprint to
    surface template-level variation.
  - Third-party vendor summary with matched request counts and
    unidentified host inventory.
  - 17 auto-generated finding types with severity ratings: coverage_gap,
    dual_fire, multiple_measurement_ids, programmatic_ads,
    no_consent_management, unidentified_vendors,
    tag_profile_inconsistency, vendor_redundancy, missing_title,
    missing_description, duplicate_titles, slow_pages,
    tag_performance_correlation, silent_ga4, no_event_tracking,
    multiple_gtm_containers, dead_end_pages.
- **Tag coverage matrix export** (`export_tag_matrix`).  CSV matrix with
  pages as rows (grouped when identical tag profiles) and tags as columns.
  Includes a summary row with total page counts per tag.
- **Per-run output directories.**  Crawl output now lands in
  `output/run-{domain}/` instead of flat in `output/`.  All export paths,
  state files, and partial flushes follow the new structure automatically.
- **Audit-report Claude skill** (`.claude/skills/audit-report/`).  Reads
  crawl JSON and findings JSON to produce a client-ready narrative report
  in markdown at three tiers: factual summary, analytical, or advisory
  with expanded findings and recommendations.
- **Data dictionary** (`docs/DATA_DICTIONARY.md`).  Field definitions for
  patterns, detection output, and export schema.
- **Pipeline documentation** (`docs/PIPELINE.md`).  Full walkthrough of
  the data pipeline from crawl to report.
- 24 new tests covering findings generation: vendor redundancy, missing
  metadata, performance findings, silent GA4, dataLayer pollution,
  multiple GTM containers, dead-end pages, and severity sort order.
  Total: 264.

### Changed

- Default output prefix changed from `output/site-audit-{domain}` to
  `output/run-{domain}/site-audit-{domain}`.
- Updated README with findings export, tag matrix, narrative report,
  pipeline docs, and revised project structure.

## v3.2.0

Extended technology detection via Wappalyzer adapter.  ChoopScoop can now
detect ~5000 technologies by converting Wappalyzer OSS fingerprints at
runtime, without bundling any GPL data in the package.

### Added

- **Wappalyzer adapter module** (`wappalyzer_adapter.py`).  Build-time
  converter that transforms Wappalyzer-format fingerprints (scriptSrc, html,
  meta, headers) into ChoopScoop's TECHNOLOGY_PATTERNS schema.  Strips
  `\;version:\1` and `\;confidence:` suffixes, validates regexes, and
  normalizes keys to snake_case.
- **`--fetch-rulesets` CLI flag.**  Downloads Wappalyzer fingerprint data
  from GitHub to `~/.choopscoop/rulesets/` using stdlib urllib.  Tries
  multiple mirror URLs (enthec/webappanalyzer, AliasIO/wappalyzer,
  wappalyzer/wappalyzer) for resilience.  No URL argument required.
- **`--extended` CLI flag.**  Loads cached Wappalyzer rulesets, converts
  them, and merges with curated patterns using curated-wins semantics.
  All patterns are compiled once at load for performance (~4900 patterns
  in ~0.3s).
- **One-time pattern compilation** (`compile_patterns`).  Pre-compiles all
  regex patterns, meta patterns, and header patterns to `re.Pattern` objects.
  The auditor's detection methods transparently handle both compiled and
  string patterns.
- **Category mapping.**  Maps Wappalyzer's ~100 category IDs to
  ChoopScoop's 16 category strings via explicit ID map with name-based
  fallback.  Unmapped categories default to 'Other'.
- 36 new tests covering suffix stripping, key normalization, category
  mapping, entry conversion, merge semantics, pattern compilation, and
  end-to-end auditor integration with compiled patterns.  Total: 240.

### Changed

- `SiteAuditor.__init__` accepts optional `extended_tech_patterns` parameter
  for injecting pre-merged/compiled pattern dicts.
- `detect_technologies` and `_classify_network_requests` use
  `self._tech_patterns` instead of the global `TECHNOLOGY_PATTERNS`,
  enabling extended detection without modifying the curated pattern library.
- `url` CLI positional argument is now optional when `--fetch-rulesets` is
  used.

## v3.1.0

Evidence-based detection overhaul. Network requests are now the primary evidence
source for tag and technology detection, replacing the HTML-only approach that
caused false negatives, false positives, and event blindness.

### Added

- **Network request detection for tags.** Tags are now detected from captured
  third-party request hosts, not just inline HTML. LinkedIn Insight Tag, Google
  Ads/DoubleClick, and Facebook Pixel are now detected on sites where they fire
  only via network beacons with no inline signature.
- **Full third-party request capture.** The crawler now captures all requests to
  hosts that differ from the crawled page, replacing the previous 13-domain
  allowlist. Unknown vendors are no longer silently dropped.
- **Unidentified third-party host summary.** JSON export includes a deduplicated
  list of third-party hosts that did not match any known pattern, with request
  counts. Useful for competitive recon and privacy auditing.
- **GA4 Measurement Protocol decoder.** New `decode_ga4_collect_requests` method
  parses `google-analytics.com/g/collect` request URLs and POST bodies. Extracts
  event names (`en=`), measurement IDs (`tid=`), and event params (`ep.*`/`epn.*`).
  Deduplicates retransmissions (`_s=1` vs `_s=2`). Output stored under
  `ga4_collect_events` alongside the existing `datalayer` key.
- **gtag() argument object decoding in dataLayer parser.** `_parse_datalayer` now
  recognizes gtag() calls serialized as `{"0":"event","1":"purchase","2":{...}}`
  and routes them correctly: `event` commands go to the events list, while
  `config`/`consent`/`set`/`js`/`get` go to a new `gtag_config` summary.
- **Evidence and confidence model.** Every tag and technology detection now records
  what it matched on (`evidence` list) and a derived confidence level (`high`,
  `medium`, `low`). Evidence types: `html_pattern`, `script_url`, `request_host`,
  `request_url`, `meta`, `header`.
- **Technology detection from network requests.** Technologies with a `urls` field
  are now also matched against captured request hosts, enabling detection of
  platforms that load assets from known CDNs (e.g., Shopify via `cdn.shopify.com`).
- Added `urls` field to Shopify technology pattern for network corroboration.
- Added missing tag URL entries: `cm.g.doubleclick.net` and
  `pagead2.googlesyndication.com` for Google Ads, `platform.linkedin.com` for
  LinkedIn Insight, `facebook.com/tr` for Facebook Pixel.
- **Vendor-owned domain attribution.** Added `owned_domains` field to 22 pattern
  entries (16 tags, 6 technologies) listing registrable domains each vendor serves
  from. The unidentified third-party hosts bucket now excludes hosts attributable
  to a known vendor (e.g., `secure.quantserve.com` is attributed to Quantcast, not
  listed as unidentified). Only genuinely unknown vendors remain in the bucket.
- **Programmatic-Advertising tag category.** 4 new tags for ad-tech supply chain
  vendors: LiveRamp/Pippio (`rlcdn.com`, `pippio.com`), Index Exchange
  (`casalemedia.com`), PubMatic (`pubmatic.com`), Magnite/Rubicon Project
  (`rubiconproject.com`). Total tag count: 77.
- 42 new tests covering network detection, GA4 decoding, gtag argument parsing,
  false-positive hardening, evidence model, and host classification. Total: 204.

### Fixed

- **Magento false positives.** Bare `Magento` regex (case-insensitive) matched any
  text mention. Replaced with specific patterns: `Magento_Ui`, `mage/cookies`,
  `/skin/frontend/.*Magento`. Removed overly broad `/static/version` pattern.
- **WooCommerce false positives.** Bare `woocommerce` regex matched blog text.
  Replaced with `wc-cart-fragments`, `class="woocommerce`, and
  `wp-content/plugins/woocommerce`.
- **Bootstrap false positives.** CSS class pattern (`container`, `row`, `col-md`)
  matched nearly every site. Removed; kept only versioned filename pattern.
- **Tailwind false positives.** CSS utility class pattern (`flex`, `grid`,
  `text-sm`) matched nearly every site. Removed; kept only filename patterns.
  Added `detection_note` flagging that purged/bundled Tailwind is undetectable.
- **900 "unknown" dataLayer events** on gtag-heavy sites were actually gtag()
  argument objects. Now decoded correctly, with conversion events surfaced and
  config commands routed separately. Also fixed gtag argument detection for objects
  with GTM-injected non-numeric keys (e.g., `gtm.uniqueEventId`) that previously
  prevented recognition of `gtag('js', ...)` init calls.
- **POST data capture.** `log_request` now captures `request.post_data` on POST
  requests (guarded against Playwright exceptions), enabling GA4 collect request
  body parsing.

### Changed

- `detect_tags` signature: added optional `network_requests` parameter.
- `detect_technologies` signature: added optional `network_requests` parameter.
- `_parse_datalayer` return structure: added `gtag_config` key.
- JSON export: raw `network_requests` stripped from per-page data; replaced with
  top-level `matched_requests` and `unidentified_third_party_hosts` keys.
- Host-based URL matching uses `urllib.parse.urlparse` instead of substring
  matching to avoid false matches on short patterns.

## v3.0.1

- Added 11 ecommerce/DTC tag patterns: Shopify Web Pixels, Attentive, Yotpo, Nosto, Smile.io, Rebuy, Privy, Gorgias, AfterShip, Recharge, Bold Commerce
- Total tag detection expanded from 62 to 73 patterns
- Fixed resume bug where fresh crawls would not start due to empty state being loaded
- Fixed page load timeout by switching from networkidle to domcontentloaded with best-effort networkidle fallback
- Fixed JSON export crash caused by non-serializable datetime objects in crawl data
- Fixed .gitignore encoding corruption that prevented crawl output from being ignored

## v3.0.0

**Breaking:** Full restructure from single-file script to proper Python package.

- Reorganized into `src/choopscoop/` package layout (auditor, cli, patterns modules)
- Removed Wappalyzer subprocess dependency; all detection is now built-in
- Expanded technology detection from 8 to 50 patterns (CMS, frameworks, CDN, hosting, payment, monitoring)
- Added response header analysis for server/CDN/platform fingerprinting
- Cleaned up exception hierarchy and removed unused dependencies (aiofiles, requests)
- Updated pyproject.toml with proper src layout, console_scripts, and pytest config
- Stripped internal project management docs; streamlined for public consumption

## v2.1.1

- Fixed cross-platform Playwright browser path detection (Windows/macOS/Linux)
- Dependency checks no longer produce false errors on Windows

## v2.1.0

Initial public release.

- Playwright-powered async crawler with concurrent page processing
- 48 marketing/analytics tag detection patterns
- DataLayer extraction and GA4 event parsing
- Performance metrics (load time, FCP, DOM timings)
- Resume capability for interrupted crawls
- JSON, CSV, and HTML export
- YAML configuration support
- Cross-platform support (Windows, macOS, Linux)
