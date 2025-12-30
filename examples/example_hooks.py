"""Example hooks demonstrating request/response modification.

This file shows various ways to create hooks that modify requests
before they are proxied and responses after they are received.
"""

import logging

logger = logging.getLogger(__name__)


# Example 1: Simple before_request hook using function name
async def before_request(request, request_data):
    """Modify request before proxying.

    Args:
        request: Original aiohttp Request object
        request_data: Dict with keys: method, url, headers, data

    Returns:
        Modified request_data dict or None to leave unchanged
    """
    # Add custom header to all outgoing requests
    request_data["headers"]["X-Proxied-By"] = "python-proxy"

    # Log outgoing request
    logger.info(f"Proxying {request_data['method']} {request_data['url']}")

    return request_data


# Example 2: Simple after_response hook using function name
async def after_response(response, body):
    """Modify response after receiving from target.

    Args:
        response: aiohttp ClientResponse object
        body: Response body as bytes

    Returns:
        Modified body as bytes or None to leave unchanged
    """
    # Log response
    logger.info(f"Received response: {response.status} ({len(body)} bytes)")

    # Only modify HTML responses
    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type:
        # Add a comment to HTML
        html = body.decode("utf-8", errors="ignore")
        modified = html.replace(
            "</body>",
            "<!-- Proxied by python-proxy --></body>"
        )
        return modified.encode("utf-8")

    return body
