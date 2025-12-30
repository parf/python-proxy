"""Core proxy server implementation."""

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from aiohttp import ClientSession, ClientTimeout, web
from aiohttp.web import Request, Response, StreamResponse

logger = logging.getLogger(__name__)


class ProxyServer:
    """Transparent HTTP proxy server with modification hooks."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        target_host: Optional[str] = None,
        timeout: int = 30,
        before_request_hook: Optional[
            Callable[[Request, dict], Awaitable[Optional[dict]]]
        ] = None,
        after_response_hook: Optional[
            Callable[[Response, bytes], Awaitable[Optional[bytes]]]
        ] = None,
    ):
        """Initialize proxy server.

        Args:
            host: Host to bind the proxy server to
            port: Port to bind the proxy server to
            target_host: Default target host for proxying (can be overridden per request)
            timeout: Request timeout in seconds
            before_request_hook: Async function to modify request before proxying
            after_response_hook: Async function to modify response after proxying
        """
        self.host = host
        self.port = port
        self.target_host = target_host
        self.timeout = ClientTimeout(total=timeout)
        self.before_request_hook = before_request_hook
        self.after_response_hook = after_response_hook
        self.app = web.Application()
        self.app.router.add_route("*", "/{path:.*}", self.handle_request)
        self.session: Optional[ClientSession] = None

    async def start(self):
        """Start the proxy server."""
        self.session = ClientSession(timeout=self.timeout)
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info(f"Proxy server started on {self.host}:{self.port}")
        if self.target_host:
            logger.info(f"Default target: {self.target_host}")

    async def stop(self):
        """Stop the proxy server."""
        if self.session:
            await self.session.close()
        logger.info("Proxy server stopped")

    async def handle_request(self, request: Request) -> StreamResponse:
        """Handle incoming proxy request.

        Supports multiple ways to specify the target:
        - X-Proxy-Server: host or host:port (e.g., "example.com" or "example.com:8080")
        - X-Proxy-Target: full URL (e.g., "http://example.com")
        - Default target_host from configuration
        - Automatic .local domain handling: example.com.local -> example.com

        Args:
            request: Incoming HTTP request

        Returns:
            HTTP response
        """
        # Determine target URL
        proxy_server = request.headers.get("X-Proxy-Server")
        proxy_target = request.headers.get("X-Proxy-Target")
        proxy_host_override = request.headers.get("X-Proxy-Host")

        # Check if request is for a .local domain (automatic routing)
        # Get the requested hostname from the request URL or Host header
        original_host = request.host
        if original_host and isinstance(original_host, str) and ".local" in original_host:
            # Strip .local suffix and any port, route to port 80
            # Format: hostname.local or hostname.local:port → hostname (port 80)
            if original_host.endswith(".local") or ".local:" in original_host:
                # Remove .local suffix
                stripped_host = original_host.replace(".local", "", 1)
                # Remove any port specification - .local requests always go to port 80
                if ":" in stripped_host:
                    stripped_host = stripped_host.split(":")[0]

                logger.info(
                    f"Auto-routing .local domain: {original_host} -> {stripped_host}:80"
                )

                # If no explicit proxy headers, auto-route to stripped hostname
                # Port will default to 80 (set by proxy_server logic below)
                if not proxy_server and not proxy_target:
                    proxy_server = stripped_host

        # Build target URL based on available headers
        if proxy_server:
            # X-Proxy-Server: host or host:port
            if ":" in proxy_server:
                host, port = proxy_server.rsplit(":", 1)
                port = int(port)
            else:
                host = proxy_server
                port = 80

            # Choose scheme based on port
            scheme = "https" if port == 443 else "http"
            port_suffix = f":{port}" if port not in (80, 443) else ""
            target_base = f"{scheme}://{host}{port_suffix}"

        elif proxy_target:
            # X-Proxy-Target: full URL (legacy support)
            target_base = proxy_target.rstrip("/")

        elif self.target_host:
            # Default target from configuration
            target_base = self.target_host.rstrip("/")

        else:
            return web.Response(
                text=(
                    "No target host specified. "
                    "Set X-Proxy-Server, X-Proxy-Target header, or configure default target."
                ),
                status=400,
            )

        # Build full target URL
        path = request.match_info.get("path", "")
        query_string = f"?{request.query_string}" if request.query_string else ""
        target_url = f"{target_base}/{path}{query_string}"

        # Prepare request data
        request_data = {
            "method": request.method,
            "url": target_url,
            "headers": dict(request.headers),
            "data": await request.read(),
        }

        # Remove proxy control headers
        for header in ["X-Proxy-Server", "X-Proxy-Target", "X-Proxy-Host"]:
            request_data["headers"].pop(header, None)

        # Remove Host header (will be set by aiohttp automatically)
        request_data["headers"].pop("Host", None)

        # Apply X-Proxy-Host override if specified
        if proxy_host_override:
            request_data["headers"]["Host"] = proxy_host_override

        # Apply before_request hook
        if self.before_request_hook:
            try:
                modified_data = await self.before_request_hook(request, request_data)
                if modified_data:
                    request_data = modified_data
            except Exception as e:
                logger.error(f"Error in before_request_hook: {e}", exc_info=True)
                return web.Response(text=f"Hook error: {e}", status=500)

        # Forward request to target
        try:
            async with self.session.request(**request_data) as resp:
                response_body = await resp.read()

                # Apply after_response hook
                if self.after_response_hook:
                    try:
                        modified_body = await self.after_response_hook(resp, response_body)
                        if modified_body is not None:
                            response_body = modified_body
                    except Exception as e:
                        logger.error(f"Error in after_response_hook: {e}", exc_info=True)
                        return web.Response(text=f"Hook error: {e}", status=500)

                # Build response
                headers = {k: v for k, v in resp.headers.items()
                          if k.lower() not in ["transfer-encoding", "content-encoding"]}

                return web.Response(
                    body=response_body,
                    status=resp.status,
                    headers=headers
                )

        except asyncio.TimeoutError:
            logger.error(f"Request timeout: {target_url}")
            return web.Response(text="Request timeout", status=504)
        except Exception as e:
            logger.error(f"Proxy error: {e}", exc_info=True)
            return web.Response(text=f"Proxy error: {e}", status=502)

    async def run(self):
        """Run the proxy server indefinitely."""
        await self.start()
        try:
            # Keep running
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await self.stop()
