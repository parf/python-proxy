"""Hook system for request/response modification."""

import fnmatch
import importlib.util
import inspect
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from aiohttp.web import Request, Response

from python_proxy.builtin_hooks import BUILTIN_POST_HOOKS, BUILTIN_PRE_HOOKS

logger = logging.getLogger(__name__)


class HookManager:
    """Manager for loading and executing hooks."""

    def __init__(
        self,
        hooks_dir: Optional[str] = None,
        hook_mappings: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ):
        """Initialize hook manager.

        Args:
            hooks_dir: Directory containing hook modules
            hook_mappings: Configuration-based hook mappings
        """
        self.hooks_dir = Path(hooks_dir) if hooks_dir else None
        self.before_request_hooks: List[Callable] = []
        self.after_response_hooks: List[Callable] = []

        # Configuration-based hooks
        self.hook_mappings = hook_mappings or {"pre_hooks": [], "post_hooks": []}
        self.pre_hook_configs = self.hook_mappings.get("pre_hooks", [])
        self.post_hook_configs = self.hook_mappings.get("post_hooks", [])

    def load_hooks(self):
        """Load all hooks from the hooks directory."""
        if not self.hooks_dir or not self.hooks_dir.exists():
            logger.warning(f"Hooks directory not found: {self.hooks_dir}")
            return

        logger.info(f"Loading hooks from: {self.hooks_dir}")

        # Load all Python files in hooks directory
        for hook_file in self.hooks_dir.glob("*.py"):
            if hook_file.name.startswith("_"):
                continue

            try:
                self._load_hook_file(hook_file)
            except Exception as e:
                logger.error(f"Error loading hook {hook_file}: {e}", exc_info=True)

        logger.info(
            f"Loaded {len(self.before_request_hooks)} before_request hooks and "
            f"{len(self.after_response_hooks)} after_response hooks"
        )

    def _load_hook_file(self, hook_file: Path):
        """Load hooks from a single file.

        Args:
            hook_file: Path to hook file
        """
        # Load module
        spec = importlib.util.spec_from_file_location(hook_file.stem, hook_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find hook functions
        for name, obj in inspect.getmembers(module):
            if not inspect.isfunction(obj):
                continue

            # Check for before_request hooks
            if name == "before_request" or getattr(obj, "_before_request_hook", False):
                self.before_request_hooks.append(obj)
                logger.debug(f"Registered before_request hook: {hook_file.stem}.{name}")

            # Check for after_response hooks
            if name == "after_response" or getattr(obj, "_after_response_hook", False):
                self.after_response_hooks.append(obj)
                logger.debug(f"Registered after_response hook: {hook_file.stem}.{name}")

    def _match_hostname(self, pattern: str, hostname: str) -> bool:
        """Match hostname against pattern (supports wildcards).

        Args:
            pattern: Hostname pattern (e.g., "example.com", "*.example.com", "*")
            hostname: Actual hostname to match

        Returns:
            True if hostname matches pattern
        """
        if pattern == "*":
            return True
        return fnmatch.fnmatch(hostname.lower(), pattern.lower())

    def _match_url_pattern(self, pattern: str, path: str) -> bool:
        """Match URL path against pattern (supports glob and regex).

        Args:
            pattern: URL pattern (e.g., "/api/*", "/users/*/profile", regex:^/api/v[0-9]+/)
            path: Actual URL path to match

        Returns:
            True if path matches pattern
        """
        # If pattern starts with "regex:", use regex matching
        if pattern.startswith("regex:"):
            regex_pattern = pattern[6:]  # Remove "regex:" prefix
            try:
                return bool(re.match(regex_pattern, path))
            except re.error as e:
                logger.error(f"Invalid regex pattern {regex_pattern}: {e}")
                return False

        # Otherwise use glob matching
        return fnmatch.fnmatch(path, pattern)

    def find_matching_pre_hook(
        self, hostname: str, path: str
    ) -> Optional[tuple[Callable, Dict[str, Any]]]:
        """Find first matching pre-hook configuration.

        Args:
            hostname: Request hostname
            path: Request path

        Returns:
            Tuple of (hook_function, params) or None if no match
        """
        for config in self.pre_hook_configs:
            pattern_hostname = config.get("hostname", "*")
            pattern_url = config.get("url_pattern", "*")
            hook_name = config.get("hook")

            if not hook_name:
                logger.warning(f"Pre-hook config missing 'hook' field: {config}")
                continue

            # Check if hostname and URL match
            if self._match_hostname(pattern_hostname, hostname) and self._match_url_pattern(
                pattern_url, path
            ):
                # Get hook function from built-in hooks
                hook_func = BUILTIN_PRE_HOOKS.get(hook_name)
                if hook_func:
                    params = config.get("params", {})
                    logger.debug(
                        f"Matched pre-hook: {hook_name} for {hostname}{path}"
                    )
                    return (hook_func, params)
                else:
                    logger.warning(f"Pre-hook not found: {hook_name}")

        return None

    def find_matching_post_hooks(
        self, hostname: str, path: str
    ) -> List[tuple[Callable, Dict[str, Any]]]:
        """Find all matching post-hook configurations.

        Args:
            hostname: Request hostname
            path: Request path

        Returns:
            List of (hook_function, params) tuples
        """
        matching_hooks = []

        for config in self.post_hook_configs:
            pattern_hostname = config.get("hostname", "*")
            pattern_url = config.get("url_pattern", "*")
            hook_name = config.get("hook")

            if not hook_name:
                logger.warning(f"Post-hook config missing 'hook' field: {config}")
                continue

            # Check if hostname and URL match
            if self._match_hostname(pattern_hostname, hostname) and self._match_url_pattern(
                pattern_url, path
            ):
                # Get hook function from built-in hooks
                hook_func = BUILTIN_POST_HOOKS.get(hook_name)
                if hook_func:
                    params = config.get("params", {})
                    logger.debug(
                        f"Matched post-hook: {hook_name} for {hostname}{path}"
                    )
                    matching_hooks.append((hook_func, params))
                else:
                    logger.warning(f"Post-hook not found: {hook_name}")

        return matching_hooks

    async def execute_before_request(
        self, request: Request, request_data: Dict
    ) -> Optional[Dict | Response]:
        """Execute all before_request hooks including configuration-based pre-hooks.

        Args:
            request: Original aiohttp request
            request_data: Request data dict (method, url, headers, data)

        Returns:
            Modified request data, Response (early return), or None
        """
        # First check configuration-based pre-hooks
        # These can return a Response to skip backend call
        if request is not None:
            hostname = request.host
            path = request.path

            matched_pre_hook = self.find_matching_pre_hook(hostname, path)
            if matched_pre_hook:
                hook_func, params = matched_pre_hook
                try:
                    result = await hook_func(request, request_data, params)
                    # If result is a Response, return it immediately (skip backend)
                    if isinstance(result, Response):
                        logger.info("Pre-hook returned early response, skipping backend")
                        return result
                except Exception as e:
                    logger.error(f"Error in pre-hook {hook_func.__name__}: {e}", exc_info=True)

        # Then execute regular before_request hooks
        for hook in self.before_request_hooks:
            try:
                if inspect.iscoroutinefunction(hook):
                    result = await hook(request, request_data)
                else:
                    result = hook(request, request_data)

                if result is not None:
                    request_data = result

            except Exception as e:
                logger.error(f"Error in before_request hook {hook.__name__}: {e}", exc_info=True)

        return request_data

    async def execute_after_response(
        self,
        response: Response,
        body: bytes,
        hostname: Optional[str] = None,
        path: Optional[str] = None,
    ) -> Optional[bytes]:
        """Execute all after_response hooks including configuration-based post-hooks.

        Args:
            response: aiohttp response object
            body: Response body bytes
            hostname: Request hostname (for matching post-hooks), optional
            path: Request path (for matching post-hooks), optional

        Returns:
            Modified response body or None
        """
        # First execute regular after_response hooks
        for hook in self.after_response_hooks:
            try:
                if inspect.iscoroutinefunction(hook):
                    result = await hook(response, body)
                else:
                    result = hook(response, body)

                if result is not None:
                    body = result

            except Exception as e:
                logger.error(f"Error in after_response hook {hook.__name__}: {e}", exc_info=True)

        # Then execute configuration-based post-hooks (if hostname and path provided)
        if hostname and path:
            matched_post_hooks = self.find_matching_post_hooks(hostname, path)
            for hook_func, params in matched_post_hooks:
                try:
                    result = await hook_func(response, body, params)
                    if result is not None:
                        body = result
                except Exception as e:
                    logger.error(f"Error in post-hook {hook_func.__name__}: {e}", exc_info=True)

        return body


def before_request(func: Callable) -> Callable:
    """Decorator to mark a function as a before_request hook.

    Example:
        @before_request
        async def my_hook(request, request_data):
            # Modify request_data
            return request_data
    """
    func._before_request_hook = True
    return func


def after_response(func: Callable) -> Callable:
    """Decorator to mark a function as an after_response hook.

    Example:
        @after_response
        async def my_hook(response, body):
            # Modify body
            return body
    """
    func._after_response_hook = True
    return func
