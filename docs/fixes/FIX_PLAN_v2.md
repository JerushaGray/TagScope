# TagScope fix plan v2 — audit quality improvements (Oct 2026)

**Supersedes:** the fix plan from the zip bundle.
**Baseline to write against:** public `main` @ `17c9d71` (v3.5.0).
**Codespace HEAD:** `4eb50fb` — two commits ahead of public main; adds interaction
simulation and structured output folders. The interaction code exists but does **not**
meet the FIX-02 spec (see Step 0). Merge or reconcile before implementing FIX-02.

**How to work this plan:** fix in order within each priority tier. Each FIX has matching
xfail tests in `tests/test_crawl_regression.py` (from the zip bundle, renamed on
extraction — see the files table at the end). When a fix is done, delete that test's
`@_todo(...)` marker; it must pass and the full suite must stay green. The test counts on
`17c9d71` are 376 passed / 20 xfailed. Re-baseline after merging `4eb50fb` before
starting — the count may differ.

Every commit that changes an output field **must** update `CHANGELOG.md` (v3.6.0),
`docs/DATA_DICTIONARY.md`, and `docs/PIPELINE.md` in the same commit.

---

## Step 0 — Pre-flight (do this before any fix)

### 0a. Diagnose the interaction code gap

`4eb50fb`'s `_simulate_interactions` dispatches JavaScript `window.scrollTo()` calls at
25/50/75/100 % scroll depth. WP Rocket's "Delay JavaScript execution" waits for real
browser input events — `keydown`, `mousedown`, `mousemove`, `touchmove`, `touchstart`,
`touchend`, `wheel` — not JavaScript scroll calls. `window.scrollTo()` is not on that
list.

The 20-of-52 release rate was not caused by `gtm.click` events in the dataLayer —
`gtm.click` events are recorded BY GTM and therefore require GTM to already be running.
The actual mechanism: on pages where the existing code found clickable or hoverable
elements (the `.icon-flip` widgets), Playwright's `.click()` and `.hover()` dispatched
real `mousedown`/`mousemove` input that WP Rocket listened for, which released the
deferred scripts and let GTM load. Text-only pages (blog, integrations, `/book-a-demo`)
had nothing for the element-based code to interact with, so only `scrollTo()` ran, and
nothing was released.

**Why hovering nav links didn't release every page is an open question.** The nav hover
runs `item.is_visible()` before hovering — hidden mega-menu links may be failing that
check silently. Verify empirically on one page before assuming:

```python
# (a) run current _simulate_interactions on /take-more-bookings;
#     check whether gtm.js appears in the dataLayer
# (b) add a single page.mouse.move(400, 300) before the element code;
#     check again
# Report both results before replacing anything.
```

The existing code also has no before/after tag-state snapshot, no `page_info["interaction"]`
dict, and no `crawl_info["interaction_mode"]` field. None of the FIX-02 contract is met.

### 0b. Re-baseline

```bash
pip install -e '.[dev]'
pytest -q
```

Record the new pass/xfail counts and note any failures before touching any code.

---

## P0 — Correctness

### FIX-01 Separate "declared" from "fired"

**Where:** `auditor.py` — `detect_tags`, `_detect_tags_from_page`, `export_findings`
(tag_index + coverage findings), `_crawl_page` (page_info).

**Changes:**

1. Add a module-level `classify_tag_status(evidence: list[str]) -> str`. Returns
   `"fired"` when any evidence item starts with `"request_"`, else `"declared"`.
   Works from stored evidence so old JSONs can be reinterpreted without re-crawling.

2. In `detect_tags`, add `"status"` to every tag dict using `classify_tag_status`.
   Keep `found: True` for back-compat.

3. In `_detect_tags_from_page`, collect each script's `type`, `src`, and a small
   attribute dict (`data-rocket-src`, `data-rocket-type`, `data-cookieconsent`,
   `data-cfasync`, `data-src`, `class`). Pass to a new module-level
   `detect_script_deferral(scripts) -> {"deferred": bool, "mechanisms": [...],
   "count": int, "examples": [...]}`. Store as `page_info["script_deferral"]`.

   Deferral mechanisms to detect:

   | key | signature |
   | --- | --- |
   | `wp_rocket_delay_js` | `type="rocketlazyloadscript"` or `data-rocket-src`/`data-rocket-type` |
   | `litespeed_delay_js` | `type="litespeed/javascript"` |
   | `perfmatters_delay_js` | `type="pmdelayedscript"` |
   | `flying_scripts` | `type="flying-scripts"` or `data-type="lazy"` with `data-src` |
   | `cloudflare_rocket_loader` | `type` ending in `-text/javascript` |
   | `cookiebot_autoblock` | `type="text/plain"` + `data-cookieconsent` |
   | `onetrust_autoblock` | `type="text/plain"` + `class` containing `optanon-category-` |
   | `partytown` | `type="text/partytown"` |

4. Add `page_info["gtm_executed"]: bool` — True when dataLayer contains `gtm.js` OR a
   request hit `googletagmanager.com/gtm.js`.

5. `tag_index` entries gain `fired_page_count` (int) and `declared_only_pages` (list).
   `page_count` keeps its current meaning.

6. New finding `declared_not_executed` (severity **high**). Emitted when ≥1 page has
   GTM declared but not executed. Detail names the deferral mechanism(s), page count,
   and example URLs. States that tag coverage on those pages could not be observed.
   Must fire even when `script_deferral` is absent from page_data (e.g., fixtures built
   before this fix) — detect via status counts alone.

7. `coverage_gap` uses `fired_page_count`. When a tag's missing pages are all pages
   where `gtm_executed` is False, add `"explained_by": "declared_not_executed"` and
   change wording to "not observed (scripts deferred)".

8. `silent_ga4` must only consider pages where GA4 `status == "fired"` or where
   `gtm_executed` is True.

**Back-compat note:** `_load_pages` in the regression test fixture builds page_data
without `script_deferral` or `status` fields. All new code paths must handle these
fields being absent with safe defaults.

**Done when:** `test_classify_tag_status`, `test_detect_tags_sets_status`,
`test_detect_script_deferral`, `test_passive_status_counts` (GTM fired on exactly 2
passive pages in the reference fixture), and `test_interact_status_counts` (20) pass.

---

### FIX-02 Interaction mode that reliably releases deferred scripts

**Where:** `_simulate_interactions` in `auditor.py` (replace the existing
implementation); config/CLI `crawl.simulate_interaction` / `--interact`.

**The problem with `4eb50fb`:** `window.scrollTo()` is a JS call, not a browser input
event. WP Rocket ignores it. Replace it entirely.

**New implementation:**

- Snapshot request log length and tag statuses ("before").
- Dispatch real browser input on **every** page (replaces the `scrollTo` approach):
  - `page.mouse.move` sweep across the viewport in ~10 steps
  - `page.mouse.wheel(0, 800)` × 3
  - `page.keyboard.press("Tab")`
  - `page.wait_for_load_state('networkidle', timeout=5000)`
- Element-based hover/click is optional and may be kept, but **never click inside a
  consent banner container.** Guard every click with a check that the element is not
  inside any of:
  - `#CybotCookiebotDialog`
  - `#onetrust-banner-sdk`, `#onetrust-consent-sdk`
  - `[id*="cookie" i][role="dialog"]`
  - `.cmplz-cookiebanner`
  - `#usercentrics-root`

  The current code's `button:not([type="submit"]):not([disabled])` selector matches
  Cookiebot's "Allow All" button, which would silently accept consent and corrupt
  results from that mode.

- Log every element clicked in `page_info["interaction"]["events"]`.
- Re-run detection ("after").
- Record `page_info["interaction"] = {"performed": True, "events": [...],
  "tags_fired_after_interaction": [...]}`.
- Add `crawl_info["interaction_mode"]` so reports can state which mode produced them.
- New finding `tags_require_interaction` (medium): tags that only fire after interaction.

**Done when:** an interactive re-crawl of a WP Rocket-delayed site shows GTM `fired` on
every WordPress page. Validate against the reference fixture: `test_interact_status_counts`
must report 20 fired pages.

---

### FIX-03 Consent awareness

**Where:** new `_extract_consent_state(page)` called from `_crawl_page`; findings.

**Changes:**

- Per page, evaluate in the browser:
  - `window.google_tag_data?.ics?.entries` (consent type → `{default, update}`)
  - CMP globals: `Cookiebot?.consent`, `OnetrustActiveGroups`, `__tcfapi` presence
  - Whether the CMP banner element is visible
- Store as `page_info["consent"]`.
- Add config `crawl.consent_action: none | accept | reject` (default `none`); record in
  `crawl_info`.
- New finding `consent_default_granted` (high): `analytics_storage` or `ad_storage`
  is granted before any CMP interaction. Fall back to the container summary (FIX-07)
  when runtime state is unavailable.

**Done when:** `test_container_summary_suppresses_no_event_tracking` passes and asserts
`consent_default_granted`.

---

## P1 — False positives and mislabels

### FIX-04 Google Optimize signature matches any GTM ID

**Where:** `patterns.py` `TAG_PATTERNS['google_optimize']['patterns']`.

**Change:** replace `[r'GTM-[A-Z0-9]{4,}']` with `[r'OPT-[A-Z0-9]{6,}']`. Keep the
`googleoptimize.com/optimize.js` URL pattern. Add `'detection_note': 'Sunset by
Google Sept 2023 — any hit is dead code.'`.

Note: `test_optimize_url_still_detected` is not xfail — it must pass both before and
after this change.

**Done when:** `test_gtm_id_alone_is_not_google_optimize` passes.

---

### FIX-05 Clarity is counted twice

**Where:** `patterns.py` (merge entries); `auditor.py` (alias at detection boundary).

**Changes:**

1. In `patterns.py`, remove the `clarity` entry and update `microsoft_clarity` to
   `category: 'Session Recording'` with both pattern sets merged. Add:

   ```python
   TAG_ALIASES = {"clarity": "microsoft_clarity"}
   ```

   `test_tag_pattern_count` expects 77 — update to 76.

   New crawls cannot produce the `clarity` key: `detect_tags` only writes keys that
   exist in `TAG_PATTERNS`, so removing `clarity` from there is sufficient for new
   crawls. No detection-boundary aliasing is needed.

2. The exposure is **old crawl files** that already have both `clarity` and
   `microsoft_clarity` as separate keys. A category-only alias fallback is not enough —
   both keys would still appear in `tag_index` and trigger a false
   `vendor_redundancy` finding between them.

   Fix: add `canonical_tag_key(name: str) -> str` (uses `TAG_ALIASES`). At the **start**
   of `export_findings`, `export_tag_matrix`, and `format_site_llm`, rename
   `page["tags"]` keys to their canonical form, merging evidence lists when both
   `clarity` and `microsoft_clarity` are present on the same page. Keep the category
   lookup alias as a secondary fallback only.

3. Update `test_two_heatmap_tools`: replace `clarity` (Heatmaps) with
   `microsoft_clarity` (Session Recording). The finding still fires because
   `vendor_redundancy` in `auditor.py` maps both `'Heatmaps'` and `'Session Recording'`
   to the same `'heatmap/session recording'` bucket.

4. Add a test: a page holding both `'clarity'` and `'microsoft_clarity'` in its tags
   produces ONE `tag_index` entry and no `vendor_redundancy` finding between them.

**Done when:** `test_single_clarity_signature` passes and the full suite stays green.

---

### FIX-06 Wappalyzer category ID map is mis-keyed

**Two separate commits.**

**Commit (a) — correct the ID map** in `wappalyzer_adapter.py`:

| ID | Wappalyzer name | currently → | should be |
| --- | --- | --- | --- |
| 22 | Web servers | CDN | Web Server |
| 32 | Marketing automation | Performance Monitoring | Marketing Automation |
| 34 | Databases | Web Server | Database |
| 36 | Advertising | Hosting | Advertising |
| 42 | Tag managers | (unmapped) | Tag Management |
| 47 | Development | CSS Framework | Developer Tools |
| 51 | Page builders | UI Library | CMS |
| 52 | Live chat | JavaScript Library | Customer Support |
| 64 | Reverse proxies | Security | Web Server |
| 66 | UI frameworks | (unmapped) | UI Library |
| 67 | Cookie compliance | Font Service | Consent Management |
| 68 | Accessibility | Error Tracking | Accessibility |
| 74 | A/B Testing | (unmapped) | A/B Testing |
| 75 | Email | E-commerce | Marketing Automation |
| 76 | Personalisation | Performance Monitoring | Personalization |
| 77 | Retargeting | (unmapped) | Advertising |
| 78 | RUM | Security | Performance Monitoring |
| 86 | Segmentation | Headless CMS | Customer Data Platform |
| 87 | WordPress plugins | (unmapped) | CMS Plugin |
| 92 | Performance | E-commerce | Performance |
| 95 | Digital asset management | Performance Monitoring | Digital Asset Management |
| 97 | Customer data platform | (unmapped) | Customer Data Platform |
| fallback | "analytics" substring | Performance Monitoring | Analytics |

Preferred approach: look up the category **name** first via an explicit name→TagScope
dict; keep the ID map only for overrides. Existing `test_wappalyzer_adapter.py` tests
use only IDs 1 and 6, which are already correct and unaffected.

Add a test that every ID in `_CATEGORY_MAP` exists in the pinned
`tests/fixtures/wappalyzer_categories_04faf24.json` and its name matches the expected
mapping. Pinned fixture is included in the zip bundle.

**Commit (b) — dedupe Wappalyzer entries that duplicate TAG_PATTERNS** (separate
commit, separate CHANGELOG entry because `technology_index` output changes):

Drop technologies from `technology_index` whose normalised name matches a `TAG_PATTERNS`
key. This resolves dual-counting where the same tool appears in both the tag index and
the technology index with different page counts. Add a test that no key appearing in
`TAG_PATTERNS` also appears in `technology_index`.

**Done when:** all `test_wappalyzer_category_map[...]` cases pass.

---

### FIX-07 Container-aware, observation-only findings

**Where:** `export_findings` sections `no_event_tracking`, `silent_ga4`, `coverage_gap`;
new `self.gtm_container_summary`; `src/tagscope/gtm_runtime.py` (from the zip bundle).

**Changes:**

1. Add `src/tagscope/gtm_runtime.py` from the zip bundle. It is stdlib-only,
   Python 3.9+, and its tests pass as delivered once the fixtures are in place.

2. In `export_findings`, check `getattr(self, 'gtm_container_summary', None)` — never
   assume the attribute exists (existing tests never set it).

3. `no_event_tracking`:
   - With container summary and `ga4_event_tags` present: emit
     `events_configured_not_observed` (low) listing event names, triggers, and noting
     that the crawl does not submit forms or click CTAs.
   - Without container: rename to `no_events_observed`. Rewrite as an observation:
     "N dataLayer pushes observed; none were GA4 event names. Conversion events may be
     configured in GTM on interactions the crawler did not perform."
   - Count only non-lifecycle pushes. Exclude `gtm.js`, `gtm.dom`, `gtm.load`,
     `gtm.click`, `gtm.linkClick`, `gtm.init*`, CMP consent events, gtag argument
     objects.

4. New container findings (when `gtm_container_summary` present):
   - `consent_default_granted` — from `consent_defaults`
   - `tags_without_consent_requirement` — tags with no GTM additional consent setting
   - `paused_tags` (low)
   - `obfuscated_custom_html` (medium)
   - `container_tag_not_observed` — tags with `fires_on_all_pages` whose vendor was not
     seen on pages where `gtm_executed` is True

5. Write `"gtm_container": {...summary...}` as a top-level key in the findings JSON.

6. **Wording rule for every finding detail:** state the observation, not the diagnosis.
   No "is not configured", "are not being measured", "is non-compliant". Put likely
   causes in a separate `possible_causes` list field.

**Done when:** `test_no_event_tracking_is_observational` and
`test_container_summary_suppresses_no_event_tracking` pass.

---

### FIX-08 Apex → www redirect ends the crawl

**Where:** `SiteAuditor.__init__`, `should_crawl`, `_crawl_page`.

**Change:** add `_adopt_redirect_host(final_url: str)`. After the depth-0 page loads,
if `response.url`'s host differs from `base_domain` only by a leading `www.` (either
direction), set `base_domain` to the final host and log it. Reject any other host.
Call from `_crawl_page` when `depth == 0`.

**Done when:** `test_adopt_www_redirect_host` and `test_adopt_redirect_rejects_foreign_host`
pass.

---

## P2 — Report quality

### FIX-09 Broken links have no source

**Where:** `to_visit`, `_extract_links`, `broken_links` entries.

**Change:** carry the parent URL in `to_visit` as `(url, depth, found_on)`. Have
`_extract_links` keep `{href_raw, text, outer_html[:200]}` per link. Add `found_on`,
`href_raw`, and `link_text` to broken-link entries. Optional: flag links absent from
the initial HTML response as `js_injected: true`.

---

### FIX-10 Non-HTML assets crawled as pages

**Where:** `_default_config` in `cli.py`; `_crawl_page`.

**Pre-check:** on the Codespace HEAD (`4eb50fb`), `.svg` may already be in `cli.py`'s
`skip_extensions` (it is on that branch). On the `17c9d71` baseline it is not — only
`config.yaml` has it. Reconcile so the default config in `cli.py` matches `config.yaml`.
Add any extensions from the plan that are still missing: `.avif`, `.json`, `.xml`,
`.txt`, `.webm`.

Also skip recording responses whose `Content-Type` is not `text/html` in `_crawl_page`.
This catches SVG or JSON files served without a recognised extension.

Once the default list is correct, remove the `@_todo("FIX-10")` marker from
`test_svg_assets_not_crawled` — it requires no other code change.

---

### FIX-11 Tag-count vs load-time correlation is confounded

**Where:** `export_findings` → `tag_performance_correlation`.

**Changes:**

- Require ≥5 pages per compared group. (The reference passive fixture has groups of
  2 vs 2 — below threshold, finding is correctly suppressed.)
- Only compare pages sharing the same CMS/technology profile.
- Prefer Spearman rank correlation over all eligible pages.
- Skip the finding when FIX-01 shows tag execution was deferred.
- Word as a correlation, not a cause.

**Existing test to update:** `test_tag_performance_correlation` at
[tests/test_findings.py:157](../tests/test_findings.py) uses groups of 3 and 2 pages.
Any minimum > 2 breaks it. Rewrite to use **5 vs 5 pages** and add a negative test
(2 vs 2 → finding not emitted).

**Done when:** `test_perf_correlation_requires_group_size` passes and the rewritten
`test_tag_performance_correlation` passes.

---

### FIX-12 Vendor coverage and first-party hosts

- Add tag patterns:
  - `zoominfo` (`js.zi-scripts.com`, `ws.zoominfo.com`; B2B Visitor Identification)
  - `capterra` (`tr.capterra.com`, `ct.capterra.com`; Advertising)
  - `ethicalads` (`server.ethicalads.io`; Advertising)
  - `vimeo` (Video, non-tracking)
- Treat hosts sharing the site's registrable domain (`get.`, `api.`, `cdn-.`, etc.) as
  first-party in the unidentified-hosts inventory. Use a small multi-label suffix list
  (`co.uk`, `com.au` …) without adding an external dependency.

---

### FIX-13 `/audit-report` skill guardrails

**Where:** `.claude/skills/audit-report/SKILL.md` — insert the block below before the
"Report Structure" section.

```markdown
### Evidence rules (mandatory)

1. **Declared ≠ fired.** Treat a tag as present only where `status == "fired"` (or, for
   pre-3.6 JSON, where evidence includes `request_host`/`request_url`). If findings
   include `declared_not_executed` or any page has `script_deferral.deferred == true`,
   the Executive Summary must lead with that, and every coverage statement must say
   "not observed" rather than "missing" or "not firing".
2. **Never infer GTM configuration from page observations.** Only describe what a
   container contains when `gtm_container` is present in findings. Never recommend
   "add a tag" or "configure X in GTM" without it.
3. **Low-confidence detections cannot headline.** A tag whose only evidence is
   `html_pattern` may appear in the inventory table, not in the summary or
   recommendations.
4. **Observed / Possible cause / How to verify.** Each tier-3 finding uses those three
   parts. "Possible cause" is hedged; "How to verify" names a concrete check.
5. **Correlation language only** for performance findings.
6. **Different app, not a gap.** Pages with zero tags AND a different technology profile
   are reported as separate applications, not coverage or consent gaps.
7. **State the crawl mode.** Report `crawl_info.interaction_mode` and
   `crawl_info.consent_action` in the Executive Summary.
8. **No external facts without data.** Don't add vendor history unless the pattern
   carries a `detection_note`.
```

---

## Files from the zip bundle to add to the repo

All of these are additive — nothing existing is overwritten:

| Path | Action |
| --- | --- |
| `src/tagscope/gtm_runtime.py` | Add (used by FIX-07) |
| `tests/test_gtm_runtime.py` | Add (9 passing tests, ground truth for GTM container decoding) |
| `tests/test_crawl_regression.py` | Add (**rename** the zip bundle's regression test file on extraction) |
| `tests/fixtures/reference_site/*` | Add (**rename** the zip bundle's fixtures directory on extraction) |
| `tests/fixtures/wappalyzer_categories_04faf24.json` | Add (pinned fixture for FIX-06) |
| `scripts/trim_crawl_fixture.py` | Add (utility for creating fixtures from future crawls) |

Add these first, before any fix implementation. Run `pytest -q` to confirm the 9 gtm_runtime
tests pass and all regression tests are xfail with no unexpected failures.
