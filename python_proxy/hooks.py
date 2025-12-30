"""Hook system for request/response modification."""

import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional

from aiohttp.web import Request, Response

logger = logging.getLogger(__name__)


class HookManager:
    """Manager for loading and executing hooks."""

    def __init__(self, hooks_dir: Optional[str] = None):
        """Initialize hook manager.

        Args:
            hooks_dir: Directory containing hook modules
        """
        self.hooks_dir = Path(hooks_dir) if hooks_dir else None
        self.before_request_hooks: List[Callable] = []
        self.after_response_hooks: List[Callable] = []

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

    async def execute_before_request(
        self, request: Request, request_data: Dict
    ) -> Optional[Dict]:
        """Execute all before_request hooks.

        Args:
            request: Original aiohttp request
            request_data: Request data dict (method, url, headers, data)

        Returns:
            Modified request data or None
        """
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
        self, response: Response, body: bytes
    ) -> Optional[bytes]:
        """Execute all after_response hooks.

        Args:
            response: aiohttp response object
            body: Response body bytes

        Returns:
            Modified response body or None
        """
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
