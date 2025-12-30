"""Tests for configuration module."""

import os
import tempfile

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
