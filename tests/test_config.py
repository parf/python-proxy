"""Tests for configuration module."""

import os
import tempfile
from pathlib import Path

import pytest

from python_proxy.config import Config


def test_config_defaults():
    """Test default configuration values."""
    config = Config()
    assert config.host == "0.0.0.0"
    assert config.port == 8080
    assert config.target_host is None
    assert config.timeout == 30
    assert config.hooks_dir is None
    assert config.log_level == "INFO"


def test_config_custom_values():
    """Test configuration with custom values."""
    config = Config(
        host="127.0.0.1",
        port=3128,
        target_host="http://example.com",
        timeout=60,
        hooks_dir="./hooks",
        log_level="DEBUG"
    )
    assert config.host == "127.0.0.1"
    assert config.port == 3128
    assert config.target_host == "http://example.com"
    assert config.timeout == 60
    assert config.hooks_dir == "./hooks"
    assert config.log_level == "DEBUG"


def test_config_from_env(monkeypatch):
    """Test loading configuration from environment variables."""
    monkeypatch.setenv("PROXY_HOST", "192.168.1.1")
    monkeypatch.setenv("PROXY_PORT", "9090")
    monkeypatch.setenv("PROXY_TARGET", "http://test.com")
    monkeypatch.setenv("PROXY_TIMEOUT", "45")
    monkeypatch.setenv("PROXY_HOOKS_DIR", "/tmp/hooks")
    monkeypatch.setenv("PROXY_LOG_LEVEL", "WARNING")

    config = Config.from_env()
    assert config.host == "192.168.1.1"
    assert config.port == 9090
    assert config.target_host == "http://test.com"
    assert config.timeout == 45
    assert config.hooks_dir == "/tmp/hooks"
    assert config.log_level == "WARNING"


def test_config_from_file():
    """Test loading configuration from YAML file."""
    yaml_content = """
host: "10.0.0.1"
port: 7777
target_host: "http://yaml.com"
timeout: 20
hooks_dir: "./yaml-hooks"
log_level: "ERROR"
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        config = Config.from_file(temp_path)
        assert config.host == "10.0.0.1"
        assert config.port == 7777
        assert config.target_host == "http://yaml.com"
        assert config.timeout == 20
        assert config.hooks_dir == "./yaml-hooks"
        assert config.log_level == "ERROR"
    finally:
        os.unlink(temp_path)


def test_config_from_nonexistent_file():
    """Test loading from nonexistent file raises error."""
    with pytest.raises(FileNotFoundError):
        Config.from_file("/nonexistent/config.yaml")


def test_config_to_dict():
    """Test converting configuration to dictionary."""
    config = Config(
        host="1.2.3.4",
        port=1234,
        target_host="http://dict.com"
    )
    config_dict = config.to_dict()

    assert config_dict["host"] == "1.2.3.4"
    assert config_dict["port"] == 1234
    assert config_dict["target_host"] == "http://dict.com"
    assert config_dict["timeout"] == 30
    assert config_dict["hooks_dir"] is None
    assert config_dict["log_level"] == "INFO"


def test_config_with_hook_includes():
    """Test loading configuration with hostname-specific includes."""
    # Create a temporary directory for test files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create include file for example.com
        example_hooks_content = """
- url_pattern: "/old-page"
  hook: "redirect_301"
  params:
    location: "/new-page"

- url_pattern: "/deleted/*"
  hook: "gone_410"
  params:
    message: "Content removed"
"""
        example_hooks_path = tmpdir_path / "example-hooks.yaml"
        example_hooks_path.write_text(example_hooks_content)

        # Create include file for api.example.com
        api_hooks_content = """
- url_pattern: "/v1/*"
  hook: "url_rewrite"
  params:
    pattern: '"/v1/users/([^/]+)"'
    replacement: '"/v1/users?id=$1"'
"""
        api_hooks_path = tmpdir_path / "api-hooks.yaml"
        api_hooks_path.write_text(api_hooks_content)

        # Create main config file with includes
        config_content = f"""
host: "0.0.0.0"
port: 8080
log_level: "INFO"

hook_mappings:
  pre_hooks:
    - hostname: "example.com"
      include: "example-hooks.yaml"

    - hostname: "other.com"
      url_pattern: "/inline"
      hook: "not_found_404"
      params:
        message: "Not found"

  post_hooks:
    - hostname: "api.example.com"
      include: "api-hooks.yaml"
"""
        config_path = tmpdir_path / "config.yaml"
        config_path.write_text(config_content)

        # Load config
        config = Config.from_file(str(config_path))

        # Verify pre_hooks were expanded
        assert len(config.hook_mappings["pre_hooks"]) == 3  # 2 from include + 1 inline

        # First two should be from example.com include
        assert config.hook_mappings["pre_hooks"][0]["hostname"] == "example.com"
        assert config.hook_mappings["pre_hooks"][0]["url_pattern"] == "/old-page"
        assert config.hook_mappings["pre_hooks"][0]["hook"] == "redirect_301"

        assert config.hook_mappings["pre_hooks"][1]["hostname"] == "example.com"
        assert config.hook_mappings["pre_hooks"][1]["url_pattern"] == "/deleted/*"
        assert config.hook_mappings["pre_hooks"][1]["hook"] == "gone_410"

        # Third should be inline hook
        assert config.hook_mappings["pre_hooks"][2]["hostname"] == "other.com"
        assert config.hook_mappings["pre_hooks"][2]["url_pattern"] == "/inline"

        # Verify post_hooks were expanded
        assert len(config.hook_mappings["post_hooks"]) == 1
        assert config.hook_mappings["post_hooks"][0]["hostname"] == "api.example.com"
        assert config.hook_mappings["post_hooks"][0]["url_pattern"] == "/v1/*"
        assert config.hook_mappings["post_hooks"][0]["hook"] == "url_rewrite"


def test_config_include_with_absolute_path():
    """Test include with absolute path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create include file in a different directory
        include_dir = tmpdir_path / "includes"
        include_dir.mkdir()

        include_content = """
- url_pattern: "/*"
  hook: "text_rewrite"
  params:
    pattern: "old"
    replacement: "new"
"""
        include_path = include_dir / "hooks.yaml"
        include_path.write_text(include_content)

        # Create config with absolute path
        config_content = f"""
hook_mappings:
  pre_hooks:
    - hostname: "example.com"
      include: "{include_path}"
"""
        config_path = tmpdir_path / "config.yaml"
        config_path.write_text(config_content)

        config = Config.from_file(str(config_path))

        assert len(config.hook_mappings["pre_hooks"]) == 1
        assert config.hook_mappings["pre_hooks"][0]["hostname"] == "example.com"
        assert config.hook_mappings["pre_hooks"][0]["hook"] == "text_rewrite"


def test_config_include_file_not_found():
    """Test that missing include file logs error but doesn't crash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        config_content = """
hook_mappings:
  pre_hooks:
    - hostname: "example.com"
      include: "nonexistent.yaml"

    - hostname: "other.com"
      url_pattern: "/*"
      hook: "redirect_301"
      params:
        location: "/"
"""
        config_path = tmpdir_path / "config.yaml"
        config_path.write_text(config_content)

        # Should not raise exception, but log error and continue
        config = Config.from_file(str(config_path))

        # Only the second hook should be loaded
        assert len(config.hook_mappings["pre_hooks"]) == 1
        assert config.hook_mappings["pre_hooks"][0]["hostname"] == "other.com"


def test_config_include_preserves_existing_hostname():
    """Test that hooks with existing hostname in include file keep it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create include with hook that specifies its own hostname
        include_content = """
- hostname: "override.com"
  url_pattern: "/test"
  hook: "redirect_301"
  params:
    location: "/redirected"
"""
        include_path = tmpdir_path / "hooks.yaml"
        include_path.write_text(include_content)

        config_content = f"""
hook_mappings:
  pre_hooks:
    - hostname: "example.com"
      include: "hooks.yaml"
"""
        config_path = tmpdir_path / "config.yaml"
        config_path.write_text(config_content)

        config = Config.from_file(str(config_path))

        # Hook should keep its original hostname
        assert config.hook_mappings["pre_hooks"][0]["hostname"] == "override.com"
