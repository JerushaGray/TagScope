"""Tests for configuration loading and CLI argument merging."""

import os
import tempfile
import pytest
from tagscope.cli import load_config, _default_config


class TestDefaultConfig:
    def test_has_required_sections(self):
        config = _default_config()
        for section in ['crawl', 'retry', 'browser', 'filters', 'technology',
                        'tags', 'datalayer', 'performance', 'output', 'logging', 'resume']:
            assert section in config

    def test_default_max_pages(self):
        assert _default_config()['crawl']['max_pages'] == 100

    def test_default_formats(self):
        assert _default_config()['output']['formats'] == ['json', 'csv', 'html']

    def test_default_skip_extensions(self):
        exts = _default_config()['filters']['skip_extensions']
        assert '.pdf' in exts
        assert '.jpg' in exts
        assert '.zip' in exts


class TestLoadConfig:
    def _base_args(self, **overrides):
        args = {
            'url': 'https://example.com',
            'config': None,
            'max_pages': None,
            'max_depth': None,
            'rate_limit': None,
            'concurrent': None,
            'output': None,
            'format': None,
            'exclude': None,
            'include': None,
            'no_resume': False,
        }
        args.update(overrides)
        return args

    def test_no_config_file_uses_defaults(self):
        config = load_config(None, self._base_args())
        assert config['start_url'] == 'https://example.com'
        assert config['crawl']['max_pages'] == 100

    def test_cli_max_pages_override(self):
        config = load_config(None, self._base_args(max_pages=500))
        assert config['crawl']['max_pages'] == 500

    def test_cli_max_depth_override(self):
        config = load_config(None, self._base_args(max_depth=5))
        assert config['crawl']['max_depth'] == 5

    def test_cli_rate_limit_override(self):
        config = load_config(None, self._base_args(rate_limit=2.5))
        assert config['crawl']['rate_limit'] == 2.5

    def test_cli_concurrent_override(self):
        config = load_config(None, self._base_args(concurrent=8))
        assert config['crawl']['concurrent_pages'] == 8

    def test_cli_output_prefix(self):
        config = load_config(None, self._base_args(output='my-report'))
        assert config['output']['prefix'] == 'my-report'

    def test_cli_format_single(self):
        config = load_config(None, self._base_args(format='html'))
        assert config['output']['formats'] == ['html']

    def test_cli_format_all(self):
        config = load_config(None, self._base_args(format='all'))
        assert config['output']['formats'] == ['json', 'csv', 'html']

    def test_cli_exclude_patterns(self):
        config = load_config(None, self._base_args(exclude=['/admin.*', '/api/.*']))
        assert config['filters']['exclude_patterns'] == ['/admin.*', '/api/.*']

    def test_cli_include_patterns(self):
        config = load_config(None, self._base_args(include=['/blog/.*']))
        assert config['filters']['include_patterns'] == ['/blog/.*']

    def test_cli_no_resume(self):
        config = load_config(None, self._base_args(no_resume=True))
        assert config['resume']['enabled'] is False

    def test_yaml_config_loaded(self):
        yaml_content = """
crawl:
  max_pages: 250
  max_depth: 5
  rate_limit: 0.5
  concurrent_pages: 5
  timeout: 60
retry:
  max_retries: 2
  retry_delay: 1.0
  retry_on_status: [500, 503]
browser:
  headless: true
  user_agent: "TestBot/1.0"
  viewport: {width: 1280, height: 720}
  javascript_enabled: true
  ignore_https_errors: false
filters:
  respect_robots: true
  exclude_patterns: []
  include_patterns: []
  skip_extensions: [".pdf"]
technology:
  detect_all: true
tags:
  detect_all: true
  custom_patterns: {}
datalayer:
  extract: true
  parse_events: true
  max_events: 50
performance:
  capture_metrics: true
  capture_screenshots: false
  screenshot_format: png
output:
  formats: ["json"]
  prefix: "test-audit"
  save_progress: false
  progress_interval: 5
logging:
  level: "DEBUG"
  log_file: null
  console: false
resume:
  enabled: false
  state_file: "state.json"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config = load_config(f.name, self._base_args())

        os.unlink(f.name)
        assert config['crawl']['max_pages'] == 250
        assert config['output']['formats'] == ['json']

    def test_missing_config_file_uses_defaults(self):
        config = load_config('/nonexistent/config.yaml', self._base_args())
        assert config['crawl']['max_pages'] == 100

    def test_cli_overrides_yaml(self):
        yaml_content = """
crawl:
  max_pages: 250
  max_depth: 5
  rate_limit: 0.5
  concurrent_pages: 5
  timeout: 60
retry:
  max_retries: 2
  retry_delay: 1.0
  retry_on_status: [500]
browser:
  headless: true
  user_agent: "Bot"
  viewport: {width: 1280, height: 720}
  javascript_enabled: true
  ignore_https_errors: false
filters:
  respect_robots: true
  exclude_patterns: []
  include_patterns: []
  skip_extensions: [".pdf"]
technology:
  detect_all: true
tags:
  detect_all: true
  custom_patterns: {}
datalayer:
  extract: true
  parse_events: true
  max_events: 50
performance:
  capture_metrics: true
  capture_screenshots: false
  screenshot_format: png
output:
  formats: ["json"]
  prefix: "test"
  save_progress: false
  progress_interval: 5
logging:
  level: "DEBUG"
  log_file: null
  console: false
resume:
  enabled: false
  state_file: "state.json"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config = load_config(f.name, self._base_args(max_pages=999))

        os.unlink(f.name)
        assert config['crawl']['max_pages'] == 999
