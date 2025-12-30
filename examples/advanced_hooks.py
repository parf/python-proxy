"""Advanced hook examples showing more complex modifications."""

import json

from python_proxy.hooks import after_response, before_request


@before_request
async def add_auth_header(request, request_data):
    """Add authentication header to requests for specific domains."""
    url = request_data["url"]

    if "api.example.com" in url:
        request_data["headers"]["Authorization"] = "Bearer YOUR_TOKEN_HERE"

    return request_data


@before_request
async def modify_query_params(request, request_data):
    """Modify URL query parameters before proxying."""
    url = request_data["url"]

    # Example: Add tracking parameter
    if "?" in url:
        request_data["url"] = f"{url}&source=proxy"
    else:
        request_data["url"] = f"{url}?source=proxy"

    return request_data


@after_response
async def inject_javascript(response, body):
    """Inject JavaScript into HTML pages."""
    content_type = response.headers.get("Content-Type", "")

    if "text/html" in content_type:
        html = body.decode("utf-8", errors="ignore")

        # Inject script before closing head tag
        script = """
        <script>
            console.log('This page was proxied through python-proxy');
        </script>
        """

        if "</head>" in html:
            html = html.replace("</head>", f"{script}</head>")
            return html.encode("utf-8")

    return body


@after_response
async def modify_json_response(response, body):
    """Modify JSON responses."""
    content_type = response.headers.get("Content-Type", "")

    if "application/json" in content_type:
        try:
            data = json.loads(body)

            # Add custom field
            data["_proxied"] = True

            return json.dumps(data).encode("utf-8")
        except json.JSONDecodeError:
            pass

    return body


@after_response
async def replace_text(response, body):
    """Replace text in responses."""
    content_type = response.headers.get("Content-Type", "")

    if "text/" in content_type:
        text = body.decode("utf-8", errors="ignore")

        # Example: Replace all occurrences of a domain
        text = text.replace("example.com", "example.org")

        return text.encode("utf-8")

    return body
