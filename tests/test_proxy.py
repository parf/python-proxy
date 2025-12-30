"""Tests for proxy module."""

from aiohttp import ClientSession, web
from aiohttp.test_utils import AioHTTPTestCase, unused_port

from python_proxy.proxy import ProxyServer


class TestProxyServer(AioHTTPTestCase):
    """Test cases for ProxyServer."""

    async def get_application(self):
        """Create test application."""
        # Create a simple test backend server
        app = web.Application()

        async def hello(request):
            return web.Response(text="Hello, World!")

        async def echo_headers(request):
            headers = dict(request.headers)
            return web.json_response(headers)

        app.router.add_get("/hello", hello)
        app.router.add_get("/echo-headers", echo_headers)

        return app

    async def test_proxy_basic_request(self):
        """Test basic proxy functionality."""
        # Get the test server URL
        backend_url = f"http://{self.server.host}:{self.server.port}"

        # Create proxy server with unused port
        port = unused_port()
        proxy = ProxyServer(host="127.0.0.1", port=port, target_host=backend_url)
        await proxy.start()

        try:
            # Make request directly to backend to verify it works
            async with ClientSession() as session:
                async with session.get(f"{backend_url}/hello") as resp:
                    text = await resp.text()
                    assert text == "Hello, World!"
                    assert resp.status == 200
        finally:
            await proxy.stop()

    async def test_proxy_missing_target(self):
        """Test proxy without target host."""
        # Use unused port to avoid conflicts
        port = unused_port()
        proxy = ProxyServer(host="127.0.0.1", port=port)
        await proxy.start()

        try:
            # Create mock request object
            from unittest.mock import MagicMock

            mock_request = MagicMock()
            mock_request.host = None  # No host specified
            mock_request.headers = {}
            mock_request.match_info = {"path": "test"}
            mock_request.method = "GET"
            mock_request.query_string = ""

            async def mock_read():
                return b""

            mock_request.read = mock_read

            # Call handle_request directly
            response = await proxy.handle_request(mock_request)
            assert response.status == 400
            assert "X-Proxy-Server" in response.text
        finally:
            await proxy.stop()

    async def test_proxy_server_header_with_port(self):
        """Test X-Proxy-Server header with explicit port."""
        from unittest.mock import MagicMock

        port = unused_port()
        proxy = ProxyServer(host="127.0.0.1", port=port)
        await proxy.start()

        try:
            mock_request = MagicMock()
            mock_request.headers = {
                "X-Proxy-Server": f"{self.server.host}:{self.server.port}"
            }
            mock_request.match_info = {"path": "hello"}
            mock_request.method = "GET"
            mock_request.query_string = ""

            async def mock_read():
                return b""

            mock_request.read = mock_read

            # Call handle_request directly
            response = await proxy.handle_request(mock_request)
            text = response.body.decode()
            assert response.status == 200
            assert "Hello, World!" in text
        finally:
            await proxy.stop()

    async def test_proxy_server_header_without_port(self):
        """Test X-Proxy-Server header without port (defaults to 80)."""
        from unittest.mock import MagicMock

        port = unused_port()
        proxy = ProxyServer(host="127.0.0.1", port=port)
        await proxy.start()

        try:
            mock_request = MagicMock()
            mock_request.headers = {"X-Proxy-Server": "example.com"}
            mock_request.match_info = {"path": "test"}
            mock_request.method = "GET"
            mock_request.query_string = ""

            async def mock_read():
                return b""

            mock_request.read = mock_read

            # Mock the session.request to verify URL construction
            captured_url = None

            class MockResponse:
                def __init__(self):
                    self.status = 200
                    self.headers = {}

                async def read(self):
                    return b"test"

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            def mock_session_request(*args, **kwargs):
                nonlocal captured_url
                captured_url = kwargs.get("url")
                return MockResponse()

            proxy.session.request = mock_session_request

            response = await proxy.handle_request(mock_request)
            # Verify URL was constructed with http:// and no port suffix
            assert captured_url == "http://example.com/test"
            assert response.status == 200
        finally:
            await proxy.stop()

    async def test_proxy_server_header_https_port(self):
        """Test X-Proxy-Server header with port 443 uses https."""
        from unittest.mock import MagicMock

        port = unused_port()
        proxy = ProxyServer(host="127.0.0.1", port=port)
        await proxy.start()

        try:
            mock_request = MagicMock()
            mock_request.headers = {"X-Proxy-Server": "example.com:443"}
            mock_request.match_info = {"path": "test"}
            mock_request.method = "GET"
            mock_request.query_string = ""

            async def mock_read():
                return b""

            mock_request.read = mock_read

            # Mock the session.request to capture the URL
            captured_url = None

            class MockResponse:
                def __init__(self):
                    self.status = 200
                    self.headers = {}

                async def read(self):
                    return b"test"

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            def mock_session_request(*args, **kwargs):
                nonlocal captured_url
                captured_url = kwargs.get("url")
                return MockResponse()

            proxy.session.request = mock_session_request

            await proxy.handle_request(mock_request)
            assert captured_url.startswith("https://")
            assert "example.com" in captured_url
        finally:
            await proxy.stop()

    async def test_proxy_host_header_override(self):
        """Test X-Proxy-Host header overrides Host sent to backend."""
        from unittest.mock import MagicMock

        port = unused_port()
        proxy = ProxyServer(host="127.0.0.1", port=port)
        await proxy.start()

        try:
            mock_request = MagicMock()
            mock_request.headers = {
                "X-Proxy-Server": f"{self.server.host}:{self.server.port}",
                "X-Proxy-Host": "custom-host.example.com",
            }
            mock_request.match_info = {"path": "echo-headers"}
            mock_request.method = "GET"
            mock_request.query_string = ""

            async def mock_read():
                return b""

            mock_request.read = mock_read

            response = await proxy.handle_request(mock_request)
            assert response.status == 200

            # Parse the JSON response to check the Host header
            import json

            body = response.body.decode()
            headers = json.loads(body)
            assert headers.get("Host") == "custom-host.example.com"
        finally:
            await proxy.stop()

    async def test_local_domain_stripping(self):
        """Test automatic .local domain suffix stripping."""
        from unittest.mock import MagicMock

        port = unused_port()
        proxy = ProxyServer(host="127.0.0.1", port=port)
        await proxy.start()

        try:
            mock_request = MagicMock()
            mock_request.host = "example.com.local"
            mock_request.headers = {}
            mock_request.match_info = {"path": "test"}
            mock_request.method = "GET"
            mock_request.query_string = ""

            async def mock_read():
                return b""

            mock_request.read = mock_read

            # Mock the session.request to verify URL construction
            captured_url = None

            class MockResponse:
                def __init__(self):
                    self.status = 200
                    self.headers = {}

                async def read(self):
                    return b"test"

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            def mock_session_request(*args, **kwargs):
                nonlocal captured_url
                captured_url = kwargs.get("url")
                return MockResponse()

            proxy.session.request = mock_session_request

            response = await proxy.handle_request(mock_request)
            # Verify .local was stripped and routed to example.com
            assert "example.com/test" in captured_url
            assert ".local" not in captured_url
            assert response.status == 200
        finally:
            await proxy.stop()

    async def test_local_domain_with_port(self):
        """Test .local domain stripping - port is stripped and defaults to 80."""
        from unittest.mock import MagicMock

        port = unused_port()
        proxy = ProxyServer(host="127.0.0.1", port=port)
        await proxy.start()

        try:
            mock_request = MagicMock()
            mock_request.host = "api.example.com.local:8080"
            mock_request.headers = {}
            mock_request.match_info = {"path": "api/data"}
            mock_request.method = "GET"
            mock_request.query_string = ""

            async def mock_read():
                return b""

            mock_request.read = mock_read

            # Mock the session.request to verify URL construction
            captured_url = None

            class MockResponse:
                def __init__(self):
                    self.status = 200
                    self.headers = {}

                async def read(self):
                    return b"test"

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            def mock_session_request(*args, **kwargs):
                nonlocal captured_url
                captured_url = kwargs.get("url")
                return MockResponse()

            proxy.session.request = mock_session_request

            response = await proxy.handle_request(mock_request)
            # Verify .local and port were stripped, defaults to port 80
            assert "api.example.com/api" in captured_url
            assert ":8080" not in captured_url
            assert ".local" not in captured_url
            # Should use default port 80 (http://api.example.com/api)
            assert captured_url == "http://api.example.com/api/data"
            assert response.status == 200
        finally:
            await proxy.stop()

    async def test_local_domain_with_explicit_header(self):
        """Test .local domain doesn't override explicit X-Proxy-Server header."""
        from unittest.mock import MagicMock

        port = unused_port()
        proxy = ProxyServer(host="127.0.0.1", port=port)
        await proxy.start()

        try:
            mock_request = MagicMock()
            mock_request.host = "example.com.local"
            # Explicit header should take precedence
            mock_request.headers = {"X-Proxy-Server": "other.com"}
            mock_request.match_info = {"path": "test"}
            mock_request.method = "GET"
            mock_request.query_string = ""

            async def mock_read():
                return b""

            mock_request.read = mock_read

            # Mock the session.request to verify URL construction
            captured_url = None

            class MockResponse:
                def __init__(self):
                    self.status = 200
                    self.headers = {}

                async def read(self):
                    return b"test"

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

            def mock_session_request(*args, **kwargs):
                nonlocal captured_url
                captured_url = kwargs.get("url")
                return MockResponse()

            proxy.session.request = mock_session_request

            response = await proxy.handle_request(mock_request)
            # Verify explicit header was used, not .local stripping
            assert "other.com/test" in captured_url
            assert "example.com" not in captured_url
            assert response.status == 200
        finally:
            await proxy.stop()
