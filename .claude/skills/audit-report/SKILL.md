---
description: Analyze a TagScope site audit JSON and produce a structured narrative report. Use when the user asks for a site audit report, audit summary, or audit analysis.
argument-hint: <path-to-json> [--tier 1|2|3]
---

## Context

TagScope is a Playwright-powered site auditor that detects marketing tags, technologies,
dataLayer events, and GA4 Measurement Protocol events across crawled pages. The JSON export
contains all crawl data. Your job is to read it and produce a client-ready narrative.

## Arguments

- `$0` -- Path to the TagScope JSON export file. Required.
- `--tier 1` -- Factual summary only (reformats the data).
- `--tier 2` -- Analytical (derives insights, flags anomalies). **Default.**
- `--tier 3` -- Advisory (includes recommendations and priority ranking).

If no file is provided, look for the most recent `site-audit-*.json` in the working directory.

## Instructions

Read the JSON file at `$0` using the Read tool. If a companion findings report exists
(same path with `-findings.json` suffix, e.g., `output/site-audit-example_com-findings.json`),
read that too -- it contains the pre-built tag index, technology index, coverage profiles,
GA4 summary, and auto-generated findings. Use the findings report as your primary data
source for sections 2-5 and 7, and fall back to the raw JSON for anything not covered.

Use the data dictionary at `docs/DATA_DICTIONARY.md` for field definitions if needed.

## Output

Write the finished report to `output/audit-report-{domain}.md`, where
`{domain}` is derived from the crawl's start_url (e.g., `output/audit-report-basemonkeys_com.md`).
Create the `output/` directory if it does not exist. Use the Write tool to save the file.
After writing, tell the user the output path.

**Do not hallucinate data. Every number, tag name, and finding must come from the JSON.**

### Report Structure

Produce the report in markdown with these sections. Skip any section where there is nothing
meaningful to report.

#### 1. Executive Summary (all tiers)
- Site crawled, page count, date
- Tag count, technology count, broken link count
- One-sentence overall assessment

#### 2. Tag Inventory (all tiers)
- Table: tag name, category, page count, confidence, notable IDs extracted
- Group by category

**Tier 2+ additions:**
- Flag tags present on fewer pages than expected (coverage gaps)
- Flag duplicate/overlapping tags (e.g., UA + GA4 dual-fire)
- Flag tags in the Advertising or Programmatic-Advertising category -- these represent
  data sharing with third parties
- Flag vendor redundancy (multiple tools in the same category, e.g., two heatmap tools)
- Flag multiple GTM containers if detected

#### 3. Technology Stack (all tiers)
- Table: technology name, category, page count, confidence
- Note any detection_notes present

**Tier 2+ additions:**
- Confirm CMS platform and whether detection is consistent across all pages
- Flag technologies detected on very few pages (potential template inconsistency)

#### 4. GA4 & DataLayer Analysis (all tiers)
- Measurement IDs found
- Event summary table: event name, count, type (ga4/custom/ecommerce)
- gtag_config commands summary

**Tier 2+ additions:**
- Flag measurement ID conflicts (multiple tid values)
- Flag high custom event counts (may indicate misconfiguration)
- Compare dataLayer events vs collect request events (intent vs reality)
- Flag conversion events and confirm they carry expected parameters
- Flag silent GA4 pages (tag present but no collect requests fired)
- Flag no event tracking (dataLayer active but zero named GA4 events -- no conversion measurement)

#### 5. Third-Party Vendor Inventory (all tiers)
- Matched request count
- Unidentified hosts (if any), with request counts

**Tier 2+ additions:**
- Count distinct vendor domains from matched requests
- Flag high-volume vendors (potential performance impact)
- Privacy surface: list all vendors receiving requests, grouped by purpose

#### 6. Site Health (all tiers)
- Broken link count and list (if any)
- Performance summary: average load time, slowest pages, FCP distribution

**Tier 2+ additions:**
- Correlate tag count with load time (do pages with more tags load slower?)
- Flag slow pages (>1.5x average load time)
- Flag pages missing critical metadata (title, description, canonical)
- Flag duplicate page titles
- Flag dead-end pages (1 or fewer internal links)
- Note crawl depth distribution

#### 7. Findings & Recommendations (tier 3 only)
- Pull all auto-generated findings from the findings report and expand each into:
  - **Finding**: what was observed
  - **Risk**: why it matters (privacy, performance, data quality, compliance)
  - **Recommendation**: specific action to take
  - **Priority**: High / Medium / Low
- Finding types to expect: `coverage_gap`, `dual_fire`, `multiple_measurement_ids`,
  `programmatic_ads`, `no_consent_management`, `unidentified_vendors`,
  `tag_profile_inconsistency`, `vendor_redundancy`, `missing_title`,
  `missing_description`, `duplicate_titles`, `slow_pages`,
  `tag_performance_correlation`, `silent_ga4`, `no_event_tracking`,
  `multiple_gtm_containers`, `dead_end_pages`
- Sort by priority descending

### Formatting Rules

- Use tables for inventories, not bullet lists
- Bold tag and technology names on first mention
- Include actual numbers from the data -- never say "several" or "many"
- If a tag has extracted IDs, show them (but redact if they look like tokens/secrets)
- Keep the tone professional and direct -- this is a deliverable, not a chat message
- Do not include raw JSON in the report
- Target length: Tier 1 ~500 words, Tier 2 ~1000-1500 words, Tier 3 ~2000 words
