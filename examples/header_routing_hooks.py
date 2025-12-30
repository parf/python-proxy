"""Example hooks demonstrating dynamic routing using new headers.

This example shows how to use X-Proxy-Server and X-Proxy-Host headers
for advanced routing scenarios.
"""

import logging

from python_proxy.hooks import before_request

logger = logging.getLogger(__name__)


@before_request
async def route_by_path(request, request_data):
    """Route requests to different backends based on URL path.

    This example shows how hooks can dynamically set the proxy target
    based on the request path, useful for multi-backend setups.
    """
    url = request_data["url"]

    # Route API requests to API server
    if "/api/" in url:
        logger.info("Routing API request to api.internal:8080")
        # Modify the URL to point to the API backend
        request_data["url"] = url.replace(
            request_data["url"].split("/")[2],  # Current host
            "api.internal:8080",
        )
        # Set Host header for backend
        request_data["headers"]["Host"] = "api.myapp.com"

    # Route static files to CDN
    elif url.endswith((".js", ".css", ".jpg", ".png", ".gif")):
        logger.info("Routing static file to cdn.internal:9000")
        request_data["url"] = url.replace(
            request_data["url"].split("/")[2],
            "cdn.internal:9000",
        )

    # Route admin requests to admin server
    elif "/admin/" in url:
        logger.info("Routing admin request to admin.internal:8081")
        request_data["url"] = url.replace(
            request_data["url"].split("/")[2],
            "admin.internal:8081",
        )
        request_data["headers"]["Host"] = "admin.myapp.com"

    return request_data


@before_request
async def load_balancer(request, request_data):
    """Simple round-robin load balancer.

    Distributes requests across multiple backend servers.
    """
    import random

    # List of backend servers
    backends = [
        "backend1.internal:8080",
        "backend2.internal:8080",
        "backend3.internal:8080",
    ]

    # Pick a random backend (in production, use proper round-robin)
    backend = random.choice(backends)

    # Get the original URL parts
    url_parts = request_data["url"].split("/", 3)
    path = url_parts[3] if len(url_parts) > 3 else ""

    # Rebuild URL with selected backend
    scheme = "https" if ":443" in backend else "http"
    request_data["url"] = f"{scheme}://{backend}/{path}"

    logger.info(f"Load balancing request to {backend}")

    return request_data


@before_request
async def add_backend_auth(request, request_data):
    """Add authentication for backend servers.

    This shows how to add authentication headers that are different
    from what the client sent.
    """
    # Extract which backend we're connecting to
    url = request_data["url"]

    # Add backend-specific authentication
    if "api.internal" in url:
        request_data["headers"]["X-Internal-Auth"] = "secret-api-token"
    elif "admin.internal" in url:
        request_data["headers"]["X-Internal-Auth"] = "secret-admin-token"

    return request_data
