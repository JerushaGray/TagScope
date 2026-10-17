# Site Audit Report: www.checkfront.com

**Crawled:** October 15, 2026 · **Pages:** 149 · **TagScope v3.5.0**

---

## 1. Executive Summary

TagScope crawled 149 pages of `www.checkfront.com`, detecting 12 unique marketing tags and 40 technologies. The site is built on WordPress with a well-established marketing stack anchored by Google Tag Manager, but suffers from a critical split-deployment pattern: the full advertising and analytics suite (GA4, Google Ads, Facebook Pixel, LinkedIn Insight) fires on only 2 of 149 pages — the `/pricing` and `/plans` pages — leaving the entire marketing funnel dark to conversion measurement. GA4 is present but no named events are tracked anywhere on the site, and the two A/B testing tools (Google Optimize and VWO) run in parallel across 147 pages, creating measurement conflict and unnecessary load.

---

## 2. Tag Inventory

### Tag Management

| Tag | Category | Pages | Coverage | Confidence | IDs |
|---|---|---|---|---|---|
| **Google Tag Manager** | Tag Management | 147/149 | 98.7% | High | GTM-P6TLSZF |

### Analytics & Optimization

| Tag | Category | Pages | Coverage | Confidence | IDs |
|---|---|---|---|---|---|
| **Google Analytics 4** | Analytics | 2/149 | 1.3% | High | G-SQ4Z7H3P33 |
| **Google Optimize** | A/B Testing | 147/149 | 98.7% | Low | GTM-P6TLSZF |
| **VWO** | A/B Testing | 147/149 | 98.7% | High | — |

### Advertising ⚠️

| Tag | Category | Pages | Coverage | Confidence | IDs |
|---|---|---|---|---|---|
| **Facebook Pixel** | Advertising | 2/149 | 1.3% | High | 838153926237180 |
| **Google Ads** | Advertising | 2/149 | 1.3% | Low | AW-1029841353 |
| **LinkedIn Insight** | Advertising | 2/149 | 1.3% | High | — |

> **Advertising note:** All three advertising tags share data with third-party platforms (Meta, Google, LinkedIn). They are currently restricted to `/pricing` and `/plans`, limiting retargeting audience size.

### Consent & Compliance

| Tag | Category | Pages | Coverage | Confidence | IDs |
|---|---|---|---|---|---|
| **Cookiebot** | Consent Management | 147/149 | 98.7% | High | — |

### Marketing & Support

| Tag | Category | Pages | Coverage | Confidence | IDs |
|---|---|---|---|---|---|
| **HubSpot** | Marketing Automation | 147/149 | 98.7% | High | — |
| **Crazy Egg** | Heatmaps | 147/149 | 98.7% | High | — |
| **HubSpot Conversations** | Customer Support | 2/149 | 1.3% | High | — |
| **Zendesk** | Customer Support | 1/149 | 0.7% | High | — |

**Coverage gaps flagged:**
- GA4, Google Ads, Facebook Pixel, LinkedIn Insight, and HubSpot Conversations each appear on only 2/149 pages (1.3%).
- Zendesk appears on 1/149 pages (0.7%) — isolated to the `/company/contact` page.
- GTM, Cookiebot, HubSpot, Crazy Egg, Google Optimize, and VWO are absent from `/login` and `/support/developers`.

**Vendor redundancy:** **Google Optimize** and **VWO** are both active across 147 pages. Running two A/B testing platforms simultaneously creates conflicting experiment data, doubles the network overhead for every page load, and expands the third-party data-sharing surface unnecessarily.

---

## 3. Technology Stack

### Core Platform

| Technology | Category | Pages | Coverage | Confidence |
|---|---|---|---|---|
| **WordPress** | CMS | 147/149 | 98.7% | Medium |
| **WP Rocket** | Performance | 145/149 | 97.3% | High |
| **EWWW Image Optimizer** | Image Optimization | 147/149 | 98.7% | Medium |
| **jQuery Migrate** | JavaScript Library | 147/149 | 98.7% | Medium |
| **Max Mega Menu** | Navigation | 147/149 | 98.7% | Medium |
| **HTTP/3** | Protocol | 149/149 | 100% | High |

### UI & Frontend

| Technology | Category | Pages | Coverage | Confidence |
|---|---|---|---|---|
| **Font Awesome** | UI Library | 148/149 | 99.3% | Medium |
| **Google Fonts** | Font Service | 147/149 | 98.7% | Medium |
| **Magnific Popup** | JavaScript Library | 26/149 | 17.4% | Medium |
| **Popper** | JavaScript Library | 14/149 | 9.4% | Medium |
| **GSAP** | Animation Library | 2/149 | 1.3% | Medium |
| **Material UI** | CSS Framework | 2/149 | 1.3% | Medium |
| **Onsen UI** | JavaScript Framework | 2/149 | 1.3% | Medium |
| **Angular** | JavaScript Framework | 1/149 | 0.7% | Medium |

### Security & Infrastructure

| Technology | Category | Pages | Coverage | Confidence |
|---|---|---|---|---|
| **reCAPTCHA** | Security | 147/149 | 98.7% | Medium |
| **Cloudflare** | CDN | 3/149 | 2.0% | High |
| **Google Cloud CDN** | CDN | 1/149 | 0.7% | High |
| **OpenResty** | CDN/Server | 1/149 | 0.7% | High |

### Third-Party Services (Spot-detected)

| Technology | Category | Pages | Coverage |
|---|---|---|---|
| **Snowplow Analytics** | Analytics | 18/149 | 12.1% |
| **Doubleclick Floodlight** | Advertising | 12/149 | 8.1% |
| **HubSpot Chat** | Support | 35/149 | 23.5% |
| **Zendesk** | Support | 3/149 | 2.0% |
| **Joomla** | CMS | 1/149 | 0.7% |
| **JazzHR** | HR | 1/149 | 0.7% |
| **Trustpilot** | Reviews | 1/149 | 0.7% |
| **Twitter** | Social | 1/149 | 0.7% |
| **SemRush** | SEO | 1/149 | 0.7% |
| **EthicalAds** | Advertising | 1/149 | 0.7% |
| **Indeed** | HR | 1/149 | 0.7% |

**Notes:**
- WordPress is the confirmed CMS, detected consistently across 147/149 pages. The 2 exceptions (`/login`, `/support/developers`) appear to be non-WordPress applications.
- **Joomla** detected on 1 page only — likely a reference in page content (the `/integrations/joomla` page), not an actual Joomla installation.
- **Snowplow Analytics** detected on 18 pages (12.1%) — likely a partial integration or embedded in specific content sections. Not present as a tag in the tag index, suggesting it may be firing through GTM or via an embedded third-party widget.
- **HubSpot Chat** detected on 35 pages but **HubSpot Conversations** (the tag variant) fires on only 2. These are related but distinct detections — worth reconciling.

---

## 4. GA4 & DataLayer Analysis

**Measurement ID:** G-SQ4Z7H3P33 (single ID, no conflicts)

**GA4 collect events observed:**

| Event | Count | Type |
|---|---|---|
| page_view | 2 | GA4 standard |

**gtag() commands observed:**

| Command | Target | Notes |
|---|---|---|
| `set` | `developer_id.dMWZhNz` | HubSpot developer ID |
| `set` | `developer_id.dZTQ1Zm` | Secondary developer ID |
| `config` | `AW-1029841353` | Google Ads conversion ID |
| `js` | timestamp | Standard gtag init |

**DataLayer activity:**
- 16 total `dataLayer.push()` calls recorded across all pages
- 0 named GA4 events surfaced from these pushes
- No ecommerce events detected

**Findings:**
- **Silent GA4 on 147 pages:** GA4 (G-SQ4Z7H3P33) is only present on `/pricing` and `/plans`. The remaining 147 pages load GTM (GTM-P6TLSZF) but GA4 is not firing through it — or is not configured within the container. `page_view` events recorded on only 2 pages means session and traffic data is effectively blind across the entire marketing site.
- **No event tracking:** Despite 16 dataLayer pushes site-wide, no named GA4 events (form submissions, CTA clicks, demo requests, sign-ups) are being captured. Conversion measurement is absent.
- **Google Ads configured but not tracking:** `AW-1029841353` is initialized via `gtag config`, but without GA4 event tracking or Ads conversion tags firing across the funnel, attribution data will be incomplete.

---

## 5. Third-Party Vendor Inventory

**Total matched requests:** 4,313  
**Unidentified third-party hosts:** 12

**Identified vendor domains (by purpose):**

| Purpose | Vendors |
|---|---|
| Tag Management | googletagmanager.com |
| Analytics | google-analytics.com |
| Advertising | connect.facebook.net, facebook.com, px.ads.linkedin.com, snap.licdn.com, doubleclick.net |
| A/B Testing | dev.visualwebsiteoptimizer.com |
| Consent | consent.cookiebot.com, consentcdn.cookiebot.com |
| Marketing Automation | js.hs-scripts.com, js.hubspot.com |
| Heatmaps | script.crazyegg.com |
| Support | static.zdassets.com, js.usemessages.com |
| Fonts | fonts.googleapis.com |

**Unidentified hosts (flagged):**

| Host | Requests | Notes |
|---|---|---|
| player.vimeo.com | 52 | Video embeds — likely content, not tracking |
| get.checkfront.com | 35 | First-party subdomain — booking widget |
| api.checkfront.com | 17 | First-party API calls |
| tr.capterra.com | 6 | Capterra review/tracking pixel |
| consentcdn.cookiebot.com | 4 | Cookiebot CDN — first-party consent vendor |
| media.ethicalads.io | 4 | Ad network (developer-targeted ads) |
| csp.withgoogle.com | 3 | Google CSP reporting endpoint |
| checkfront-legacy.zendesk.com | 2 | Legacy Zendesk subdomain |
| api.hubapi.com | 2 | HubSpot API |
| server.ethicalads.io | 2 | EthicalAds server |
| ekr.zdassets.com | 1 | Zendesk assets |
| cdn-production.checkfront.com | 1 | First-party CDN |

Most "unidentified" hosts are either first-party Checkfront subdomains or recognized third-party services. `tr.capterra.com` and `media.ethicalads.io` represent additional advertising/tracking pixels not captured in the tag inventory.

---

## 6. Site Health

**Broken links:** 1  
**Failed pages:** 1 (out of 150 attempted)

**Load time summary:**
- Average load time: 2,871ms
- Slow pages (>1.5× average, i.e., >4,307ms): **13 pages**
- Slowest page: `/plans` — 8,086ms
- Second slowest: `/pricing` — 7,576ms

Note: `/pricing` and `/plans` are also the only pages with the full advertising tag stack (11 tags vs. 6 on all other pages). The load time correlation is direct — see findings below.

**Metadata issues:**
- 2 pages missing meta descriptions: `/login`, `/support/developers`
- 10 pages share duplicate titles across 5 title strings; most repeated: "Online Booking Software for Tours & Activities | Checkfront" (2 pages)

**Internal linking:**
- 50 pages have 1 or fewer internal links, limiting crawlability and SEO equity distribution. Affected pages include blog posts, landing pages (`/maximize-your-resources`, `/company`), and integration pages.

**Crawl depth distribution:** Max depth reached: 3. The 150-page cap was reached with 113+ URLs still in queue, indicating a larger site.

---

## 7. Findings & Recommendations

### 1. GA4 Not Firing on 147 of 149 Pages
**Finding:** Google Analytics 4 (G-SQ4Z7H3P33) is detected on only `/pricing` and `/plans`. The GTM container (GTM-P6TLSZF) loads across 147 pages but GA4 is not configured within it, or the GA4 tag within GTM is blocked by a trigger condition.

**Risk:** Near-total loss of web analytics data. Traffic, behaviour, and attribution across the marketing site (blog, features, integrations, industries pages) is not measured. Decisions about content and paid media cannot be grounded in data.

**Recommendation:** Audit the GTM container. Add a GA4 configuration tag with an "All Pages" trigger. Verify that GA4 `page_view` fires on every page except explicitly excluded paths (e.g., `/login`).

**Priority:** High

---

### 2. Zero Conversion Event Tracking
**Finding:** 16 dataLayer pushes are recorded site-wide but 0 named GA4 events are captured. No form submissions, demo requests, CTA clicks, or sign-up events are being measured.

**Risk:** Paid campaigns (Google Ads AW-1029841353, Facebook Pixel 838153926237180, LinkedIn) have no conversion signal to optimize against. ROAS cannot be measured. Funnel analysis is impossible.

**Recommendation:** Define a conversion event taxonomy (at minimum: `generate_lead` for demo requests, `sign_up`, `begin_checkout`). Implement GA4 event tags in GTM with appropriate triggers. Pass conversion events to Google Ads via linked GA4 goals or a dedicated Ads Conversion tag.

**Priority:** High

---

### 3. Advertising Tags Confined to 2 Pages
**Finding:** Facebook Pixel (838153926237180), Google Ads (AW-1029841353), and LinkedIn Insight Tag fire only on `/pricing` and `/plans`.

**Risk:** Retargeting audiences built from these tags represent only visitors who reached the pricing page — a small fraction of total site traffic. Users who read blog content, viewed features pages, or visited industry pages are excluded from all retargeting pools.

**Recommendation:** Extend advertising tags sitewide through GTM. Segment audiences by page category (e.g., blog readers vs. features viewers vs. pricing visitors) using custom events or URL-based audience rules rather than restricting tag deployment.

**Priority:** High

---

### 4. Dual A/B Testing Tools (Google Optimize + VWO)
**Finding:** Both **Google Optimize** and **VWO** are active on 147 pages.

**Risk:** Running two experimentation platforms simultaneously introduces flicker risk (both tools modify the DOM before render), creates conflicting experiment attribution, increases page load time on every page, and doubles the privacy exposure from A/B testing vendors.

**Recommendation:** Consolidate to one platform. Evaluate which tool is actively running experiments. If Google Optimize is the primary tool, remove VWO. Note that Google Optimize was sunset in September 2023 — if it is still loading, the tag should be removed entirely and replaced with an alternative (VWO, Optimizely, or GA4 Experiments).

**Priority:** Medium

---

### 5. Consent Gap on `/login` and `/support/developers`
**Finding:** Cookiebot (consent management), GTM, HubSpot, Crazy Egg, and VWO are all absent from `/login` and `/support/developers`. These pages have zero tags.

**Risk:** If users navigate directly to these URLs, no consent mechanism loads. Depending on jurisdiction (GDPR, CCPA), loading tags on subsequent pages without consent obtained on the entry point may be non-compliant. The absence of all tags on these pages also means authenticated users are invisible to analytics entirely.

**Recommendation:** Ensure Cookiebot loads on all pages, including `/login` and utility pages. Confirm whether analytics tags should fire for authenticated users and implement accordingly.

**Priority:** Medium

---

### 6. 13 Slow Pages — Tag Load Correlation Confirmed
**Finding:** 13 pages load more than 1.5× the site average (2,871ms). The two slowest pages — `/plans` (8,086ms) and `/pricing` (7,576ms) — are exactly the two pages carrying 11 tags (vs. 6 on all other pages). Pages with 11 tags average 7,831ms; pages with 0 tags average 711ms — a **1,001% difference**.

**Risk:** Slow pricing pages directly impact conversion rates. Users are most likely to abandon at the moment of highest purchase intent.

**Recommendation:** Audit tag firing on `/pricing` and `/plans`. Consider loading advertising pixels asynchronously or post-interaction. Use GTM's tag sequencing and timeout settings to prevent tag loading from blocking page render.

**Priority:** Medium

---

### 7. Capterra Tracking Pixel Unaccounted For
**Finding:** `tr.capterra.com` received 6 requests across the crawl. This is a review platform tracking pixel not listed in the tag inventory.

**Risk:** A tracking pixel sending data to a third party without explicit documentation may not be covered by the privacy policy or disclosed to users via the cookie consent banner.

**Recommendation:** Identify where the Capterra pixel is loaded (likely through GTM or hardcoded on select pages). Ensure it is categorized in Cookiebot's consent configuration and disclosed in the cookie policy.

**Priority:** Medium

---

### 8. 50 Dead-End Pages
**Finding:** 50 pages have 1 or fewer internal links, including blog posts, landing pages, and integration pages.

**Risk:** Pages with no outbound internal links limit SEO crawlability, reduce time-on-site metrics, and fail to move users through the conversion funnel.

**Recommendation:** Audit dead-end blog posts and landing pages. Add relevant CTAs or related content links. Pages like `/maximize-your-resources` and `/company` should link to product or pricing pages.

**Priority:** Low

---

### 9. Duplicate Page Titles (10 Pages)
**Finding:** 10 pages share duplicate `<title>` tags across 5 title strings.

**Risk:** Duplicate titles reduce SEO differentiation and make it harder for search engines to distinguish page intent.

**Recommendation:** Audit the 10 affected pages and assign unique, keyword-targeted titles. The WordPress SEO plugin (Yoast/RankMath) can automate this for post archives and pagination.

**Priority:** Low

---

*Report generated by TagScope v3.5.0 · www.checkfront.com · October 15, 2026*
