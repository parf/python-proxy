"""Configuration handling for proxy server."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class Config:
    """Configuration container for proxy server."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        target_host: Optional[str] = None,
        timeout: int = 30,
        hooks_dir: Optional[str] = None,
        log_level: str = "INFO",
        hook_mappings: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ):
        """Initialize configuration.

        Args:
            host: Host to bind the proxy server to
            port: Port to bind the proxy server to
            target_host: Default target host for proxying
            timeout: Request timeout in seconds
            hooks_dir: Directory containing hook modules
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            hook_mappings: Hook routing configuration with pre_hooks and post_hooks
        """
        self.host = host
        self.port = port
        self.target_host = target_host
        self.timeout = timeout
        self.hooks_dir = hooks_dir
        self.log_level = log_level
        self.hook_mappings = hook_mappings or {"pre_hooks": [], "post_hooks": []}

    @classmethod
    def from_file(cls, config_path: str) -> "Config":
        """Load configuration from YAML file.

        Args:
            config_path: Path to configuration file

        Returns:
            Config instance
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables.

        Returns:
            Config instance
        """
        return cls(
            host=os.getenv("PROXY_HOST", "0.0.0.0"),
            port=int(os.getenv("PROXY_PORT", "8080")),
            target_host=os.getenv("PROXY_TARGET"),
            timeout=int(os.getenv("PROXY_TIMEOUT", "30")),
            hooks_dir=os.getenv("PROXY_HOOKS_DIR"),
            log_level=os.getenv("PROXY_LOG_LEVEL", "INFO"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "host": self.host,
            "port": self.port,
            "target_host": self.target_host,
            "timeout": self.timeout,
            "hooks_dir": self.hooks_dir,
            "log_level": self.log_level,
            "hook_mappings": self.hook_mappings,
        }
