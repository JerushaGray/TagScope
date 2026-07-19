# TagScope

[![CI](https://github.com/JerushaGray/TagScope/actions/workflows/ci.yml/badge.svg)](https://github.com/JerushaGray/TagScope/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE.md)
[![Playwright](https://img.shields.io/badge/browser-Playwright-45ba63.svg)](https://playwright.dev/python/)

A Playwright-powered site auditor that crawls websites to detect marketing tags, identify technologies, parse dataLayer events, and generate structured reports. Built for marketing operations professionals who need visibility into what is actually firing on a site, not just what should be.

## What it detects

| Category | Count | Examples |
|----------|-------|---------|
| Marketing/analytics tags | 77 | GTM, GA4, Facebook Pixel, LinkedIn, TikTok, Adobe, HubSpot, Segment |
| Technologies | 50 | WordPress, Shopify, React, Next.js, Cloudflare, Stripe, Vercel |
| GA4 event types | 25 | purchase, add_to_cart, page_view, generate_lead, form_submit |

All detection uses built-in pattern matching against HTML, script sources, meta tags, response headers, and captured network requests. No external services or API keys required.

## Quick start

```bash
# Clone and install
git clone https://github.com/JerushaGray/TagScope.git
cd TagScope
pip install .

# Install the Chromium browser engine (one-time)
playwright install chromium

# Run an audit
tagscope https://example.com
```

## Usage

```bash
# Basic crawl (100 pages, depth 3, exports JSON + CSV + HTML)
tagscope https://example.com

# Larger crawl with higher concurrency
tagscope https://example.com --max-pages 500 --concurrent 5

# Single format output
tagscope https://example.com --format html --output my-report

# Filter URLs
tagscope https://example.com --exclude "/admin.*" "/login.*"

# Use a config file for repeatable settings
tagscope https://example.com --config config.yaml

# Also works as a module
python -m tagscope https://example.com
```

## Output

Each crawl creates a run directory at `output/run-{domain}/` containing:

| File | Contents |
|------|----------|
| `site-audit-{domain}.json` | Full crawl data: tags, technologies, dataLayer, GA4 collect events, performance, network requests |
| `site-audit-{domain}-findings.json` | Computed analysis: tag index, technology index, coverage profiles, GA4 summary, and auto-generated findings with severity ratings |
| `site-audit-{domain}-tag-matrix.csv` | Tag coverage matrix -- pages as rows, tags as columns, with group deduplication |
| `site-audit-{domain}.csv` | One row per page with tag presence, load time, link counts |
| `site-audit-{domain}.html` | Interactive dashboard with tag/tech summaries, broken links, page details |

### Auto-generated findings

The findings report detects 17 issue types automatically, including coverage gaps, UA/GA4 dual-fire, silent GA4 pages, missing consent management, vendor redundancy, duplicate titles, missing metadata, slow pages, dead-end pages, and programmatic ad vendor exposure. Each finding includes a type, severity (high/medium/low), and detail string.

### Narrative report (optional)

If you use [Claude Code](https://claude.ai/code), the bundled `/audit-report` skill reads the crawl JSON and produces a client-ready markdown report:

```
/audit-report output/run-example.com/site-audit-example_com.json --tier 3
```

| Tier | Content | Length |
|------|---------|--------|
| Tier 1 | Factual summary -- reformats data into tables | ~500 words |
| Tier 2 | Analytical -- flags anomalies, identifies patterns (default) | ~1000-1500 words |
| Tier 3 | Advisory -- expands each finding into Finding / Risk / Recommendation / Priority | ~2000 words |

See [docs/PIPELINE.md](docs/PIPELINE.md) for a full walkthrough of the data pipeline.

## How it works

```
URL --> Playwright (Chromium, headless)
         |
         |--> Intercept all third-party network requests
         |--> Extract script tags, meta tags, response headers
         |--> Match against 77 tag patterns (regex + URL signatures + network hosts)
         |--> Match against 50+ technology patterns (HTML, meta, headers, network)
         |--> Parse dataLayer for GA4/ecommerce/gtag events
         |--> Decode GA4 Measurement Protocol collect requests
         |--> Capture performance metrics (load time, FCP, DOM timings)
         |--> Extract internal links --> queue for next depth level
         |
         |--> Concurrent page processing (configurable, 1-10 pages)
         |--> Retry with backoff on timeouts and server errors
         |--> Periodic flush to disk for memory management
         |--> Resume capability via state files
         |
         v
    output/run-{domain}/
         |--> Raw JSON + CSV + HTML exports
         |--> Findings report (computed analysis + auto-findings)
         |--> Tag coverage matrix
         |--> [optional] Narrative report via /audit-report skill
```

## Project structure

```
src/tagscope/
    __init__.py              Package metadata and version
    __main__.py              python -m tagscope entry point
    auditor.py               SiteAuditor class: crawling, detection, export
    cli.py                   Argument parsing, config loading, entry point
    patterns.py              Tag patterns, technology patterns, GA4 event map
    wappalyzer_adapter.py    Wappalyzer fingerprint conversion and caching
config.yaml           Default configuration template
tests/                Test suite (264 tests, pytest)
docs/
    PIPELINE.md       Full pipeline walkthrough
    DATA_DICTIONARY.md  Field definitions for patterns, detection output, and export schema
    ARCHITECTURE.md   System architecture
    CONTRIBUTING.md   Development guidelines
    ROADMAP.md        Planned enhancements
```

## Configuration

Copy and edit `config.yaml` to customize crawl behavior. Key settings:

```yaml
crawl:
  max_pages: 100        # Page limit
  max_depth: 3          # Link-follow depth
  rate_limit: 1.0       # Seconds between requests
  concurrent_pages: 3   # Parallel page limit (1-10)

filters:
  exclude_patterns: ["/admin.*", "/api/.*"]
  skip_extensions: [".pdf", ".jpg", ".png", ".zip"]

output:
  formats: ["json", "csv", "html"]
  prefix: "output/site-audit"

resume:
  enabled: true         # Resume interrupted crawls
```

All settings can also be overridden via CLI flags. See `tagscope --help`.

## Extended technology detection

By default TagScope ships 50 curated technology patterns. For broader coverage (~5000 technologies), you can opt in to fingerprints from the [Wappalyzer](https://github.com/AliasIO/wappalyzer) open-source project:

```bash
# One-time: download fingerprints to ~/.tagscope/rulesets/
tagscope --fetch-rulesets

# Use them on your next crawl
tagscope https://example.com --extended
```

This is opt-in because the Wappalyzer fingerprint data is [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.en.html) licensed. TagScope (MIT) never bundles or redistributes that data -- `--fetch-rulesets` downloads it to your local machine only. The 50 curated patterns always take precedence when both sources define the same technology.

## Comparison

| Feature | TagScope | Screaming Frog | Lighthouse | python-seo-analyzer |
|---------|-----------|----------------|------------|---------------------|
| Marketing tag detection (77 tools) | Yes | No | No | No |
| Technology fingerprinting (50 curated, ~5000 extended) | Yes | Limited | No | No |
| DataLayer/GA4 event parsing | Yes | No | No | No |
| GA4 Measurement Protocol decoding | Yes | No | No | No |
| Auto-generated findings (17 types) | Yes | No | No | No |
| JavaScript-rendered pages | Yes (Playwright) | Yes | Yes | No |
| Performance metrics | Yes | Yes | Yes | No |
| Concurrent crawling | Yes (1-10 pages) | Yes | Single page | Yes |
| Resume interrupted crawls | Yes | No | N/A | No |
| Interactive HTML report | Yes | Yes | Yes | Yes |
| Free/open source | Yes (MIT) | Free tier limited | Yes | Yes |
| No external dependencies | Yes | N/A | Requires Chrome | Yes |

## Requirements

- Python 3.9+
- Playwright (installed automatically via pip)
- Chromium browser engine (`playwright install chromium`)

## License

[MIT](LICENSE.md)

## Author

**Jerusha Gray** -- Marketing Operations, MarTech, and Data Strategy
