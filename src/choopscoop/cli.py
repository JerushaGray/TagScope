"""Command-line interface for ChoopScoop."""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from platform import system
from typing import Dict, Optional
from urllib.parse import urlparse

from choopscoop import __version__
from choopscoop.auditor import SiteAuditor
from choopscoop.wappalyzer_adapter import (
    fetch_rulesets, load_and_convert, merge_patterns, compile_patterns,
    RULESETS_DIR,
)

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def check_dependencies() -> bool:
    """Check if all required dependencies are available."""
    issues = []

    try:
        from playwright.async_api import async_playwright  # noqa: F401
    except ImportError:
        issues.append("Playwright not installed. Run: pip install playwright")

    if system() == "Windows":
        playwright_dir = Path.home() / "AppData" / "Local" / "ms-playwright"
    else:
        playwright_dir = Path.home() / ".cache" / "ms-playwright"

    if not playwright_dir.exists() or not any(playwright_dir.glob("chromium-*")):
        issues.append("Playwright browsers not installed. Run: playwright install chromium")

    if issues:
        print("Missing dependencies:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return False

    return True


def load_config(config_file: Optional[str], cli_args: Dict) -> Dict:
    """Load and merge configuration from file and CLI arguments."""
    config = None

    if config_file and Path(config_file).exists():
        if not YAML_AVAILABLE:
            print(f"Cannot load {config_file}: PyYAML not installed", file=sys.stderr)
            print("Install with: pip install pyyaml", file=sys.stderr)
        else:
            try:
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                print(f"Loaded config from {config_file}\n")
            except yaml.YAMLError as e:
                print(f"Error parsing config file {config_file}: {e}", file=sys.stderr)
            except Exception as e:
                print(f"Could not read config file: {e}", file=sys.stderr)

    if not config:
        config = _default_config()

    config['start_url'] = cli_args['url']
    if cli_args.get('max_pages'):
        config['crawl']['max_pages'] = cli_args['max_pages']
    if cli_args.get('max_depth'):
        config['crawl']['max_depth'] = cli_args['max_depth']
    if cli_args.get('rate_limit'):
        config['crawl']['rate_limit'] = cli_args['rate_limit']
    if cli_args.get('concurrent'):
        config['crawl']['concurrent_pages'] = cli_args['concurrent']
    if cli_args.get('output'):
        config['output']['prefix'] = cli_args['output']
    else:
        domain = urlparse(config['start_url']).netloc.replace(':', '_')
        config['output']['prefix'] = f'output/run-{domain}/site-audit-{domain}'

    # Ensure the output directory exists
    output_dir = Path(config['output']['prefix']).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    if cli_args.get('format'):
        if cli_args['format'] == 'all':
            config['output']['formats'] = ['json', 'csv', 'html']
        else:
            config['output']['formats'] = [cli_args['format']]
    if cli_args.get('exclude'):
        config['filters']['exclude_patterns'] = cli_args['exclude']
    if cli_args.get('include'):
        config['filters']['include_patterns'] = cli_args['include']
    if cli_args.get('no_resume'):
        config['resume']['enabled'] = False

    return config


def _default_config() -> Dict:
    """Return default configuration."""
    return {
        'crawl': {
            'max_pages': 100, 'max_depth': 3, 'rate_limit': 1.0,
            'concurrent_pages': 3, 'timeout': 30
        },
        'retry': {
            'max_retries': 3, 'retry_delay': 2.0,
            'retry_on_status': [500, 502, 503, 504, 429]
        },
        'browser': {
            'headless': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'viewport': {'width': 1920, 'height': 1080},
            'javascript_enabled': True, 'ignore_https_errors': False
        },
        'filters': {
            'respect_robots': True, 'exclude_patterns': [],
            'include_patterns': [],
            'skip_extensions': ['.pdf', '.jpg', '.png', '.gif', '.css', '.js', '.zip']
        },
        'technology': {'detect_all': True},
        'tags': {'detect_all': True, 'custom_patterns': {}},
        'datalayer': {'extract': True, 'parse_events': True, 'max_events': 100},
        'performance': {
            'capture_metrics': True, 'capture_screenshots': False,
            'screenshot_format': 'png'
        },
        'output': {
            'formats': ['json', 'csv', 'html'], 'prefix': 'site-audit',
            'save_progress': True, 'progress_interval': 10
        },
        'logging': {'level': 'INFO', 'log_file': 'choopscoop.log', 'console': True},
        'resume': {'enabled': True, 'state_file': 'crawl_state.json'}
    }


async def _async_main():
    """Async entry point."""
    parser = argparse.ArgumentParser(
        description='ChoopScoop - Playwright-powered site auditor and marketing tag detector',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://example.com
  %(prog)s https://example.com --max-pages 500 --concurrent 5
  %(prog)s https://example.com --config my-config.yaml
  %(prog)s https://example.com --exclude "/admin.*" "/login.*"
        """
    )

    parser.add_argument('url', nargs='?', default=None,
                        help='Starting URL to crawl')
    parser.add_argument('--config', help='Path to config file (YAML)')
    parser.add_argument('--max-pages', type=int, help='Maximum pages to crawl')
    parser.add_argument('--max-depth', type=int, help='Maximum crawl depth')
    parser.add_argument('--rate-limit', type=float, help='Seconds between requests')
    parser.add_argument('--concurrent', type=int, help='Concurrent pages (1-10)')
    parser.add_argument('--output', help='Output filename prefix')
    parser.add_argument('--format', choices=['json', 'csv', 'html', 'llm', 'all'],
                        help='Export format')
    parser.add_argument('--exclude', nargs='+',
                        help='URL patterns to exclude (regex)')
    parser.add_argument('--include', nargs='+',
                        help='URL patterns to include (regex)')
    parser.add_argument('--no-resume', action='store_true',
                        help='Disable resume capability')
    parser.add_argument('--fetch-rulesets', action='store_true',
                        help='Download Wappalyzer fingerprints to local cache and exit')
    parser.add_argument('--extended', action='store_true',
                        help='Enable extended technology detection using cached Wappalyzer rulesets')
    parser.add_argument('--version', action='version',
                        version=f'%(prog)s {__version__}')

    args = parser.parse_args()

    # Handle --fetch-rulesets: download and exit
    if args.fetch_rulesets:
        print(f"ChoopScoop v{__version__} - fetching Wappalyzer rulesets...\n")
        try:
            dest = fetch_rulesets()
            print(f"\nRulesets cached at {dest}")
            print("Use --extended to enable extended detection on your next crawl.")
        except Exception as e:
            print(f"Error fetching rulesets: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if not args.url:
        parser.error("the following arguments are required: url")

    print(f"ChoopScoop v{__version__} - checking dependencies...\n")
    if not check_dependencies():
        print("\nPlease install missing dependencies and try again.", file=sys.stderr)
        sys.exit(2)
    print("All dependencies available.\n")

    config = load_config(args.config, vars(args))

    # Load extended patterns if requested
    extended_patterns = None
    if args.extended:
        if not RULESETS_DIR.exists():
            print(
                "No cached rulesets found. Run --fetch-rulesets first.",
                file=sys.stderr,
            )
            sys.exit(2)
        print("Loading extended technology detection (Wappalyzer rulesets)...")
        wappalyzer_patterns = load_and_convert()
        from choopscoop.patterns import TECHNOLOGY_PATTERNS
        extended_patterns = merge_patterns(TECHNOLOGY_PATTERNS, wappalyzer_patterns)
        extended_patterns = compile_patterns(extended_patterns)
        print(f"  {len(extended_patterns)} technology patterns loaded "
              f"({len(extended_patterns) - len(TECHNOLOGY_PATTERNS)} from Wappalyzer)\n")

    auditor = SiteAuditor(config, extended_tech_patterns=extended_patterns)

    try:
        await auditor.crawl()

        print("\n" + "=" * 80)
        print("Exporting results...")
        print("=" * 80)

        output_prefix = config['output']['prefix']

        if 'json' in config['output']['formats']:
            auditor.export_json(f'{output_prefix}.json')

        if 'csv' in config['output']['formats']:
            auditor.export_csv(f'{output_prefix}.csv')

        if 'html' in config['output']['formats']:
            auditor.export_html(f'{output_prefix}.html')

        if 'llm' in config['output']['formats']:
            auditor.export_llm(f'{output_prefix}-llm.json')

        auditor.export_findings(f'{output_prefix}-findings.json')
        auditor.export_tag_matrix(f'{output_prefix}-tag-matrix.csv')

        print("\n" + "=" * 80)
        print("Audit complete!")
        print("=" * 80)

    except KeyboardInterrupt:
        print("\n\nCrawl interrupted by user.")
        if config['output']['save_progress']:
            auditor.save_progress()
            print("Progress saved. Resume with the same command.")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Synchronous entry point for console_scripts."""
    asyncio.run(_async_main())


if __name__ == '__main__':
    main()
