"""Core crawler and site auditor engine."""

import asyncio
import json
import csv
import re
import logging
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs, unquote_plus
from datetime import datetime
from collections import defaultdict
from typing import Set, Dict, List, Optional, Tuple

from playwright.async_api import (
    async_playwright, Page, Browser,
    TimeoutError as PlaywrightTimeout,
)

from tagscope.patterns import (
    TAG_PATTERNS, GA4_EVENTS, TECHNOLOGY_PATTERNS,
    CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW,
)


def _extract_host(url_fragment: str) -> str:
    """Extract the host from a URL or URL fragment.

    Handles full URLs (https://example.com/path) and bare fragments
    (example.com/path) that appear in TAG_PATTERNS/TECHNOLOGY_PATTERNS urls lists.
    """
    if '://' in url_fragment:
        return urlparse(url_fragment).netloc
    # Bare fragment like 'px.ads.linkedin.com/collect' -- take before first '/'
    return url_fragment.split('/')[0]


class CrawlState:
    """Manages crawl state for resume capability."""

    def __init__(self, state_file: str):
        self.state_file = state_file
        self.state = self.load_state()

    def load_state(self) -> Dict:
        """Load saved crawl state."""
        if Path(self.state_file).exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"Could not load state file: {e}")
        return {
            'visited_urls': [],
            'to_visit': [],
            'page_data': [],
            'broken_links': []
        }

    def save_state(self, visited: Set[str], to_visit: List[Tuple],
                   page_data: List[Dict], broken_links: List[Dict]):
        """Save current crawl state."""
        try:
            state = {
                'visited_urls': list(visited),
                'to_visit': to_visit,
                'page_data': page_data,
                'broken_links': broken_links,
                'last_saved': datetime.now().isoformat()
            }
            state_path = Path(self.state_file)
            with open(state_path, 'w') as f:
                json.dump(state, f, indent=2, default=str)
            logging.debug(f"Saved crawl state to {self.state_file}")
        except Exception as e:
            logging.error(f"Could not save state: {e}")


class SiteAuditor:
    """Playwright-powered web crawler with comprehensive tag and technology detection."""

    def __init__(self, config: Dict, extended_tech_patterns: Optional[Dict] = None):
        self.config = config
        self._tech_patterns = extended_tech_patterns or TECHNOLOGY_PATTERNS
        self.start_url = config['start_url']
        self.base_domain = urlparse(self.start_url).netloc

        # Crawl settings
        self.max_pages = max(1, config['crawl']['max_pages'])
        self.max_depth = max(0, config['crawl']['max_depth'])
        self.rate_limit = max(0.1, config['crawl']['rate_limit'])

        concurrent = config['crawl'].get('concurrent_pages', 3)
        if not isinstance(concurrent, int) or concurrent < 1:
            logging.warning(f"Invalid concurrent_pages: {concurrent}, using default 3")
            concurrent = 3
        self.concurrent_pages = min(concurrent, 10)

        self.timeout = config['crawl']['timeout'] * 1000  # Convert to ms

        # State management
        self.visited_urls: Set[str] = set()
        self.to_visit: List[Tuple[str, int]] = [(self.start_url, 0)]
        self.page_data: List[Dict] = []
        self.broken_links: List[Dict] = []
        self.network_requests: Dict[str, List] = defaultdict(list)

        # Resume capability with domain-specific state files
        if config['resume']['enabled']:
            domain_safe = self.base_domain.replace('.', '_').replace(':', '_')
            output_dir = Path(config['output']['prefix']).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            state_file = str(output_dir / f"crawl_state_{domain_safe}.json")
            self.state = CrawlState(state_file)
            self._load_previous_state()
        else:
            self.state = None

        # Statistics
        self.stats = {
            'pages_crawled': 0,
            'pages_failed': 0,
            'tags_found': defaultdict(int),
            'technologies_found': defaultdict(int)
        }

        # Memory management
        self.output_prefix = config['output']['prefix']
        self.memory_threshold = 50  # Flush to disk every 50 pages

        self._setup_logging()

    def _setup_logging(self):
        """Configure logging with safe paths."""
        log_config = self.config['logging']
        log_level = getattr(logging, log_config['level'].upper())

        handlers = []

        if log_config['console']:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            )
            handlers.append(console_handler)

        if log_config['log_file']:
            log_dir = Path.home() / '.tagscope'
            log_dir.mkdir(exist_ok=True)
            log_path = log_dir / log_config['log_file']

            try:
                file_handler = logging.FileHandler(log_path)
                file_handler.setFormatter(
                    logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
                )
                handlers.append(file_handler)
                print(f"Log file: {log_path}")
            except Exception as e:
                print(f"Could not create log file: {e}")

        logging.basicConfig(
            level=log_level,
            handlers=handlers,
            force=True
        )

    def _load_previous_state(self):
        """Load previous crawl state for resume."""
        if self.state and self.state.state:
            visited = self.state.state.get('visited_urls', [])
            if not visited:
                return

            self.visited_urls = set(visited)
            self.to_visit = self.state.state.get('to_visit', [(self.start_url, 0)])
            self.page_data = self.state.state.get('page_data', [])
            self.broken_links = self.state.state.get('broken_links', [])

            logging.info(f"Resuming crawl: {len(self.visited_urls)} pages already visited")

    def save_progress(self):
        """Save crawl progress."""
        if self.state and self.config['output']['save_progress']:
            self.state.save_state(
                self.visited_urls,
                self.to_visit,
                self.page_data,
                self.broken_links
            )

    def _flush_to_disk(self):
        """Periodically flush data to disk to manage memory."""
        if len(self.page_data) >= self.memory_threshold:
            temp_file = Path(f'{self.output_prefix}_partial.json')
            try:
                existing_data = []
                if temp_file.exists():
                    with open(temp_file, 'r') as f:
                        existing_data = json.load(f)

                existing_data.extend(self.page_data)

                with open(temp_file, 'w') as f:
                    json.dump(existing_data, f, indent=2)

                logging.info(f"Flushed {len(self.page_data)} pages to disk")
                self.page_data = []
            except Exception as e:
                logging.error(f"Could not flush to disk: {e}")

    def _load_partial_data(self):
        """Load partial data back from disk."""
        temp_file = Path(f'{self.output_prefix}_partial.json')
        if temp_file.exists():
            try:
                with open(temp_file, 'r') as f:
                    partial_data = json.load(f)
                self.page_data.extend(partial_data)
                temp_file.unlink()
                logging.info(f"Loaded {len(partial_data)} pages from partial file")
            except Exception as e:
                logging.error(f"Could not load partial data: {e}")

    def should_crawl(self, url: str) -> bool:
        """Check if URL should be crawled."""
        parsed = urlparse(url)

        if parsed.netloc != self.base_domain:
            return False

        for pattern in self.config['filters']['exclude_patterns']:
            if re.search(pattern, url):
                return False

        if self.config['filters']['include_patterns']:
            matched = False
            for pattern in self.config['filters']['include_patterns']:
                if re.search(pattern, url):
                    matched = True
                    break
            if not matched:
                return False

        skip_extensions = self.config['filters']['skip_extensions']
        if any(url.lower().endswith(ext) for ext in skip_extensions):
            return False

        return True

    def normalize_url(self, url: str) -> str:
        """Normalize URL."""
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        if normalized.endswith('/') and parsed.path != '/':
            normalized = normalized[:-1]
        return normalized

    async def _extract_links(self, page: Page, current_url: str) -> Tuple[List[str], List[Dict]]:
        """Extract internal links and identify broken links."""
        internal_links = []
        broken_links = []

        try:
            links_data = await page.eval_on_selector_all(
                'a[href]',
                """elements => elements.map(el => ({
                    href: el.href,
                    text: el.textContent.trim(),
                    title: el.title
                }))"""
            )

            for link_data in links_data:
                href = link_data['href']

                if not href or any(href.startswith(x) for x in ['javascript:', 'mailto:', 'tel:', '#']):
                    continue

                absolute_url = urljoin(current_url, href)
                normalized = self.normalize_url(absolute_url)

                if urlparse(normalized).netloc == self.base_domain:
                    if self.should_crawl(normalized) and normalized not in self.visited_urls:
                        internal_links.append(normalized)

            return list(set(internal_links)), broken_links

        except Exception as e:
            logging.error(f"Error extracting links from {current_url}: {e}")
            return [], []

    def detect_tags(self, page_content: str, page_url: str,
                    network_requests: Optional[List[Dict]] = None) -> Dict:
        """Detect tracking tags from HTML content and network requests."""
        detected_tags = {}

        for tag_name, tag_config in TAG_PATTERNS.items():
            matches = []
            evidence = []

            for pattern in tag_config['patterns']:
                found_matches = re.findall(pattern, page_content)
                if found_matches:
                    matches.extend(found_matches)
                    evidence.append(f"html_pattern:{pattern}")

            for url_pattern in tag_config['urls']:
                if url_pattern in page_content:
                    evidence.append(f"script_url:{url_pattern}")

            if network_requests:
                for url_pattern in tag_config['urls']:
                    pattern_host = _extract_host(url_pattern)
                    for req in network_requests:
                        req_host = urlparse(req['url']).netloc
                        if pattern_host and pattern_host in req_host:
                            evidence.append(f"request_host:{req_host}")
                        elif url_pattern in req['url']:
                            evidence.append(f"request_url:{url_pattern}")

            if evidence or matches:
                evidence = list(dict.fromkeys(evidence))  # dedupe, preserve order
                has_network = any(e.startswith('request_') for e in evidence)
                has_script = any(e.startswith('script_url:') for e in evidence)
                if has_network:
                    confidence = CONFIDENCE_HIGH
                elif has_script:
                    confidence = CONFIDENCE_MEDIUM
                else:
                    confidence = CONFIDENCE_MEDIUM

                detected_tags[tag_name] = {
                    'found': True,
                    'ids': list(set(matches)) if matches else [],
                    'category': tag_config['category'],
                    'evidence': evidence,
                    'confidence': confidence,
                }
                self.stats['tags_found'][tag_name] += 1

        return detected_tags

    def detect_technologies(self, page_content: str, meta_tags: List,
                            headers: Dict,
                            network_requests: Optional[List[Dict]] = None) -> List[Dict]:
        """Detect technologies from HTML, meta tags, headers, and network requests."""
        technologies = []

        for tech_name, tech_config in self._tech_patterns.items():
            evidence = []

            for pattern in tech_config['patterns']:
                # Support both compiled patterns and raw strings
                if hasattr(pattern, 'search'):
                    match = pattern.search(page_content)
                else:
                    match = re.search(pattern, page_content, re.IGNORECASE)
                if match:
                    pat_str = pattern.pattern if hasattr(pattern, 'pattern') else pattern
                    evidence.append(f"html_pattern:{pat_str}")
                    break

            if 'meta' in tech_config:
                for meta_name, meta_pattern in tech_config['meta']:
                    for meta in meta_tags:
                        if meta.get('name') == meta_name:
                            content = meta.get('content', '')
                            if hasattr(meta_pattern, 'search'):
                                matched = meta_pattern.search(content)
                            else:
                                matched = re.search(meta_pattern, content)
                            if matched:
                                evidence.append(f"meta:{meta_name}")

            if 'headers' in tech_config:
                for header_name, header_pattern in tech_config['headers']:
                    header_val = headers.get(header_name, '')
                    if header_val:
                        if hasattr(header_pattern, 'search'):
                            matched = header_pattern.search(header_val)
                        else:
                            matched = re.search(header_pattern, header_val, re.IGNORECASE)
                        if matched:
                            evidence.append(f"header:{header_name}")

            if network_requests and 'urls' in tech_config:
                for url_pattern in tech_config['urls']:
                    pattern_host = _extract_host(url_pattern)
                    for req in network_requests:
                        req_host = urlparse(req['url']).netloc
                        if pattern_host and pattern_host in req_host:
                            evidence.append(f"request_host:{req_host}")
                            break
                    else:
                        continue
                    break

            if evidence:
                evidence = list(dict.fromkeys(evidence))
                has_network = any(e.startswith('request_host:') for e in evidence)
                has_header = any(e.startswith('header:') for e in evidence)
                has_meta = any(e.startswith('meta:') for e in evidence)
                if has_network or has_header or has_meta:
                    confidence = CONFIDENCE_HIGH
                else:
                    confidence = CONFIDENCE_MEDIUM

                tech_entry = {
                    'name': tech_name,
                    'category': tech_config['category'],
                    'evidence': evidence,
                    'confidence': confidence,
                }
                if 'detection_note' in tech_config:
                    tech_entry['detection_note'] = tech_config['detection_note']
                technologies.append(tech_entry)
                self.stats['technologies_found'][tech_name] += 1

        return technologies

    async def _detect_tags_from_page(self, page: Page,
                                    network_requests: Optional[List[Dict]] = None) -> Dict:
        """Extract script content from a page and detect tags."""
        try:
            scripts = await page.eval_on_selector_all(
                'script',
                'elements => elements.map(el => el.innerHTML + " " + (el.src || ""))'
            )

            page_content = ' '.join(scripts)
            return self.detect_tags(page_content, page.url, network_requests)

        except Exception as e:
            logging.error(f"Error detecting tags: {e}")
            return {}

    @staticmethod
    def _is_gtag_arguments_object(item: Dict) -> bool:
        """Check if a dataLayer item is a gtag() arguments object.

        gtag() calls serialize into dataLayer as their raw arguments object,
        e.g. gtag('config','G-XXX') becomes {"0":"config","1":"G-XXX"}.
        GTM may inject extra keys like gtm.uniqueEventId alongside the numeric
        positional args, so we gate on the presence of key "0" rather than
        requiring all keys to be numeric.
        """
        if 'event' in item:
            return False
        return '0' in item

    def _parse_datalayer(self, datalayer: List[Dict]) -> Dict:
        """Parse and analyze dataLayer events, including gtag() argument objects."""
        parsed = {
            'total_events': len(datalayer),
            'events': [],
            'ga4_events': defaultdict(int),
            'ecommerce_events': [],
            'custom_events': [],
            'gtag_config': [],
        }

        _GTAG_CONFIG_COMMANDS = {'js', 'config', 'set', 'consent', 'get'}

        for item in datalayer:
            if not isinstance(item, dict):
                continue

            # Handle gtag() arguments objects (keys are all numeric strings)
            if self._is_gtag_arguments_object(item):
                command = item.get('0', '')
                if command == 'event':
                    event_name = item.get('1', 'unknown')
                    params = item.get('2', {})
                    if not isinstance(params, dict):
                        params = {}
                    event_info = {
                        'event': event_name,
                        'data': {'event': event_name, **params},
                        'source': 'gtag_arguments',
                    }
                    if event_name in GA4_EVENTS:
                        parsed['ga4_events'][GA4_EVENTS[event_name]] += 1
                        event_info['type'] = 'ga4'
                        event_info['description'] = GA4_EVENTS[event_name]
                    else:
                        parsed['custom_events'].append(event_name)
                        event_info['type'] = 'custom'
                    parsed['events'].append(event_info)
                elif command in _GTAG_CONFIG_COMMANDS:
                    parsed['gtag_config'].append({
                        'command': command,
                        'target': item.get('1', ''),
                        'params': item.get('2', {}),
                    })
                else:
                    # Unknown gtag command -- treat as custom event
                    parsed['custom_events'].append(f"gtag:{command}")
                    parsed['events'].append({
                        'event': f"gtag:{command}",
                        'data': item,
                        'type': 'custom',
                    })
                continue

            # Standard dataLayer.push with an "event" key
            event_name = item.get('event', 'unknown')

            event_info = {
                'event': event_name,
                'data': item
            }

            if event_name in GA4_EVENTS:
                parsed['ga4_events'][GA4_EVENTS[event_name]] += 1
                event_info['type'] = 'ga4'
                event_info['description'] = GA4_EVENTS[event_name]
            elif 'ecommerce' in item:
                parsed['ecommerce_events'].append(event_info)
                event_info['type'] = 'ecommerce'
            else:
                parsed['custom_events'].append(event_name)
                event_info['type'] = 'custom'

            parsed['events'].append(event_info)

        return parsed

    def decode_ga4_collect_requests(self, network_requests: List[Dict]) -> Dict:
        """Decode GA4 Measurement Protocol /g/collect requests.

        Extracts event names, measurement IDs, and event params from
        google-analytics.com/g/collect request URLs and POST bodies.
        Deduplicates retransmissions (_s=1 vs _s=2).
        """
        result = {
            'measurement_ids': [],
            'events': defaultdict(int),
            'event_details': [],
            'raw_request_count': 0,
        }

        seen_keys = set()
        measurement_ids = set()

        for req in network_requests:
            url = req.get('url', '')
            if 'g/collect' not in url:
                continue
            parsed_url = urlparse(url)
            host = parsed_url.netloc
            if 'google-analytics.com' not in host and 'analytics.google.com' not in host:
                continue

            result['raw_request_count'] += 1

            # Parse params from query string
            params = parse_qs(parsed_url.query, keep_blank_values=True)

            # Also parse POST body if present
            post_data = req.get('post_data')
            if post_data and isinstance(post_data, str):
                try:
                    body_params = parse_qs(post_data, keep_blank_values=True)
                    for k, v in body_params.items():
                        if k not in params:
                            params[k] = v
                except Exception:
                    pass

            event_name = params.get('en', [''])[0]
            tid = params.get('tid', [''])[0]
            dl = params.get('dl', [''])[0]

            if not event_name:
                continue

            if tid:
                measurement_ids.add(tid)

            # Deduplicate retransmissions using stable key
            dedup_key = (event_name, tid, dl)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            result['events'][event_name] += 1

            # Extract event params (ep.* keys)
            event_params = {}
            for k, v in params.items():
                if k.startswith('ep.'):
                    event_params[k[3:]] = v[0] if len(v) == 1 else v
                elif k.startswith('epn.'):
                    try:
                        event_params[k[4:]] = float(v[0])
                    except (ValueError, IndexError):
                        event_params[k[4:]] = v[0] if v else ''

            detail = {
                'name': event_name,
                'params': event_params,
                'source': 'collect_request',
            }
            if event_name in GA4_EVENTS:
                detail['description'] = GA4_EVENTS[event_name]
            if tid:
                detail['measurement_id'] = tid
            result['event_details'].append(detail)

        result['measurement_ids'] = sorted(measurement_ids)
        result['events'] = dict(result['events'])
        return result

    async def _extract_datalayer(self, page: Page) -> Dict:
        """Extract and parse dataLayer."""
        try:
            datalayer_raw = await page.evaluate("""() => {
                if (typeof dataLayer !== 'undefined') {
                    return dataLayer;
                }
                if (typeof window.dataLayer !== 'undefined') {
                    return window.dataLayer;
                }
                return [];
            }""")

            if self.config['datalayer']['parse_events']:
                return self._parse_datalayer(datalayer_raw[:self.config['datalayer']['max_events']])
            else:
                return {'raw': datalayer_raw[:self.config['datalayer']['max_events']]}

        except Exception as e:
            logging.error(f"Error extracting dataLayer: {e}")
            return {}

    async def _get_page_metadata(self, page: Page) -> Dict:
        """Extract comprehensive page metadata."""
        try:
            metadata = await page.evaluate("""() => {
                const getMeta = (name) => {
                    const el = document.querySelector(`meta[name="${name}"], meta[property="${name}"]`);
                    return el ? el.content : '';
                };

                return {
                    title: document.title,
                    description: getMeta('description'),
                    keywords: getMeta('keywords'),
                    canonical: document.querySelector('link[rel="canonical"]')?.href || '',
                    og_title: getMeta('og:title'),
                    og_description: getMeta('og:description'),
                    og_image: getMeta('og:image'),
                    h1: Array.from(document.querySelectorAll('h1')).map(h => h.textContent.trim()),
                    h2: Array.from(document.querySelectorAll('h2')).map(h => h.textContent.trim()).slice(0, 5),
                    robots: getMeta('robots'),
                    viewport: getMeta('viewport'),
                    charset: document.characterSet,
                    lang: document.documentElement.lang,
                    meta_tags: Array.from(document.querySelectorAll('meta')).map(m => ({
                        name: m.name || m.property,
                        content: m.content
                    }))
                };
            }""")
            return metadata
        except Exception as e:
            logging.error(f"Error extracting metadata: {e}")
            return {}

    async def _get_performance_metrics(self, page: Page) -> Dict:
        """Capture page performance metrics."""
        try:
            metrics = await page.evaluate("""() => {
                const perfData = performance.getEntriesByType('navigation')[0];
                if (!perfData) return {};

                return {
                    load_time: perfData.loadEventEnd - perfData.fetchStart,
                    dom_content_loaded: perfData.domContentLoadedEventEnd - perfData.fetchStart,
                    first_paint: performance.getEntriesByType('paint')
                        .find(e => e.name === 'first-paint')?.startTime || 0,
                    first_contentful_paint: performance.getEntriesByType('paint')
                        .find(e => e.name === 'first-contentful-paint')?.startTime || 0,
                    transfer_size: perfData.transferSize,
                    dom_interactive: perfData.domInteractive - perfData.fetchStart
                };
            }""")
            return metrics
        except Exception as e:
            logging.error(f"Error capturing performance metrics: {e}")
            return {}

    async def _crawl_page_with_retry(self, browser: Browser, url: str, depth: int) -> Optional[Dict]:
        """Crawl a page with retry logic."""
        retry_config = self.config['retry']

        for attempt in range(retry_config['max_retries'] + 1):
            try:
                result = await self._crawl_page(browser, url, depth)
                if result:
                    self.stats['pages_crawled'] += 1
                    return result
                else:
                    self.stats['pages_failed'] += 1
                    return None

            except PlaywrightTimeout:
                if attempt < retry_config['max_retries']:
                    logging.warning(f"Timeout on {url}, retrying ({attempt + 1}/{retry_config['max_retries']})")
                    await asyncio.sleep(retry_config['retry_delay'])
                else:
                    logging.error(f"Failed after {retry_config['max_retries']} retries: {url}")
                    self.stats['pages_failed'] += 1
                    return None

            except Exception as e:
                if attempt < retry_config['max_retries']:
                    logging.warning(f"Error on {url}: {e}, retrying ({attempt + 1}/{retry_config['max_retries']})")
                    await asyncio.sleep(retry_config['retry_delay'])
                else:
                    logging.error(f"Failed after {retry_config['max_retries']} retries: {url} - {e}")
                    self.stats['pages_failed'] += 1
                    return None

        return None

    async def _crawl_page(self, browser: Browser, url: str, depth: int) -> Optional[Dict]:
        """Crawl a single page."""

        page = await browser.new_page(
            user_agent=self.config['browser']['user_agent'],
            viewport=self.config['browser']['viewport'],
            ignore_https_errors=self.config['browser']['ignore_https_errors']
        )

        network_logs = []
        page_domain = urlparse(url).netloc

        async def log_request(request):
            try:
                req_host = urlparse(request.url).netloc
            except Exception:
                return
            # Capture all third-party requests (not same-origin)
            if req_host and req_host != page_domain:
                post_data = None
                if request.method == 'POST':
                    try:
                        post_data = request.post_data
                    except Exception:
                        pass
                network_logs.append({
                    'url': request.url,
                    'method': request.method,
                    'type': request.resource_type,
                    'post_data': post_data,
                    'timestamp': datetime.now().isoformat()
                })

        page.on('request', log_request)

        try:
            response = await page.goto(
                url,
                wait_until='domcontentloaded',
                timeout=self.timeout
            )

            # Allow extra time for JS-injected tags to fire
            try:
                await page.wait_for_load_state('networkidle', timeout=5000)
            except Exception:
                pass

            if not response:
                await page.close()
                return None

            status = response.status
            resp_headers = {k.lower(): v for k, v in response.headers.items()}

            if status >= 400:
                self.broken_links.append({
                    'url': url,
                    'status': status,
                    'depth': depth
                })
                await page.close()
                return None

            await asyncio.sleep(self.rate_limit)

            metadata = await self._get_page_metadata(page)
            tags = await self._detect_tags_from_page(page, network_logs)
            links, page_broken_links = await self._extract_links(page, url)
            self.broken_links.extend(page_broken_links)

            datalayer = {}
            if self.config['datalayer']['extract']:
                datalayer = await self._extract_datalayer(page)

            ga4_collect_events = self.decode_ga4_collect_requests(network_logs)

            performance = {}
            if self.config['performance']['capture_metrics']:
                performance = await self._get_performance_metrics(page)

            screenshot_path = None
            if self.config['performance']['capture_screenshots']:
                screenshot_dir = Path(self.output_prefix).parent / "screenshots"
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                safe_name = urlparse(url).path.replace('/', '_') or 'index'
                screenshot_path = str(screenshot_dir / f"{safe_name}.{self.config['performance']['screenshot_format']}")
                await page.screenshot(path=screenshot_path)

            html_content = await page.content()

            await page.close()

            technologies = self.detect_technologies(
                html_content,
                metadata.get('meta_tags', []),
                resp_headers,
                network_logs
            )

            page_info = {
                'url': url,
                'depth': depth,
                'status': status,
                'metadata': metadata,
                'tags': tags,
                'datalayer': datalayer,
                'ga4_collect_events': ga4_collect_events,
                'technologies': technologies,
                'performance': performance,
                'network_requests': network_logs,
                'internal_links_found': len(links),
                'screenshot': screenshot_path,
                'crawled_at': datetime.now().isoformat()
            }

            if depth < self.max_depth:
                for link in links:
                    if link not in self.visited_urls and link not in [u[0] for u in self.to_visit]:
                        self.to_visit.append((link, depth + 1))

            return page_info

        except Exception as e:
            logging.error(f"Error crawling {url}: {e}")
            await page.close()
            raise

    def _display_progress(self):
        """Display crawl progress bar."""
        visited = len(self.visited_urls)
        success = self.stats['pages_crawled']
        failed = self.stats['pages_failed']
        remaining = len(self.to_visit)

        progress_bar = "=" * min(50, int(visited / self.max_pages * 50))
        percent = int(visited / self.max_pages * 100) if self.max_pages > 0 else 0

        print(f"\r[{progress_bar:<50}] {percent}% | "
              f"Visited: {visited}/{self.max_pages} | "
              f"Success: {success} | Failed: {failed} | Queue: {remaining}",
              end='', flush=True)

    async def crawl(self):
        """Main crawl loop with concurrent page processing."""
        print(f"\nStarting crawl of {self.start_url}")
        print(f"Settings: {self.max_pages} pages, depth {self.max_depth}, {self.concurrent_pages} concurrent")
        print(f"Rate limit: {self.rate_limit}s per page\n")

        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(
                    headless=self.config['browser']['headless']
                )

                page_counter = 0

                while self.to_visit and len(self.visited_urls) < self.max_pages:
                    batch = []
                    for _ in range(self.concurrent_pages):
                        if self.to_visit and len(self.visited_urls) + len(batch) < self.max_pages:
                            url, depth = self.to_visit.pop(0)
                            if url not in self.visited_urls:
                                batch.append((url, depth))
                                self.visited_urls.add(url)

                    if not batch:
                        break

                    tasks = [self._crawl_page_with_retry(browser, url, depth) for url, depth in batch]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for result in results:
                        if isinstance(result, dict):
                            self.page_data.append(result)
                            page_counter += 1

                            self._display_progress()

                            if page_counter % self.memory_threshold == 0:
                                self._flush_to_disk()

                            if self.config['output']['save_progress'] and \
                               page_counter % self.config['output']['progress_interval'] == 0:
                                self.save_progress()

            finally:
                if browser:
                    await browser.close()

        print("\n")

        self._load_partial_data()

        if self.config['output']['save_progress']:
            self.save_progress()

        print("=" * 80)
        print(f"Crawl complete!")
        print(f"Pages visited: {len(self.visited_urls)}")
        print(f"Success: {self.stats['pages_crawled']}")
        print(f"Failed: {self.stats['pages_failed']}")
        print(f"Broken links: {len(self.broken_links)}")
        print(f"Unique tags: {len(self.stats['tags_found'])}")
        print(f"Technologies: {len(self.stats['technologies_found'])}")

    def _classify_network_requests(self) -> Tuple[List[Dict], Dict[str, int]]:
        """Split network requests into matched (known pattern) and unidentified hosts.

        A host is "known" if it matches a URL fragment from any pattern entry OR
        if its registrable domain appears in any vendor's owned_domains list.
        This prevents subdomains of known vendors (e.g. secure.quantserve.com for
        Quantcast) from polluting the unidentified bucket.

        Returns (matched_requests, unidentified_hosts_counts).
        """
        # Collect URL-fragment hosts for substring matching
        known_hosts = set()
        for tag_config in TAG_PATTERNS.values():
            for url_frag in tag_config.get('urls', []):
                h = _extract_host(url_frag)
                if h:
                    known_hosts.add(h)
        for tech_config in self._tech_patterns.values():
            for url_frag in tech_config.get('urls', []):
                h = _extract_host(url_frag)
                if h:
                    known_hosts.add(h)

        # Collect owned domains for registrable-domain attribution
        owned_domains = set()
        for tag_config in TAG_PATTERNS.values():
            for d in tag_config.get('owned_domains', []):
                owned_domains.add(d)
        for tech_config in self._tech_patterns.values():
            for d in tech_config.get('owned_domains', []):
                owned_domains.add(d)

        matched = []
        unidentified_counts: Dict[str, int] = defaultdict(int)

        for page in self.page_data:
            for req in page.get('network_requests', []):
                req_host = urlparse(req['url']).netloc
                # Check URL-fragment match
                if any(kh in req_host for kh in known_hosts):
                    matched.append(req)
                # Check owned-domain match (host ends with a known domain)
                elif any(req_host == od or req_host.endswith('.' + od)
                         for od in owned_domains):
                    matched.append(req)
                else:
                    unidentified_counts[req_host] += 1

        return matched, dict(sorted(unidentified_counts.items(),
                                    key=lambda x: x[1], reverse=True))

    def export_json(self, filename: str):
        """Export comprehensive JSON with all data."""
        matched_requests, unidentified_hosts = self._classify_network_requests()

        # Strip raw network_requests from page data to control file size
        pages_export = []
        for page in self.page_data:
            p = {k: v for k, v in page.items() if k != 'network_requests'}
            pages_export.append(p)

        output = {
            'crawl_info': {
                'start_url': self.start_url,
                'crawled_at': datetime.now().isoformat(),
                'total_pages': len(self.page_data),
                'pages_success': self.stats['pages_crawled'],
                'pages_failed': self.stats['pages_failed'],
                'broken_links': len(self.broken_links),
                'max_depth_reached': max([p['depth'] for p in self.page_data]) if self.page_data else 0,
                'tags_summary': dict(self.stats['tags_found']),
                'technologies_summary': dict(self.stats['technologies_found'])
            },
            'sitemap': [p['url'] for p in self.page_data],
            'broken_links': self.broken_links,
            'matched_requests': matched_requests,
            'unidentified_third_party_hosts': unidentified_hosts,
            'pages': pages_export
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)

        print(f"Exported JSON to {filename}")

    def export_csv(self, filename: str):
        """Export CSV with key metrics per page."""
        if not self.page_data:
            return

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'url', 'status', 'depth', 'title', 'description',
                'gtm', 'ga4', 'ua', 'facebook_pixel', 'linkedin', 'tiktok',
                'adobe_analytics', 'hotjar', 'segment', 'tags_total',
                'datalayer_events', 'ga4_events', 'ecommerce_events',
                'technologies', 'load_time_ms', 'internal_links'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for page in self.page_data:
                tags = page.get('tags', {})

                row = {
                    'url': page['url'],
                    'status': page['status'],
                    'depth': page['depth'],
                    'title': page.get('metadata', {}).get('title', ''),
                    'description': page.get('metadata', {}).get('description', ''),
                    'gtm': 'Yes' if tags.get('google_tag_manager', {}).get('found') else 'No',
                    'ga4': 'Yes' if tags.get('google_analytics_4', {}).get('found') else 'No',
                    'ua': 'Yes' if tags.get('universal_analytics', {}).get('found') else 'No',
                    'facebook_pixel': 'Yes' if tags.get('facebook_pixel', {}).get('found') else 'No',
                    'linkedin': 'Yes' if tags.get('linkedin_insight', {}).get('found') else 'No',
                    'tiktok': 'Yes' if tags.get('tiktok_pixel', {}).get('found') else 'No',
                    'adobe_analytics': 'Yes' if tags.get('adobe_analytics', {}).get('found') else 'No',
                    'hotjar': 'Yes' if tags.get('hotjar', {}).get('found') else 'No',
                    'segment': 'Yes' if tags.get('segment', {}).get('found') else 'No',
                    'tags_total': len([t for t in tags.values() if t.get('found')]),
                    'datalayer_events': page.get('datalayer', {}).get('total_events', 0),
                    'ga4_events': len(page.get('datalayer', {}).get('ga4_events', {})),
                    'ecommerce_events': len(page.get('datalayer', {}).get('ecommerce_events', [])),
                    'technologies': len(page.get('technologies', [])),
                    'load_time_ms': int(page.get('performance', {}).get('load_time', 0)),
                    'internal_links': page.get('internal_links_found', 0)
                }
                writer.writerow(row)

        print(f"Exported CSV to {filename}")

    def export_findings(self, filename: str):
        """Export a structured findings report with tag index, tech index,
        GA4 summary, coverage analysis, and auto-generated findings."""
        if not self.page_data:
            return

        total_pages = len(self.page_data)
        matched_requests, unidentified_hosts = self._classify_network_requests()

        # --- Tag Index ---
        tag_index = {}
        for tag_name in sorted(self.stats['tags_found'].keys()):
            pages_present = []
            pages_absent = []
            all_ids = set()
            all_evidence = set()
            confidence_values = set()

            for page in self.page_data:
                tag_data = page.get('tags', {}).get(tag_name, {})
                if tag_data.get('found'):
                    pages_present.append(page['url'])
                    all_ids.update(tag_data.get('ids', []))
                    all_evidence.update(tag_data.get('evidence', []))
                    if 'confidence' in tag_data:
                        confidence_values.add(tag_data['confidence'])
                else:
                    pages_absent.append(page['url'])

            tag_config = TAG_PATTERNS.get(tag_name, {})
            coverage_pct = round(len(pages_present) / total_pages * 100, 1)

            entry = {
                'category': tag_config.get('category', 'Unknown'),
                'page_count': len(pages_present),
                'total_pages': total_pages,
                'coverage_pct': coverage_pct,
                'confidence': max(confidence_values, key=lambda c: {'high': 3, 'medium': 2, 'low': 1}.get(c, 0)) if confidence_values else 'unknown',
                'ids': sorted(all_ids),
                'evidence_types': sorted(all_evidence),
                'detection_methods': sorted(set(
                    e.split(':')[0] for e in all_evidence
                )),
            }
            if coverage_pct < 100:
                entry['absent_from'] = pages_absent
            tag_index[tag_name] = entry

        # --- Technology Index ---
        tech_index = {}
        tech_pages = defaultdict(list)
        tech_evidence = defaultdict(set)
        tech_confidence = defaultdict(set)
        tech_notes = {}

        for page in self.page_data:
            for tech in page.get('technologies', []):
                name = tech.get('name', 'Unknown')
                tech_pages[name].append(page['url'])
                tech_evidence[name].update(tech.get('evidence', []))
                if 'confidence' in tech:
                    tech_confidence[name].add(tech['confidence'])
                if 'detection_note' in tech:
                    tech_notes[name] = tech['detection_note']

        for name in sorted(tech_pages.keys()):
            coverage_pct = round(len(tech_pages[name]) / total_pages * 100, 1)
            conf_vals = tech_confidence[name]
            entry = {
                'category': next(
                    (t.get('category', 'Unknown')
                     for p in self.page_data
                     for t in p.get('technologies', [])
                     if t.get('name') == name),
                    'Unknown'
                ),
                'page_count': len(tech_pages[name]),
                'total_pages': total_pages,
                'coverage_pct': coverage_pct,
                'confidence': max(conf_vals, key=lambda c: {'high': 3, 'medium': 2, 'low': 1}.get(c, 0)) if conf_vals else 'unknown',
                'evidence_types': sorted(tech_evidence[name]),
            }
            if name in tech_notes:
                entry['detection_note'] = tech_notes[name]
            tech_index[name] = entry

        # --- Category Breakdown ---
        tag_categories = defaultdict(list)
        for tag_name, info in tag_index.items():
            tag_categories[info['category']].append(tag_name)
        category_breakdown = {
            cat: sorted(tags) for cat, tags in sorted(tag_categories.items())
        }

        # --- GA4 Summary (aggregated across all pages) ---
        all_measurement_ids = set()
        ga4_event_totals = defaultdict(int)
        datalayer_event_totals = defaultdict(int)
        gtag_configs = []
        total_datalayer_events = 0

        for page in self.page_data:
            # GA4 collect events
            ga4 = page.get('ga4_collect_events', {})
            all_measurement_ids.update(ga4.get('measurement_ids', []))
            for event_name, count in ga4.get('events', {}).items():
                ga4_event_totals[event_name] += count

            # DataLayer events
            dl = page.get('datalayer', {})
            total_datalayer_events += dl.get('total_events', 0)
            for label, count in dl.get('ga4_events', {}).items():
                datalayer_event_totals[label] += count

            # gtag configs (deduplicate by command+target)
            for cfg in dl.get('gtag_config', []):
                key = (cfg.get('command', ''), str(cfg.get('target', '')))
                if not any(
                    (c.get('command', ''), str(c.get('target', ''))) == key
                    for c in gtag_configs
                ):
                    gtag_configs.append(cfg)

        ga4_summary = {
            'measurement_ids': sorted(all_measurement_ids),
            'collect_events': dict(sorted(
                ga4_event_totals.items(), key=lambda x: -x[1]
            )),
            'datalayer_events': dict(sorted(
                datalayer_event_totals.items(), key=lambda x: -x[1]
            )),
            'total_datalayer_pushes': total_datalayer_events,
            'gtag_config': gtag_configs,
        }

        # --- Coverage Analysis ---
        # Group pages by their tag profile (frozenset of tag names)
        profile_groups = defaultdict(list)
        for page in self.page_data:
            tag_set = frozenset(
                k for k, v in page.get('tags', {}).items() if v.get('found')
            )
            profile_groups[tag_set].append(page['url'])

        coverage_profiles = []
        for tag_set, urls in sorted(
            profile_groups.items(), key=lambda x: -len(x[1])
        ):
            coverage_profiles.append({
                'tags': sorted(tag_set),
                'tag_count': len(tag_set),
                'page_count': len(urls),
                'pages': urls if len(urls) <= 10 else urls[:10] + [f'... and {len(urls) - 10} more'],
            })

        # --- Auto-generated Findings ---
        findings = []

        # Coverage gaps
        for tag_name, info in tag_index.items():
            if 0 < info['coverage_pct'] < 100:
                absent_count = total_pages - info['page_count']
                findings.append({
                    'type': 'coverage_gap',
                    'severity': 'medium' if info['coverage_pct'] > 50 else 'high',
                    'tag': tag_name,
                    'detail': f"{tag_name} detected on {info['page_count']}/{total_pages} pages ({info['coverage_pct']}%). Missing from {absent_count} pages.",
                })

        # Dual-fire detection (UA + GA4)
        if 'universal_analytics' in tag_index and 'google_analytics_4' in tag_index:
            findings.append({
                'type': 'dual_fire',
                'severity': 'medium',
                'tag': 'universal_analytics',
                'detail': 'Universal Analytics and GA4 are both active. UA stopped processing data in July 2023. UA tags add network overhead without collecting usable data.',
            })

        # Multiple GA4 measurement IDs
        if len(all_measurement_ids) > 1:
            findings.append({
                'type': 'multiple_measurement_ids',
                'severity': 'medium',
                'tag': 'google_analytics_4',
                'detail': f"{len(all_measurement_ids)} GA4 measurement IDs detected: {', '.join(sorted(all_measurement_ids))}. Verify all are intentional and not staging/prod crossfire.",
            })

        # Programmatic ad vendors
        ad_tags = [
            name for name, info in tag_index.items()
            if info['category'] == 'Programmatic-Advertising'
        ]
        if ad_tags:
            findings.append({
                'type': 'programmatic_ads',
                'severity': 'low',
                'tag': ', '.join(ad_tags),
                'detail': f"{len(ad_tags)} programmatic advertising vendors detected ({', '.join(ad_tags)}). These perform ID syncing and audience data sharing with third-party exchanges.",
            })

        # No consent management
        consent_tags = [
            name for name, info in tag_index.items()
            if info['category'] == 'Consent Management'
        ]
        ad_and_tracking_tags = [
            name for name, info in tag_index.items()
            if info['category'] in ('Advertising', 'Programmatic-Advertising', 'Analytics', 'Heatmaps', 'Session Recording', 'Retargeting')
        ]
        if not consent_tags and ad_and_tracking_tags:
            findings.append({
                'type': 'no_consent_management',
                'severity': 'high',
                'tag': 'none',
                'detail': f"No consent management platform detected, but {len(ad_and_tracking_tags)} tracking/advertising tags are active. This may create compliance risk under GDPR/CCPA.",
            })

        # Unidentified vendors
        if unidentified_hosts:
            findings.append({
                'type': 'unidentified_vendors',
                'severity': 'medium',
                'tag': 'none',
                'detail': f"{len(unidentified_hosts)} unidentified third-party hosts receiving requests. Top: {', '.join(list(unidentified_hosts.keys())[:5])}.",
            })

        # Tag profile inconsistency
        if len(coverage_profiles) > 1:
            dominant = coverage_profiles[0]
            outlier_count = total_pages - dominant['page_count']
            if outlier_count > 0:
                findings.append({
                    'type': 'tag_profile_inconsistency',
                    'severity': 'low',
                    'tag': 'none',
                    'detail': f"{len(coverage_profiles)} distinct tag profiles detected. {dominant['page_count']}/{total_pages} pages share the dominant profile ({dominant['tag_count']} tags). {outlier_count} pages have a different tag stack, suggesting template-level variation.",
                })

        # Vendor redundancy -- multiple tags in the same functional category
        redundancy_categories = {
            'Analytics': 'analytics',
            'Heatmaps': 'heatmap/session recording',
            'Session Recording': 'heatmap/session recording',
            'Tag Management': 'tag management',
            'A/B Testing': 'A/B testing',
            'Consent Management': 'consent management',
        }
        category_tags = defaultdict(list)
        for tag_name, info in tag_index.items():
            mapped = redundancy_categories.get(info['category'])
            if mapped:
                category_tags[mapped].append(tag_name)
        for purpose, tags in category_tags.items():
            if len(tags) > 1:
                findings.append({
                    'type': 'vendor_redundancy',
                    'severity': 'medium',
                    'tag': ', '.join(tags),
                    'detail': f"{len(tags)} {purpose} tools active: {', '.join(tags)}. Redundant tools add network overhead, may produce conflicting data, and increase the privacy surface.",
                })

        # Missing metadata
        pages_no_title = []
        pages_no_description = []
        pages_no_canonical = []
        duplicate_titles = defaultdict(list)
        for page in self.page_data:
            meta = page.get('metadata', {})
            url = page['url']
            title = (meta.get('title') or '').strip()
            if not title:
                pages_no_title.append(url)
            else:
                duplicate_titles[title].append(url)
            if not (meta.get('description') or '').strip():
                pages_no_description.append(url)
            if not (meta.get('canonical') or '').strip():
                pages_no_canonical.append(url)

        if pages_no_title:
            findings.append({
                'type': 'missing_title',
                'severity': 'medium',
                'tag': 'none',
                'detail': f"{len(pages_no_title)} page(s) missing a title tag: {', '.join(pages_no_title[:5])}" + (f" and {len(pages_no_title) - 5} more." if len(pages_no_title) > 5 else "."),
            })
        if pages_no_description:
            findings.append({
                'type': 'missing_description',
                'severity': 'medium' if len(pages_no_description) > total_pages * 0.1 else 'low',
                'tag': 'none',
                'detail': f"{len(pages_no_description)} page(s) missing a meta description: {', '.join(pages_no_description[:5])}" + (f" and {len(pages_no_description) - 5} more." if len(pages_no_description) > 5 else "."),
            })

        dupe_titles = {t: urls for t, urls in duplicate_titles.items() if len(urls) > 1}
        if dupe_titles:
            total_dupes = sum(len(urls) for urls in dupe_titles.values())
            worst_title = max(dupe_titles, key=lambda t: len(dupe_titles[t]))
            findings.append({
                'type': 'duplicate_titles',
                'severity': 'medium' if total_dupes > total_pages * 0.2 else 'low',
                'tag': 'none',
                'detail': f"{total_dupes} pages share duplicate titles across {len(dupe_titles)} title(s). Most repeated: \"{worst_title}\" ({len(dupe_titles[worst_title])} pages).",
            })

        # Tag-to-performance correlation
        load_times = []
        tag_counts = []
        for page in self.page_data:
            lt = page.get('performance', {}).get('load_time', 0)
            tc = sum(1 for v in page.get('tags', {}).values() if v.get('found'))
            if lt > 0:
                load_times.append(lt)
                tag_counts.append(tc)

        if load_times:
            avg_load = sum(load_times) / len(load_times)

            # Slow page detection (>1.5x average)
            slow_pages = [
                (page['url'], page.get('performance', {}).get('load_time', 0))
                for page in self.page_data
                if page.get('performance', {}).get('load_time', 0) > avg_load * 1.5
            ]
            if slow_pages:
                slow_pages.sort(key=lambda x: -x[1])
                findings.append({
                    'type': 'slow_pages',
                    'severity': 'medium',
                    'tag': 'none',
                    'detail': f"{len(slow_pages)} page(s) load more than 1.5x the average ({avg_load:.0f}ms). Slowest: {slow_pages[0][0]} ({slow_pages[0][1]:.0f}ms)." + (f" Next: {slow_pages[1][0]} ({slow_pages[1][1]:.0f}ms)." if len(slow_pages) > 1 else ""),
                })

            # Correlation: do pages with more tags load slower?
            if len(set(tag_counts)) > 1 and len(load_times) >= 5:
                # Group by tag count, compare averages
                tc_groups = defaultdict(list)
                for tc, lt in zip(tag_counts, load_times):
                    tc_groups[tc].append(lt)
                group_avgs = {tc: sum(lts) / len(lts) for tc, lts in tc_groups.items()}
                min_tc = min(group_avgs)
                max_tc = max(group_avgs)
                if max_tc > min_tc and group_avgs[max_tc] > group_avgs[min_tc] * 1.2:
                    findings.append({
                        'type': 'tag_performance_correlation',
                        'severity': 'low',
                        'tag': 'none',
                        'detail': f"Pages with {max_tc} tags average {group_avgs[max_tc]:.0f}ms load time vs {group_avgs[min_tc]:.0f}ms for pages with {min_tc} tags ({((group_avgs[max_tc] / group_avgs[min_tc]) - 1) * 100:.0f}% slower).",
                    })

        # Silent GA4 pages -- GA4 tag present but no collect request fired
        if 'google_analytics_4' in tag_index:
            silent_pages = []
            for page in self.page_data:
                ga4_tag = page.get('tags', {}).get('google_analytics_4', {})
                ga4_collect = page.get('ga4_collect_events', {})
                if ga4_tag.get('found') and not ga4_collect.get('events'):
                    silent_pages.append(page['url'])
            if silent_pages:
                findings.append({
                    'type': 'silent_ga4',
                    'severity': 'high' if len(silent_pages) > total_pages * 0.5 else 'medium',
                    'tag': 'google_analytics_4',
                    'detail': f"GA4 tag present on {len(silent_pages)} page(s) but no Measurement Protocol collect requests fired. GA4 may be blocked by consent, ad blockers, or misconfiguration: {', '.join(silent_pages[:5])}" + (f" and {len(silent_pages) - 5} more." if len(silent_pages) > 5 else "."),
                })

        # DataLayer pollution -- high push count with no structured events
        if ga4_summary['total_datalayer_pushes'] > 0 and not ga4_summary['datalayer_events']:
            findings.append({
                'type': 'no_event_tracking',
                'severity': 'low',
                'tag': 'none',
                'detail': f"{ga4_summary['total_datalayer_pushes']} dataLayer pushes detected across all pages but 0 named GA4 events surfaced. No structured event tracking is in place -- conversion actions (form submits, sign-ups, purchases) are not being measured.",
            })

        # Multiple GTM containers
        gtm_info = tag_index.get('google_tag_manager', {})
        gtm_ids = gtm_info.get('ids', [])
        if len(gtm_ids) > 1:
            findings.append({
                'type': 'multiple_gtm_containers',
                'severity': 'medium',
                'tag': 'google_tag_manager',
                'detail': f"{len(gtm_ids)} GTM container IDs detected: {', '.join(gtm_ids)}. Multiple containers increase page weight, can cause race conditions, and make tag governance harder.",
            })

        # Dead-end pages -- very few internal links out
        dead_end_pages = [
            page['url'] for page in self.page_data
            if page.get('internal_links_found', 0) <= 1 and page.get('status') == 200
        ]
        if dead_end_pages:
            findings.append({
                'type': 'dead_end_pages',
                'severity': 'low',
                'tag': 'none',
                'detail': f"{len(dead_end_pages)} page(s) have 1 or fewer internal links, limiting discoverability: {', '.join(dead_end_pages[:5])}" + (f" and {len(dead_end_pages) - 5} more." if len(dead_end_pages) > 5 else "."),
            })

        # Sort findings by severity
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        findings.sort(key=lambda f: severity_order.get(f['severity'], 3))

        # --- Assemble Output ---
        output = {
            'report_info': {
                'site': self.start_url,
                'domain': self.base_domain,
                'generated_at': datetime.now().isoformat(),
                'total_pages': total_pages,
                'tagscope_version': '3.3.0',
            },
            'tag_index': tag_index,
            'technology_index': tech_index,
            'category_breakdown': category_breakdown,
            'ga4_summary': ga4_summary,
            'coverage_profiles': coverage_profiles,
            'third_party_summary': {
                'matched_request_count': len(matched_requests),
                'unidentified_host_count': len(unidentified_hosts),
                'unidentified_hosts': unidentified_hosts,
            },
            'findings': findings,
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)

        print(f"Exported findings report to {filename}")

    def export_tag_matrix(self, filename: str):
        """Export a tag coverage matrix as CSV.

        Rows are pages (or page groups when multiple pages share an identical
        tag profile). Columns are every tag detected on at least one page.
        Cells contain 'x' (present) or are empty (absent).
        """
        if not self.page_data:
            return

        # Collect all tags that were found on at least one page
        all_tags = sorted({
            tag_name
            for page in self.page_data
            for tag_name, tag_data in page.get('tags', {}).items()
            if tag_data.get('found')
        })

        if not all_tags:
            return

        # Group pages by their exact tag fingerprint
        from collections import OrderedDict
        profile_groups = OrderedDict()
        for page in self.page_data:
            tag_set = frozenset(
                k for k, v in page.get('tags', {}).items() if v.get('found')
            )
            if tag_set not in profile_groups:
                profile_groups[tag_set] = []
            profile_groups[tag_set].append(page['url'])

        # Sort groups: largest first
        sorted_profiles = sorted(
            profile_groups.items(), key=lambda x: -len(x[1])
        )

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['page', 'pages_in_group'] + all_tags
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for tag_set, urls in sorted_profiles:
                if len(urls) == 1:
                    label = urls[0]
                    count = 1
                else:
                    label = urls[0] + f' (+{len(urls) - 1} more)'
                    count = len(urls)

                row = {
                    'page': label,
                    'pages_in_group': count,
                }
                for tag_name in all_tags:
                    row[tag_name] = 'x' if tag_name in tag_set else ''
                writer.writerow(row)

            # Summary row: total pages where each tag is present
            summary = {'page': 'TOTAL', 'pages_in_group': len(self.page_data)}
            for tag_name in all_tags:
                summary[tag_name] = sum(
                    len(urls) for tag_set, urls in sorted_profiles
                    if tag_name in tag_set
                )
            writer.writerow(summary)

        print(f"Exported tag coverage matrix to {filename}")

    def export_llm(self, filename: str):
        """Export LLM-optimized JSON with compact projections."""
        if not self.page_data:
            return

        _, unidentified_hosts = self._classify_network_requests()

        output = format_site_llm(
            self.page_data,
            broken_links=self.broken_links,
            unidentified_hosts=unidentified_hosts,
        )

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)

        print(f"Exported LLM format to {filename}")

    def export_html(self, filename: str):
        """Export interactive HTML report."""
        tag_summary = defaultdict(int)
        for page in self.page_data:
            for tag_name, tag_data in page.get('tags', {}).items():
                if tag_data.get('found'):
                    tag_summary[tag_name] += 1

        tech_summary = defaultdict(int)
        for page in self.page_data:
            for tech in page.get('technologies', []):
                tech_summary[tech.get('name', 'Unknown')] += 1

        html = _build_html_report(self.base_domain, self.page_data,
                                  self.broken_links, tag_summary, tech_summary)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"Exported HTML report to {filename}")


def _build_html_report(domain: str, page_data: List[Dict],
                       broken_links: List[Dict], tag_summary: Dict,
                       tech_summary: Dict) -> str:
    """Build the interactive HTML report string."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Site Audit Report - {domain}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
               background: #f5f7fa; color: #2c3e50; line-height: 1.6; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                 color: white; padding: 40px 20px; border-radius: 10px; margin-bottom: 30px; }}
        h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .subtitle {{ opacity: 0.9; font-size: 1.1em; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                      gap: 20px; margin: 30px 0; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 8px;
                     box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center; }}
        .stat-number {{ font-size: 2.5em; font-weight: bold; color: #667eea; }}
        .stat-label {{ color: #7f8c8d; margin-top: 5px; }}
        .section {{ background: white; padding: 30px; border-radius: 8px;
                   box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin: 20px 0; }}
        h2 {{ color: #2c3e50; border-bottom: 3px solid #667eea; padding-bottom: 10px; margin-bottom: 20px; }}
        .tag-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 15px; }}
        .tag-item {{ background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #667eea; }}
        .tag-name {{ font-weight: 600; color: #2c3e50; margin-bottom: 5px; }}
        .tag-count {{ color: #7f8c8d; font-size: 0.9em; }}
        .tag-category {{ display: inline-block; background: #e3e8f7; padding: 2px 8px;
                        border-radius: 3px; font-size: 0.85em; margin-top: 5px; }}
        .page-list {{ margin-top: 20px; }}
        .page-item {{ background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px;
                     border-left: 4px solid #3498db; }}
        .page-item:hover {{ background: #e8f4f8; }}
        .page-url {{ color: #2980b9; font-weight: 500; word-break: break-all; margin-bottom: 10px; }}
        .page-meta {{ display: flex; gap: 15px; flex-wrap: wrap; font-size: 0.9em; color: #7f8c8d; }}
        .badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px;
                 font-size: 0.85em; font-weight: 500; }}
        .badge-success {{ background: #d4edda; color: #155724; }}
        .badge-warning {{ background: #fff3cd; color: #856404; }}
        .badge-info {{ background: #d1ecf1; color: #0c5460; }}
        .tags-inline {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; }}
        .tag-badge {{ background: #667eea; color: white; padding: 4px 10px; border-radius: 4px; font-size: 0.85em; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #667eea; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ecf0f1; }}
        tr:hover {{ background: #f8f9fa; }}
        .broken-link {{ color: #e74c3c; }}
        .summary-box {{ background: #e8f5e9; border-left: 4px solid #4caf50; padding: 15px; margin: 15px 0; }}
        .warning-box {{ background: #fff3e0; border-left: 4px solid #ff9800; padding: 15px; margin: 15px 0; }}
        @media (max-width: 768px) {{
            .stats-grid {{ grid-template-columns: 1fr; }}
            .tag-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Site Audit Report</h1>
            <div class="subtitle">{domain}</div>
            <div class="subtitle">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{len(page_data)}</div>
                <div class="stat-label">Pages Crawled</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(tag_summary)}</div>
                <div class="stat-label">Unique Tags Found</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(tech_summary)}</div>
                <div class="stat-label">Technologies</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(broken_links)}</div>
                <div class="stat-label">Broken Links</div>
            </div>
        </div>
"""

    if tag_summary:
        html += """
        <div class="section">
            <h2>Tags Detected</h2>
            <div class="tag-grid">
"""
        for tag_name, count in sorted(tag_summary.items(), key=lambda x: x[1], reverse=True):
            tag_config = TAG_PATTERNS.get(tag_name, {})
            category = tag_config.get('category', 'Other')
            display_name = tag_name.replace('_', ' ').title()
            html += f"""
                <div class="tag-item">
                    <div class="tag-name">{display_name}</div>
                    <div class="tag-count">Found on {count} page(s)</div>
                    <div class="tag-category">{category}</div>
                </div>
"""
        html += """
            </div>
        </div>
"""

    if tech_summary:
        html += """
        <div class="section">
            <h2>Technologies Detected</h2>
            <div class="tag-grid">
"""
        for tech_name, count in sorted(tech_summary.items(), key=lambda x: x[1], reverse=True)[:20]:
            html += f"""
                <div class="tag-item">
                    <div class="tag-name">{tech_name}</div>
                    <div class="tag-count">Found on {count} page(s)</div>
                </div>
"""
        html += """
            </div>
        </div>
"""

    if broken_links:
        html += f"""
        <div class="section">
            <h2>Broken Links</h2>
            <div class="warning-box">
                Found {len(broken_links)} broken links that should be fixed.
            </div>
            <table>
                <tr><th>URL</th><th>Status Code</th><th>Depth</th></tr>
"""
        for link in broken_links[:50]:
            html += f"""
                <tr>
                    <td class="broken-link">{link['url']}</td>
                    <td>{link['status']}</td>
                    <td>{link['depth']}</td>
                </tr>
"""
        html += """
            </table>
        </div>
"""

    html += """
        <div class="section">
            <h2>Page Details</h2>
            <div class="page-list">
"""

    for page in page_data[:100]:
        tags_found = [k.replace('_', ' ').title() for k, v in page.get('tags', {}).items() if v.get('found')]
        datalayer_info = page.get('datalayer', {})
        perf = page.get('performance', {})

        html += f"""
            <div class="page-item">
                <div class="page-url">{page.get('metadata', {}).get('title', 'No Title')} <br><small>{page['url']}</small></div>
                <div class="page-meta">
                    <span class="badge badge-success">Status: {page['status']}</span>
                    <span class="badge badge-info">Depth: {page['depth']}</span>
                    <span class="badge badge-info">Tags: {len(tags_found)}</span>
                    <span class="badge badge-info">DataLayer Events: {datalayer_info.get('total_events', 0)}</span>
"""
        if perf.get('load_time'):
            html += f"""
                    <span class="badge badge-warning">Load: {int(perf['load_time'])}ms</span>
"""
        html += """
                </div>
"""
        if tags_found:
            html += """
                <div class="tags-inline">
"""
            for tag in tags_found[:10]:
                html += f"""
                    <span class="tag-badge">{tag}</span>
"""
            html += """
                </div>
"""
        html += """
            </div>
"""

    html += """
            </div>
        </div>

        <div class="section">
            <div class="summary-box">
                <strong>Report generated successfully.</strong>
                See the JSON export for complete raw data including dataLayer contents,
                network requests, and detailed tag information.
            </div>
        </div>

    </div>
</body>
</html>
"""

    return html


# ---------------------------------------------------------------------------
# Single-page audit API
# ---------------------------------------------------------------------------

def _single_page_config(url: str, overrides: Optional[Dict] = None) -> Dict:
    """Build a minimal config dict tuned for single-page auditing.

    Starts from the same defaults as the CLI, then disables crawl-specific
    features (resume, progress saving, rate limiting) so a single page can
    be audited as fast as possible.
    """
    # Import here to avoid circular dependency at module level
    from tagscope.cli import _default_config

    cfg = _default_config()
    cfg['start_url'] = url
    cfg['crawl']['max_pages'] = 1
    cfg['crawl']['max_depth'] = 0
    cfg['crawl']['rate_limit'] = 0.0  # no throttle for single page
    cfg['crawl']['concurrent_pages'] = 1
    cfg['resume']['enabled'] = False
    cfg['output']['save_progress'] = False
    cfg['logging']['console'] = False
    cfg['logging']['log_file'] = None

    if overrides:
        for section, values in overrides.items():
            if isinstance(values, dict) and section in cfg:
                cfg[section].update(values)
            else:
                cfg[section] = values

    return cfg


async def audit_page(
    url: str,
    *,
    config: Optional[Dict] = None,
    browser: Optional[Browser] = None,
    tech_patterns: Optional[Dict] = None,
) -> Optional[Dict]:
    """Audit a single page and return its data dict.

    This is the public, standalone entry point for single-page auditing.
    It reuses the full SiteAuditor analysis pipeline (metadata, tags,
    dataLayer, GA4 collect decoding, performance metrics, and technology
    detection) without any crawl orchestration overhead.

    Parameters
    ----------
    url : str
        The page URL to audit.
    config : dict, optional
        Config overrides merged on top of single-page defaults.
        Accepts the same section/key structure as the full config
        (e.g. ``{'browser': {'headless': False}}``).
    browser : playwright Browser, optional
        An existing Playwright Chromium browser instance to reuse.
        When provided the caller owns the lifecycle; ``audit_page``
        will **not** close it.  When omitted a browser is launched
        and torn down automatically.
    tech_patterns : dict, optional
        Extended technology patterns (e.g. merged Wappalyzer rulesets).
        Falls back to the built-in ``TECHNOLOGY_PATTERNS``.

    Returns
    -------
    dict or None
        The page data dict on success, ``None`` on navigation failure
        or HTTP >= 400.
    """
    cfg = _single_page_config(url, config)
    auditor = SiteAuditor(cfg, extended_tech_patterns=tech_patterns)
    # Bypass the 0.1 s floor enforced by the constructor -- single-page
    # mode should not sleep between requests.
    auditor.rate_limit = 0

    own_browser = browser is None
    pw_context = None
    try:
        if own_browser:
            pw_context = await async_playwright().start()
            browser = await pw_context.chromium.launch(
                headless=cfg['browser']['headless']
            )

        return await auditor._crawl_page(browser, url, depth=0)
    finally:
        if own_browser:
            if browser:
                await browser.close()
            if pw_context:
                await pw_context.stop()


# ---------------------------------------------------------------------------
# LLM-optimized format projection
# ---------------------------------------------------------------------------

def _merge_ga4(datalayer: Dict, ga4_collect: Dict) -> Dict:
    """Merge datalayer GA4 data and collect-request data into one summary."""
    measurement_ids = sorted(set(ga4_collect.get('measurement_ids', [])))

    # Merge event counts: collect events are the ground truth for what
    # actually fired; datalayer events show what was pushed client-side.
    # Use collect counts when available, fall back to datalayer.
    events = dict(ga4_collect.get('events', {}))
    for label, count in datalayer.get('ga4_events', {}).items():
        key = label.lower().replace(' ', '_')
        if key not in events:
            events[key] = count

    custom = datalayer.get('custom_events', [])
    gtag_config = datalayer.get('gtag_config', [])

    out = {}
    if measurement_ids:
        out['measurement_ids'] = measurement_ids
    if events:
        out['events'] = events
    if custom:
        out['custom_events'] = custom
    if gtag_config:
        out['gtag_config'] = gtag_config
    return out


def format_page_llm(page_data: Dict) -> Dict:
    """Project a page data dict into a compact, LLM-optimized shape.

    Strips detection internals (evidence, found bools, detection_notes),
    raw network request logs, full meta tag lists, screenshot paths,
    and crawl depth. Flattens metadata into top-level fields. Merges
    datalayer and GA4 collect data into a single ``ga4`` key.

    Field order is stable and alphabetical within sections to keep
    token representations consistent across calls.
    """
    meta = page_data.get('metadata', {})

    # --- Tags: keep only ids, category, confidence ---
    tags = {}
    for name, info in sorted(page_data.get('tags', {}).items()):
        entry = {'category': info['category'], 'confidence': info['confidence']}
        if info.get('ids'):
            entry['ids'] = info['ids']
        tags[name] = entry

    # --- Technologies: flatten to list of {name, category, confidence} ---
    techs = [
        {'name': t['name'], 'category': t['category'], 'confidence': t['confidence']}
        for t in sorted(page_data.get('technologies', []), key=lambda t: t['name'])
    ]

    # --- GA4: merge datalayer + collect ---
    ga4 = _merge_ga4(
        page_data.get('datalayer', {}),
        page_data.get('ga4_collect_events', {}),
    )

    # --- Performance: pass through, already compact ---
    perf = page_data.get('performance', {})

    # --- Assemble in stable order ---
    out = {'url': page_data['url'], 'status': page_data['status']}

    if meta.get('title'):
        out['title'] = meta['title']
    if meta.get('description'):
        out['description'] = meta['description']
    if meta.get('canonical'):
        out['canonical'] = meta['canonical']
    if meta.get('lang'):
        out['lang'] = meta['lang']
    if meta.get('h1'):
        out['h1'] = meta['h1']

    if tags:
        out['tags'] = tags
    if techs:
        out['technologies'] = techs
    if ga4:
        out['ga4'] = ga4
    if perf:
        out['performance'] = perf

    out['crawled_at'] = page_data.get('crawled_at', '')
    return out


def format_site_llm(
    pages: List[Dict],
    broken_links: Optional[List[Dict]] = None,
    unidentified_hosts: Optional[Dict[str, int]] = None,
) -> Dict:
    """Project a full site audit into a compact, LLM-optimized shape.

    Aggregates per-page data into site-level summaries: tag coverage,
    technology stack, merged GA4 analytics, average performance, and
    page-level compact records. Designed to fit comfortably in an LLM
    context window even for large crawls.
    """
    if not pages:
        return {'pages_audited': 0}

    start_url = pages[0]['url']
    total = len(pages)

    # --- Tag coverage ---
    tag_agg: Dict[str, Dict] = {}
    for page in pages:
        for name, info in page.get('tags', {}).items():
            if name not in tag_agg:
                tag_agg[name] = {
                    'category': info['category'],
                    'ids': set(),
                    'pages': 0,
                    'confidence': info['confidence'],
                }
            agg = tag_agg[name]
            agg['pages'] += 1
            agg['ids'].update(info.get('ids', []))
            if info['confidence'] == 'high':
                agg['confidence'] = 'high'

    tags_out = {}
    for name in sorted(tag_agg):
        agg = tag_agg[name]
        entry = {
            'category': agg['category'],
            'pages': agg['pages'],
            'coverage_pct': round(agg['pages'] / total * 100, 1),
            'confidence': agg['confidence'],
        }
        if agg['ids']:
            entry['ids'] = sorted(agg['ids'])
        tags_out[name] = entry

    # --- Technology stack ---
    tech_agg: Dict[str, Dict] = {}
    for page in pages:
        for t in page.get('technologies', []):
            name = t['name']
            if name not in tech_agg:
                tech_agg[name] = {
                    'category': t['category'],
                    'pages': 0,
                    'confidence': t['confidence'],
                }
            tech_agg[name]['pages'] += 1
            if t['confidence'] == 'high':
                tech_agg[name]['confidence'] = 'high'

    techs_out = [
        {
            'name': name,
            'category': info['category'],
            'pages': info['pages'],
            'confidence': info['confidence'],
        }
        for name, info in sorted(tech_agg.items())
    ]

    # --- GA4 aggregate ---
    all_mids: set = set()
    all_events: Dict[str, int] = {}
    all_custom: set = set()
    for page in pages:
        dl = page.get('datalayer', {})
        gc = page.get('ga4_collect_events', {})
        all_mids.update(gc.get('measurement_ids', []))
        # Per-page dedup: prefer collect events, fall back to datalayer
        page_events = dict(gc.get('events', {}))
        for label, cnt in dl.get('ga4_events', {}).items():
            key = label.lower().replace(' ', '_')
            if key not in page_events:
                page_events[key] = cnt
        for ev, cnt in page_events.items():
            all_events[ev] = all_events.get(ev, 0) + cnt
        all_custom.update(dl.get('custom_events', []))

    ga4_out = {}
    if all_mids:
        ga4_out['measurement_ids'] = sorted(all_mids)
    if all_events:
        ga4_out['events'] = all_events
    if all_custom:
        ga4_out['custom_events'] = sorted(all_custom)

    # --- Performance averages ---
    perf_sums: Dict[str, float] = {}
    perf_counts: Dict[str, int] = {}
    for page in pages:
        for k, v in page.get('performance', {}).items():
            if isinstance(v, (int, float)) and v > 0:
                perf_sums[k] = perf_sums.get(k, 0) + v
                perf_counts[k] = perf_counts.get(k, 0) + 1
    perf_avg = {
        k: round(perf_sums[k] / perf_counts[k], 1) for k in sorted(perf_sums)
    }

    # --- Compact per-page records ---
    page_records = []
    for page in pages:
        rec = format_page_llm(page)
        page_records.append(rec)

    # --- Assemble ---
    out: Dict = {
        'url': start_url,
        'pages_audited': total,
    }
    if tags_out:
        out['tags'] = tags_out
    if techs_out:
        out['technologies'] = techs_out
    if ga4_out:
        out['ga4'] = ga4_out
    if perf_avg:
        out['performance_avg'] = perf_avg
    if broken_links:
        out['broken_links'] = len(broken_links)
    if unidentified_hosts:
        out['unidentified_hosts'] = dict(
            sorted(unidentified_hosts.items(), key=lambda x: -x[1])[:20]
        )
    out['pages'] = page_records
    return out
