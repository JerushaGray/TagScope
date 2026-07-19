# TagScope Audit Pipeline

This document walks through the full audit pipeline -- from launching a crawl to producing a client-ready report -- and describes what data is gathered at each step.

---

## Step 1: Launch the Crawl

```bash
tagscope https://example.com
```

The CLI (`src/tagscope/cli.py`) parses arguments, loads configuration (defaults or a YAML config file), and initializes the `SiteAuditor`. Key settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `--max-pages` | 100 | Maximum pages to crawl |
| `--max-depth` | 3 | How many link-hops from the start URL |
| `--concurrent` | 3 | Parallel browser tabs (1-10) |
| `--rate-limit` | 1.0s | Delay between requests per tab |
| `--extended` | off | Enable Wappalyzer rulesets for broader tech detection |
| `--format` | json, csv, html | Export format(s) |

If `--extended` is passed, Wappalyzer fingerprints are loaded from the local cache and merged with built-in patterns before crawling begins.

---

## Step 2: Page-Level Data Collection

For each page, the Playwright browser navigates to the URL, waits for `domcontentloaded` and then `networkidle`, and collects the following:

### 2a. Network Request Interception

Every third-party request (host differs from the crawled domain) is captured in real time as the page loads:

- Request URL
- HTTP method (GET/POST)
- Resource type (script, stylesheet, fetch, image, etc.)
- POST body (if present -- used for GA4 collect decoding)
- Timestamp

These network logs feed into tag detection, GA4 collect decoding, and third-party vendor classification.

### 2b. Tag Detection

Tags are detected by matching page content and network requests against patterns defined in `src/tagscope/patterns.py`. Each tag pattern can use multiple detection methods:

| Method | How it works |
|--------|-------------|
| `html_pattern` | Regex match against inline `<script>` content |
| `script_url` | Substring match against external script `src` URLs |
| `request_host` | Match against intercepted third-party request hostnames |
| `request_url` | Substring match against full request URLs |

For each detected tag, the output includes:
- **found**: boolean
- **ids**: extracted identifiers (GA4 measurement IDs, GTM container IDs, Hotjar site IDs, etc.)
- **category**: functional classification (Analytics, Advertising, Heatmaps, Consent Management, etc.)
- **evidence**: which detection methods triggered and what matched
- **confidence**: high, medium, or low based on how many detection methods confirmed the tag

### 2c. Technology Detection

Technologies (CMS platforms, CDNs, JS libraries, font services, etc.) are detected using a similar pattern system in `TECHNOLOGY_PATTERNS`, plus optional Wappalyzer rulesets. Detection sources include:

- HTML content patterns
- Meta tag values (e.g., `<meta name="generator">`)
- Response headers (e.g., `server: cloudflare`)
- Script URLs and network requests

Each technology record includes name, category, confidence, evidence, and an optional detection note.

### 2d. Page Metadata

Extracted via JavaScript evaluation in the browser:

- `title` -- document title
- `description` -- meta description
- `keywords` -- meta keywords
- `canonical` -- canonical link URL
- `og_title`, `og_description`, `og_image` -- Open Graph tags
- `h1` -- all H1 elements
- `h2` -- first 5 H2 elements
- `robots` -- robots meta directive
- `viewport` -- viewport meta tag
- `charset` -- character encoding
- `lang` -- document language
- `meta_tags` -- all meta elements with name and content

### 2e. DataLayer Extraction

The crawler reads `window.dataLayer` and parses each push:

- **Standard events**: items with an `event` key are classified as GA4 standard, ecommerce, or custom events
- **gtag() arguments**: gtag calls serialize as `{"0":"config","1":"G-XXX"}` -- the parser identifies these and extracts `config`, `set`, `consent`, `get`, `js`, and `event` commands
- **gtag_config**: consent mode settings, measurement ID configs, developer IDs

Output includes total push count, GA4 event counts, ecommerce events, custom events, and the full gtag configuration chain.

### 2f. GA4 Measurement Protocol Decoding

Network requests to `google-analytics.com/g/collect` are decoded to extract:

- **Measurement IDs** (`tid` parameter)
- **Event names** (`en` parameter) -- page_view, scroll, conversion events, etc.
- **Event parameters** (`ep.*` and `epn.*` keys)
- Retransmission deduplication (via `_s` parameter)

This captures what GA4 actually sent to Google, as opposed to what the dataLayer intended to send.

### 2g. Performance Metrics

Captured from the browser's Performance API:

- `load_time` -- full page load (loadEventEnd - fetchStart)
- `dom_content_loaded` -- DOMContentLoaded timing
- `first_paint` -- time to first paint
- `first_contentful_paint` -- time to first contentful paint (FCP)
- `transfer_size` -- total transfer bytes
- `dom_interactive` -- time to DOM interactive

### 2h. Internal Link Discovery

All `<a href>` elements on the page are evaluated. Links are filtered to:
- Same domain only
- Exclude skip extensions (.pdf, .jpg, .png, .css, .js, etc.)
- Exclude patterns matching `--exclude` filters
- Respect `--max-depth` limits

The count of internal links found per page is stored (used later for dead-end page detection). New links are added to the crawl queue.

### 2i. Broken Link Detection

Any response with status >= 400 is logged as a broken link with URL, status code, and crawl depth. Additionally, links within page content that return error statuses during the link extraction phase are captured.

---

## Step 3: Automated Exports

When the crawl completes, the CLI automatically runs all configured exports in sequence.

### 3a. Raw JSON Export

**File:** `output/site-audit-{domain}.json`

The complete crawl dataset:

```
{
  "crawl_info": {           // Crawl metadata, tag/tech summary counts
    "start_url", "crawled_at", "total_pages", "pages_success",
    "pages_failed", "broken_links", "max_depth_reached",
    "tags_summary", "technologies_summary"
  },
  "sitemap": [...],          // All discovered URLs
  "broken_links": [...],     // URLs returning 4xx/5xx
  "matched_requests": [...], // Third-party network requests
  "pages": [                 // Full page-level data
    {
      "url", "depth", "status",
      "metadata": {...},
      "tags": {...},
      "datalayer": {...},
      "ga4_collect_events": {...},
      "technologies": [...],
      "performance": {...},
      "network_requests": [...],
      "internal_links_found": N,
      "screenshot": null,
      "crawled_at": "..."
    }
  ]
}
```

### 3b. Findings JSON Export

**File:** `output/site-audit-{domain}-findings.json`

A computed analysis layer derived from the raw data. This is not a copy -- it aggregates, cross-references, and analyzes the page-level data to produce:

**Tag Index** -- per-tag summary across all pages:
- Page count, coverage percentage, confidence level
- All extracted IDs (measurement IDs, container IDs, pixel IDs)
- Evidence types and detection methods used
- List of pages where the tag is absent (if coverage < 100%)

**Technology Index** -- per-technology summary:
- Page count, coverage percentage, confidence
- Evidence types, optional detection notes

**Category Breakdown** -- tags grouped by functional category

**GA4 Summary** -- aggregated across all pages:
- All measurement IDs found
- Collect event totals (event name to count)
- DataLayer event totals
- Total dataLayer push count
- Deduplicated gtag configuration chain

**Coverage Profiles** -- pages grouped by their exact tag fingerprint:
- Shows how many distinct tag stacks exist across the site
- Identifies the dominant profile and outlier pages

**Third-Party Summary** -- vendor request classification:
- Matched request count (requests to known vendor domains)
- Unidentified hosts with request counts

**Auto-Generated Findings** -- issues detected with type and severity:

| Finding Type | Severity | What It Detects |
|-------------|----------|-----------------|
| `coverage_gap` | high/medium | Tag present on some pages but not all |
| `dual_fire` | medium | Universal Analytics + GA4 both active |
| `multiple_measurement_ids` | medium | More than one GA4 measurement ID |
| `programmatic_ads` | low | Programmatic ad vendors doing ID syncing |
| `no_consent_management` | high | No CMP detected with tracking tags active |
| `unidentified_vendors` | medium | Unknown third-party hosts receiving requests |
| `tag_profile_inconsistency` | low | Multiple distinct tag stacks across pages |
| `vendor_redundancy` | medium | Multiple tools in the same category |
| `missing_title` | medium | Pages without a title tag |
| `missing_description` | low/medium | Pages without a meta description |
| `duplicate_titles` | low/medium | Multiple pages sharing the same title |
| `slow_pages` | medium | Pages loading >1.5x the site average |
| `tag_performance_correlation` | low | More tags correlate with slower load times |
| `silent_ga4` | high/medium | GA4 tag present but no collect requests fired |
| `no_event_tracking` | low | DataLayer active but zero GA4 events |
| `multiple_gtm_containers` | medium | More than one GTM container ID |
| `dead_end_pages` | low | Pages with 1 or fewer internal links |

Findings are sorted by severity (high first).

### 3c. Tag Coverage Matrix (CSV)

**File:** `output/site-audit-{domain}-tag-matrix.csv`

A spreadsheet-friendly matrix where:
- Rows are pages (grouped when multiple pages share an identical tag profile)
- Columns are every tag detected on at least one page
- Cells contain `x` (present) or blank (absent)
- A summary row shows total page counts per tag

### 3d. CSV Export

**File:** `output/site-audit-{domain}.csv`

Flat tabular export of page-level data for spreadsheet analysis.

### 3e. HTML Export

**File:** `output/site-audit-{domain}.html`

Interactive HTML report with sortable tables and visual summaries.

---

## Step 4: Narrative Report (Manual, On-Demand)

**File:** `output/audit-report-{domain}.md`

This is the only step that involves Claude. It is triggered manually:

```
/audit-report output/site-audit-{domain}.json --tier 3
```

The Claude skill reads the raw JSON and findings JSON, then produces a structured markdown report. It does not generate new findings -- it formats and expands the auto-generated findings into client-ready prose.

### Tiers

| Tier | Content | Target Length |
|------|---------|---------------|
| Tier 1 | Factual summary -- reformats data into tables | ~500 words |
| Tier 2 | Analytical -- flags anomalies, identifies patterns (default) | ~1000-1500 words |
| Tier 3 | Advisory -- expands each finding into Finding / Risk / Recommendation / Priority | ~2000 words |

### Report Sections

1. **Executive Summary** -- site, page count, tag/tech counts, one-sentence assessment
2. **Tag Inventory** -- tables grouped by category with coverage gaps and anomaly flags
3. **Technology Stack** -- tables with consistency and template variation analysis
4. **GA4 & DataLayer Analysis** -- measurement IDs, event tables, consent config, silent GA4 detection
5. **Third-Party Vendor Inventory** -- matched/unidentified vendor breakdown
6. **Site Health** -- performance stats, broken links, metadata issues, dead-end pages, crawl depth
7. **Findings & Recommendations** (tier 3 only) -- each finding expanded with risk, recommendation, and priority

---

## Output File Summary

After a full run with a tier 3 report, the output directory contains:

```
output/
  site-audit-{domain}.json           # Raw crawl data
  site-audit-{domain}-findings.json  # Computed analysis + auto-findings
  site-audit-{domain}-tag-matrix.csv # Tag coverage matrix
  site-audit-{domain}.csv            # Flat page data
  site-audit-{domain}.html           # Interactive HTML report
  audit-report-{domain}.md           # Narrative report (from Claude skill)
```
