# Data Dictionary

Reference for all data structures in TagScope: pattern definitions, detection
output, JSON export schema, and GA4 event decoding.

---

## Pattern Definitions

### TAG_PATTERNS

Each key in `TAG_PATTERNS` is a snake_case tag identifier (e.g., `google_tag_manager`).
Values are dicts with these fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `patterns` | `list[str]` | Yes | Regex patterns matched against page HTML via `re.findall`. Capture groups extract IDs (e.g., `GTM-[A-Z0-9]{4,}` captures the container ID). |
| `urls` | `list[str]` | Yes | URL fragments matched two ways: (1) substring check against page HTML source to detect inline script references, and (2) host extraction via `urllib.parse` for matching against captured network request hosts. |
| `category` | `str` | Yes | One of: `Tag Management`, `Analytics`, `Advertising`, `Server-Side Tracking`, `Customer Data Platform`, `Heatmaps`, `Session Recording`, `A/B Testing`, `Consent Management`, `E-commerce`, `Retargeting`, `Marketing Automation`, `Customer Support`, `CRM`, `Programmatic-Advertising`. |
| `owned_domains` | `list[str]` | No | Registrable domains the vendor serves requests from. Used only for vendor attribution in the unidentified third-party hosts bucket -- not for detection. A network request host that ends with an owned domain is classified as "known" even if it does not match any `urls` entry. Example: `secure.quantserve.com` is attributed to Quantcast via `quantserve.com`. |

### TECHNOLOGY_PATTERNS

Each key is a snake_case technology identifier (e.g., `wordpress`, `shopify`).
Values are dicts with these fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `patterns` | `list[str]` | Yes | Regex patterns matched against the full rendered HTML via `re.search` with `re.IGNORECASE`. Only the first matching pattern produces evidence; the rest are skipped (short-circuit). |
| `category` | `str` | Yes | One of: `CMS`, `Headless CMS`, `E-commerce`, `JavaScript Framework`, `JavaScript Library`, `CSS Framework`, `UI Library`, `CDN`, `Hosting`, `Web Server`, `Programming Language`, `Payment`, `Performance Monitoring`, `Error Tracking`, `Font Service`, `Security`. Extended (Wappalyzer) patterns may also use `Other`. |
| `meta` | `list[tuple[str, str]]` | No | List of `(meta_name, regex_pattern)` tuples. Matched against `<meta>` tags where `name` or `property` equals `meta_name` and the `content` attribute matches the pattern. Case-sensitive (no `re.IGNORECASE`). |
| `headers` | `list[tuple[str, str]]` | No | List of `(header_name, regex_pattern)` tuples. Matched against HTTP response headers. Header names are lowercased. Pattern matching uses `re.IGNORECASE`. |
| `urls` | `list[str]` | No | URL fragments for network request corroboration. Host is extracted and compared against captured third-party request hosts, same as TAG_PATTERNS. Provides independent confirmation of technologies that load assets from known CDNs (e.g., `cdn.shopify.com`). |
| `owned_domains` | `list[str]` | No | Same semantics as TAG_PATTERNS: vendor attribution only, not detection. |
| `detection_note` | `str` | No | Free-text caveat surfaced in detection output. Used when a pattern has known reliability limitations (e.g., Tailwind CSS is undetectable when purged/bundled). |
| `website` | `str` | No | Vendor website URL. Present only on entries converted from Wappalyzer data. Informational, not used in detection. |

### GA4_EVENTS

A flat `dict[str, str]` mapping GA4 event names to human-readable labels.

| Key | Value | Example |
|-----|-------|---------|
| Event name (`str`) | Display label (`str`) | `'purchase'` -> `'Purchase'` |

Used by both the dataLayer parser and the GA4 collect decoder to classify
events as recognized GA4 events vs custom events.

---

## Detection Output

### Tag detection result

Returned by `detect_tags()` as `dict[str, dict]`. Each key is a tag name from
TAG_PATTERNS. Values:

| Field | Type | Description |
|-------|------|-------------|
| `found` | `bool` | Always `True` (only detected tags are included). |
| `ids` | `list[str]` | Extracted identifiers from regex capture groups. Empty list if patterns matched but had no capture groups. Example: `['GTM-ABC123']`. |
| `category` | `str` | Category from the pattern definition. |
| `evidence` | `list[str]` | What triggered the detection. Deduplicated, order-preserved. See [Evidence types](#evidence-types). |
| `confidence` | `str` | Derived from evidence. See [Confidence derivation](#confidence-derivation). |

### Technology detection result

Returned by `detect_technologies()` as `list[dict]`. Each entry:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Technology key from TECHNOLOGY_PATTERNS. |
| `category` | `str` | Category from the pattern definition. |
| `evidence` | `list[str]` | What triggered the detection. See [Evidence types](#evidence-types). |
| `confidence` | `str` | Derived from evidence. See [Confidence derivation](#confidence-derivation). |
| `detection_note` | `str` | Present only if the pattern definition includes one. |

---

## Evidence Types

Every detection records what it matched on as a list of typed strings.

| Evidence string | Format | Source | Used by |
|-----------------|--------|--------|---------|
| `html_pattern:{regex}` | Regex that matched in page HTML | `re.findall` (tags) or `re.search` (technologies) | Tags, Technologies |
| `script_url:{fragment}` | URL fragment found as substring in page HTML | Inline `<script src="...">` references | Tags only |
| `request_host:{hostname}` | Hostname of a captured third-party network request | Playwright request interception | Tags, Technologies |
| `request_url:{fragment}` | URL fragment found in a network request URL | Full URL substring match (fallback when host match fails) | Tags only |
| `meta:{name}` | Meta tag name whose content matched | `<meta name="..." content="...">` | Technologies only |
| `header:{name}` | Response header name whose value matched | HTTP response headers | Technologies only |

---

## Confidence Derivation

Confidence is derived from the evidence list at detection time. It is not
assigned manually per pattern.

### Tags

| Condition | Confidence |
|-----------|------------|
| Any evidence starts with `request_` | `high` |
| Any evidence starts with `script_url:` | `medium` |
| HTML pattern match only | `medium` |

### Technologies

| Condition | Confidence |
|-----------|------------|
| Any evidence starts with `request_host:`, `header:`, or `meta:` | `high` |
| HTML pattern match only | `medium` |

The `low` confidence level exists as a constant but is not currently assigned
by any shipped pattern. It is reserved for future use with generic/loose
regex patterns.

---

## JSON Export Schema

Top-level keys in the exported JSON file:

| Key | Type | Description |
|-----|------|-------------|
| `crawl_info` | `object` | Crawl metadata and aggregate summaries. |
| `sitemap` | `list[str]` | Ordered list of all crawled page URLs. |
| `broken_links` | `list[object]` | Pages that returned HTTP 400+. |
| `matched_requests` | `list[object]` | Network requests attributed to a known vendor (via `urls` or `owned_domains`). |
| `unidentified_third_party_hosts` | `dict[str, int]` | Hostnames not attributable to any known vendor, with request counts. Sorted descending by count. |
| `pages` | `list[object]` | Per-page crawl data (network_requests stripped). |

### crawl_info

| Field | Type | Description |
|-------|------|-------------|
| `start_url` | `str` | The URL the crawl started from. |
| `crawled_at` | `str` | ISO 8601 timestamp of export time. |
| `total_pages` | `int` | Number of pages in the export. |
| `pages_success` | `int` | Pages that returned HTTP 200-399. |
| `pages_failed` | `int` | Pages that failed after retries. |
| `broken_links` | `int` | Count of HTTP 400+ responses. |
| `max_depth_reached` | `int` | Deepest crawl depth in the dataset. |
| `tags_summary` | `dict[str, int]` | Tag name -> page count across all pages. |
| `technologies_summary` | `dict[str, int]` | Technology name -> page count across all pages. |

### broken_links (array items)

| Field | Type | Description |
|-------|------|-------------|
| `url` | `str` | The URL that returned an error status. |
| `status` | `int` | HTTP status code. |
| `depth` | `int` | Crawl depth where the link was found. |

### matched_requests / network_requests (array items)

| Field | Type | Description |
|-------|------|-------------|
| `url` | `str` | Full request URL. |
| `method` | `str` | HTTP method (`GET`, `POST`, etc.). |
| `type` | `str` | Playwright resource type (`script`, `image`, `ping`, `xhr`, etc.). |
| `post_data` | `str\|null` | POST body if method is POST and Playwright could read it. |
| `timestamp` | `str` | ISO 8601 timestamp of when the request was captured. |

### pages (array items)

| Field | Type | Description |
|-------|------|-------------|
| `url` | `str` | Page URL. |
| `depth` | `int` | Crawl depth (0 = start URL). |
| `status` | `int` | HTTP status code. |
| `metadata` | `object` | Page metadata (see below). |
| `tags` | `dict[str, object]` | Tag detection results keyed by tag name. See [Tag detection result](#tag-detection-result). |
| `datalayer` | `object` | Parsed dataLayer output. See [DataLayer output](#datalayer-output). |
| `ga4_collect_events` | `object` | Decoded GA4 Measurement Protocol events. See [GA4 collect output](#ga4-collect-output). |
| `technologies` | `list[object]` | Technology detection results. See [Technology detection result](#technology-detection-result). |
| `performance` | `object` | Page performance metrics (see below). |
| `internal_links_found` | `int` | Count of internal links extracted from the page. |
| `screenshot` | `str\|null` | Path to screenshot file, if captured. |
| `crawled_at` | `str` | ISO 8601 timestamp of when the page was crawled. |

### metadata

| Field | Type | Description |
|-------|------|-------------|
| `title` | `str` | `<title>` tag content. |
| `description` | `str` | Meta description. |
| `keywords` | `str` | Meta keywords. |
| `canonical` | `str` | Canonical URL from `<link rel="canonical">`. |
| `og_title` | `str` | Open Graph title. |
| `og_description` | `str` | Open Graph description. |
| `og_image` | `str` | Open Graph image URL. |
| `h1` | `list[str]` | All `<h1>` text content. |
| `h2` | `list[str]` | First 5 `<h2>` text content. |
| `robots` | `str` | Meta robots directive. |
| `viewport` | `str` | Meta viewport value. |
| `charset` | `str` | Document character set. |
| `lang` | `str` | `<html lang="...">` attribute. |
| `meta_tags` | `list[object]` | All `<meta>` tags as `{name, content}` objects. |

### performance

| Field | Type | Description |
|-------|------|-------------|
| `load_time` | `float` | Total page load time in milliseconds. |
| `dom_content_loaded` | `float` | DOMContentLoaded timing in milliseconds. |
| `first_paint` | `float` | First Paint timing in milliseconds. |
| `first_contentful_paint` | `float` | First Contentful Paint in milliseconds. |
| `transfer_size` | `int` | Total transfer size in bytes. |
| `dom_interactive` | `float` | DOM interactive timing in milliseconds. |

---

## DataLayer Output

Returned by `_parse_datalayer()` and stored under the `datalayer` key per page.

| Field | Type | Description |
|-------|------|-------------|
| `total_events` | `int` | Total items in `window.dataLayer` (capped by `datalayer.max_events` config). |
| `events` | `list[object]` | All parsed events (see below). |
| `ga4_events` | `dict[str, int]` | Recognized GA4 event label -> count. Labels come from `GA4_EVENTS`. |
| `ecommerce_events` | `list[object]` | Events containing an `ecommerce` key (Enhanced Ecommerce / GA4 ecommerce). |
| `custom_events` | `list[str]` | Event names not recognized as GA4 or ecommerce. |
| `gtag_config` | `list[object]` | Decoded `gtag('config', ...)`, `gtag('consent', ...)`, `gtag('set', ...)`, `gtag('js', ...)`, and `gtag('get', ...)` calls. |

### events (array items)

| Field | Type | Description |
|-------|------|-------------|
| `event` | `str` | Event name. |
| `data` | `dict` | Full event payload (original dataLayer item or reconstructed from gtag args). |
| `type` | `str` | `'ga4'`, `'ecommerce'`, or `'custom'`. |
| `description` | `str` | Human-readable label from GA4_EVENTS. Present only when `type` is `'ga4'`. |
| `source` | `str` | `'gtag_arguments'` if decoded from a gtag() argument object. Absent for standard `dataLayer.push` events. |

### gtag_config (array items)

| Field | Type | Description |
|-------|------|-------------|
| `command` | `str` | The gtag command: `'config'`, `'consent'`, `'set'`, `'js'`, or `'get'`. |
| `target` | `str` | Second argument (e.g., measurement ID for `config`, `Date` object string for `js`). |
| `params` | `dict` | Third argument (configuration object). May be empty `{}`. |

### How gtag() argument objects are recognized

`gtag()` calls serialize into `window.dataLayer` as raw arguments objects with
numeric string keys: `gtag('event', 'purchase', {value: 99})` becomes
`{"0": "event", "1": "purchase", "2": {"value": 99}}`.

Detection gate: the item has key `"0"` and does not have key `"event"`. GTM may
inject additional non-numeric keys (e.g., `gtm.uniqueEventId`), so the check is
`'0' in item`, not "all keys are numeric."

Routing: if `item["0"]` is `"event"`, the item is parsed as an event.
If it is `"config"`, `"consent"`, `"set"`, `"js"`, or `"get"`, it goes to
`gtag_config`. Anything else is treated as a custom event.

---

## GA4 Collect Output

Returned by `decode_ga4_collect_requests()` and stored under the
`ga4_collect_events` key per page.

| Field | Type | Description |
|-------|------|-------------|
| `measurement_ids` | `list[str]` | Sorted unique GA4 measurement IDs (`tid=` parameter). Example: `['G-ABC123']`. |
| `events` | `dict[str, int]` | Event name -> count (after deduplication). |
| `event_details` | `list[object]` | Per-event details (see below). |
| `raw_request_count` | `int` | Total `/g/collect` requests before deduplication. |

### event_details (array items)

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Event name from `en=` parameter. |
| `params` | `dict` | Event parameters extracted from `ep.*` (string) and `epn.*` (numeric) query/body params. |
| `source` | `str` | Always `'collect_request'`. |
| `description` | `str` | Human-readable label from GA4_EVENTS. Present only for recognized events. |
| `measurement_id` | `str` | GA4 measurement ID from `tid=`. Present only if the request included one. |

### Deduplication

GA4 sends retransmissions with incrementing `_s=` values (e.g., `_s=1` then
`_s=2` for the same event). Deduplication key is `(event_name, tid, dl)` where
`dl` is the document location. Only the first occurrence is counted.

### Parameter extraction

| Query param prefix | Extracted as | Type |
|--------------------|-------------|------|
| `ep.{name}` | `params[name]` | `str` |
| `epn.{name}` | `params[name]` | `float` |

---

## Network Request Classification

At export time, `_classify_network_requests()` splits all captured third-party
requests into two buckets:

| Bucket | Criteria | Export key |
|--------|----------|-----------|
| **Matched** | Request host matches a `urls` fragment from any TAG_PATTERNS or TECHNOLOGY_PATTERNS entry, OR the host's registrable domain appears in any entry's `owned_domains`. | `matched_requests` |
| **Unidentified** | Host does not match any known pattern or owned domain. | `unidentified_third_party_hosts` |

The owned_domains check uses suffix matching: a request to `secure.quantserve.com`
is attributed to Quantcast because `quantserve.com` is in Quantcast's
`owned_domains` list. This prevents vendor subdomains from polluting the
unidentified bucket.

---

## Findings Report Schema

Exported as `{prefix}-findings.json` alongside the main JSON export.

### Top-level keys

| Key | Type | Description |
|-----|------|-------------|
| `report_info` | `object` | Site, domain, generation timestamp, total pages, TagScope version. |
| `tag_index` | `dict[str, object]` | Per-tag detail keyed by tag name. See below. |
| `technology_index` | `dict[str, object]` | Per-technology detail keyed by tech name. See below. |
| `category_breakdown` | `dict[str, list[str]]` | Tag category -> list of tag names in that category. |
| `ga4_summary` | `object` | Aggregated GA4 data across all pages. See below. |
| `coverage_profiles` | `list[object]` | Distinct tag profiles grouped by page. See below. |
| `third_party_summary` | `object` | Matched request count, unidentified host count and detail. |
| `findings` | `list[object]` | Auto-generated findings sorted by severity. See below. |

### tag_index entries

| Field | Type | Description |
|-------|------|-------------|
| `category` | `str` | Tag category from pattern definition. |
| `page_count` | `int` | Number of pages where this tag was detected. |
| `total_pages` | `int` | Total pages crawled. |
| `coverage_pct` | `float` | Percentage of pages with this tag (0-100). |
| `confidence` | `str` | Highest confidence level observed across all pages. |
| `ids` | `list[str]` | All unique IDs extracted (container IDs, measurement IDs, etc.). |
| `evidence_types` | `list[str]` | All unique evidence strings observed. |
| `detection_methods` | `list[str]` | Distinct evidence prefixes (e.g., `html_pattern`, `request_host`). |
| `absent_from` | `list[str]` | URLs where tag was not detected. Present only when coverage < 100%. |

### technology_index entries

| Field | Type | Description |
|-------|------|-------------|
| `category` | `str` | Technology category. |
| `page_count` | `int` | Number of pages where detected. |
| `total_pages` | `int` | Total pages crawled. |
| `coverage_pct` | `float` | Percentage of pages (0-100). |
| `confidence` | `str` | Highest confidence level observed. |
| `evidence_types` | `list[str]` | All unique evidence strings. |
| `detection_note` | `str` | Reliability caveat. Present only if the pattern definition includes one. |

### ga4_summary

| Field | Type | Description |
|-------|------|-------------|
| `measurement_ids` | `list[str]` | All unique GA4 measurement IDs from collect requests. |
| `collect_events` | `dict[str, int]` | Event name -> total count from `/g/collect` requests. |
| `datalayer_events` | `dict[str, int]` | Recognized GA4 event label -> total count from dataLayer. |
| `total_datalayer_pushes` | `int` | Total dataLayer items across all pages. |
| `gtag_config` | `list[object]` | Deduplicated gtag config/consent/set/js/get commands. |

### coverage_profiles entries

| Field | Type | Description |
|-------|------|-------------|
| `tags` | `list[str]` | Sorted list of tag names in this profile. |
| `tag_count` | `int` | Number of tags in the profile. |
| `page_count` | `int` | Number of pages sharing this exact tag set. |
| `pages` | `list[str]` | URLs (capped at 10, with "... and N more" overflow). |

### findings entries

| Field | Type | Description |
|-------|------|-------------|
| `type` | `str` | Finding type. One of: `coverage_gap`, `dual_fire`, `multiple_measurement_ids`, `programmatic_ads`, `no_consent_management`, `unidentified_vendors`, `tag_profile_inconsistency`, `vendor_redundancy`, `missing_title`, `missing_description`, `duplicate_titles`, `slow_pages`, `tag_performance_correlation`, `silent_ga4`, `no_event_tracking`, `multiple_gtm_containers`, `dead_end_pages`. |
| `severity` | `str` | `high`, `medium`, or `low`. |
| `tag` | `str` | Tag name(s) related to the finding, or `'none'`. |
| `detail` | `str` | Human-readable description of the finding. |

### Finding Type Reference

| Type | Default Severity | Trigger |
|------|-----------------|---------|
| `coverage_gap` | high (<50%) / medium (>50%) | Tag detected on some pages but not all. |
| `dual_fire` | medium | Both Universal Analytics and GA4 are active. |
| `multiple_measurement_ids` | medium | More than one GA4 measurement ID found in collect requests. |
| `programmatic_ads` | low | One or more Programmatic-Advertising category tags detected. |
| `no_consent_management` | high | No consent management tag but tracking/advertising tags are active. |
| `unidentified_vendors` | medium | Third-party request hosts not matched to any known pattern. |
| `tag_profile_inconsistency` | low | More than one distinct tag profile across pages. |
| `vendor_redundancy` | medium | Multiple tags serving the same functional purpose (e.g., 2 heatmap tools). Grouped categories: Analytics, Heatmaps + Session Recording, Tag Management, A/B Testing, Consent Management. |
| `missing_title` | medium | One or more pages have no title tag. |
| `missing_description` | medium (>10% of pages) / low | One or more pages have no meta description. |
| `duplicate_titles` | medium (>20% of pages) / low | Multiple pages share the same title tag value. |
| `slow_pages` | medium | One or more pages load more than 1.5x the site average. |
| `tag_performance_correlation` | low | Pages with more tags have measurably higher load times (>20% difference). |
| `silent_ga4` | high (>50% of pages) / medium | GA4 tag present but no Measurement Protocol collect requests fired. |
| `no_event_tracking` | low | DataLayer has pushes but zero named GA4 events -- no structured conversion tracking in place. |
| `multiple_gtm_containers` | medium | More than one GTM container ID extracted. |
| `dead_end_pages` | low | Pages with 1 or fewer internal outbound links. |

---

## Extended Patterns (Wappalyzer Adapter)

When `--extended` is used, Wappalyzer entries are converted to the same schema
as TECHNOLOGY_PATTERNS. The conversion mapping:

| Wappalyzer field | TagScope field | Notes |
|------------------|-----------------|-------|
| `scriptSrc` (list of regex) | `patterns` | Suffixes like `\;version:\1` and `\;confidence:50` are stripped. Invalid regexes are dropped. |
| `html` (list of regex) | `patterns` | Disabled by default (`INCLUDE_HTML_BODY = False`) due to false-positive risk. |
| `meta` (dict `{name: pattern}`) | `meta` (list of tuples) | Keys become the meta name; values become the regex pattern. |
| `headers` (dict `{name: pattern}`) | `headers` (list of tuples) | Header names are lowercased. |
| `url` (str or list) | `urls` | Suffixes stripped. |
| `cats` (list of int) | `category` | Mapped via ID lookup table, then name-based fallback, then `'Other'`. |
| `website` | `website` | Passed through as-is. Informational only. |

Merge rule: for any key that exists in both curated and extended, the curated
entry wins. Extended entries only fill gaps.

All patterns (regex, meta, headers) are compiled to `re.Pattern` objects once
at load via `compile_patterns()`. Compilation flags match the original
per-field behavior: `re.IGNORECASE` for `patterns` and `headers`, no flag
for `meta`.
