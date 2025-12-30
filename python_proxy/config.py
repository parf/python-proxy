"""Configuration handling for proxy server.

Copyright (C) 2025 Sergey Porfiriev <parf@difive.com>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


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
    def _process_hook_includes(
        cls, hooks: List[Dict[str, Any]], config_dir: Path, hook_type: str
    ) -> List[Dict[str, Any]]:
        """Process include directives in hook configurations.

        Args:
            hooks: List of hook configurations
            config_dir: Directory containing the main config file
            hook_type: Type of hooks (pre_hooks or post_hooks) for logging

        Returns:
            Expanded list of hooks with includes resolved
        """
        expanded_hooks = []

        for hook in hooks:
            # Check if this is an include directive
            if "include" in hook and "hostname" in hook:
                hostname = hook["hostname"]
                include_file = hook["include"]

                # Resolve include path (relative to config file)
                if not Path(include_file).is_absolute():
                    include_path = config_dir / include_file
                else:
                    include_path = Path(include_file)

                # Load included file
                try:
                    logger.info(
                        f"Loading {hook_type} for hostname '{hostname}' from {include_path}"
                    )
                    with open(include_path) as f:
                        included_hooks = yaml.safe_load(f)

                    if not isinstance(included_hooks, list):
                        logger.error(
                            f"Include file {include_path} must contain a list of hooks"
                        )
                        continue

                    # Add hostname to each hook from included file
                    for included_hook in included_hooks:
                        if not isinstance(included_hook, dict):
                            logger.warning(
                                f"Skipping invalid hook in {include_path}: {included_hook}"
                            )
                            continue

                        # Add hostname if not already specified
                        if "hostname" not in included_hook:
                            included_hook["hostname"] = hostname
                        expanded_hooks.append(included_hook)

                    logger.info(
                        f"Loaded {len(included_hooks)} {hook_type} for '{hostname}'"
                    )

                except FileNotFoundError:
                    logger.error(
                        f"Include file not found: {include_path} (referenced in {hook_type})"
                    )
                except yaml.YAMLError as e:
                    logger.error(f"Error parsing include file {include_path}: {e}")
                except Exception as e:
                    logger.error(f"Error loading include file {include_path}: {e}")
            else:
                # Regular hook, add as-is
                expanded_hooks.append(hook)

        return expanded_hooks

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

        config_dir = path.parent

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        # Process includes in hook_mappings
        if "hook_mappings" in data:
            hook_mappings = data["hook_mappings"]

            # Process pre_hooks includes
            if "pre_hooks" in hook_mappings:
                hook_mappings["pre_hooks"] = cls._process_hook_includes(
                    hook_mappings["pre_hooks"], config_dir, "pre_hooks"
                )

            # Process post_hooks includes
            if "post_hooks" in hook_mappings:
                hook_mappings["post_hooks"] = cls._process_hook_includes(
                    hook_mappings["post_hooks"], config_dir, "post_hooks"
                )

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
