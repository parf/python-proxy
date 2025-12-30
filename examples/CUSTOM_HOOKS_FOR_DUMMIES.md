# Creating Custom Python Hooks - For Beginners

A step-by-step guide to writing your own custom hooks for python-proxy. No advanced Python knowledge required!

## Table of Contents

1. [What Are Hooks?](#what-are-hooks)
2. [When to Use Custom Hooks vs Config Hooks](#when-to-use-custom-hooks-vs-config-hooks)
3. [Setting Up](#setting-up)
4. [Your First Hook](#your-first-hook)
5. [Before Request Hooks](#before-request-hooks)
6. [After Response Hooks](#after-response-hooks)
7. [Using Hook Decorators](#using-hook-decorators)
8. [Real-World Examples](#real-world-examples)
9. [Testing Your Hooks](#testing-your-hooks)
10. [Troubleshooting](#troubleshooting)
11. [Next Steps](#next-steps)

## What Are Hooks?

Hooks are Python functions that let you modify HTTP requests and responses as they pass through the proxy. Think of them as checkpoints where you can inspect and change the traffic.

**Two types of hooks:**
- **Before Request Hooks**: Run before the proxy forwards the request to the backend
- **After Response Hooks**: Run after the proxy receives the response from the backend

**Example use cases:**
- Add authentication headers to all requests
- Log sensitive data for debugging
- Replace text in HTML responses
- Add tracking pixels to web pages
- Mock API responses for testing

## When to Use Custom Hooks vs Config Hooks

**Use Configuration-Based Hooks (YAML)** when:
- You need simple operations (redirects, text replacement)
- You don't want to write code
- You want to easily enable/disable hooks
- See [HOOKS.md](HOOKS.md) for config-based hooks

**Use Custom Python Hooks** when:
- You need complex logic (API calls, database lookups)
- You need access to external libraries
- You want to make decisions based on request content
- You need stateful operations (caching, rate limiting)

## Setting Up

### 1. Create a Hooks Directory

```bash
# In your project directory
mkdir my-hooks
cd my-hooks
```

### 2. Create Your First Hook File

```bash
# Create a Python file for your hooks
touch my_first_hook.py
```

### 3. Run Proxy with Your Hooks

```bash
# Start the proxy with your hooks directory
python-proxy --hooks ./my-hooks --target http://example.com
```

## Your First Hook

Let's create a simple hook that adds a custom header to every request.

**File: `my-hooks/my_first_hook.py`**

```python
"""My first custom hook."""

async def before_request(request, request_data):
    """Add a custom header to every request.

    Args:
        request: The incoming request object
        request_data: Dict with url, method, headers, and body

    Returns:
        Modified request_data dict
    """
    # Add your custom header
    request_data["headers"]["X-My-Custom-Header"] = "Hello from my hook!"

    # Always return the request_data
    return request_data
```

**What's happening:**
1. We define an `async def` function (required for hooks)
2. Name it `before_request` (special name that python-proxy looks for)
3. It receives `request` and `request_data` parameters
4. We modify the headers in `request_data`
5. We return the modified `request_data`

**Test it:**
```bash
# Start proxy
python-proxy --hooks ./my-hooks --target http://httpbin.org

# Make a request
curl -x http://localhost:8080 http://httpbin.org/headers

# You should see your custom header in the response!
```

## Before Request Hooks

Before request hooks run BEFORE the proxy forwards the request to the backend. Use them to:
- Modify request headers
- Change the target URL
- Add authentication
- Block certain requests

### Example 1: Add Authentication

```python
"""Add API key authentication to requests."""

async def before_request(request, request_data):
    """Add API key to all API requests."""

    # Check if this is an API request
    if "/api/" in request_data["url"]:
        # Add authentication header
        request_data["headers"]["Authorization"] = "Bearer YOUR_API_KEY_HERE"

    return request_data
```

### Example 2: Change Target URL

```python
"""Redirect requests to a different server."""

async def before_request(request, request_data):
    """Route staging requests to staging server."""

    # Check if this is a staging request
    if "staging" in request.host:
        # Change the URL to staging server
        original_url = request_data["url"]
        request_data["url"] = original_url.replace(
            "production.example.com",
            "staging.example.com"
        )

    return request_data
```

### Example 3: Block Requests

```python
"""Block requests to certain paths."""

from aiohttp import web

async def before_request(request, request_data):
    """Block access to admin paths."""

    # Check if path contains /admin/
    if "/admin/" in request.path:
        # Return a 403 Forbidden response
        # This skips the backend call entirely
        return web.Response(
            status=403,
            text="Access Denied: Admin area not accessible through proxy"
        )

    return request_data
```

### Example 4: Log Requests

```python
"""Log all requests for debugging."""

import logging

logger = logging.getLogger(__name__)

async def before_request(request, request_data):
    """Log every request."""

    logger.info(
        f"Request: {request_data['method']} {request_data['url']} "
        f"from {request.remote}"
    )

    # Log headers if needed
    logger.debug(f"Headers: {request_data['headers']}")

    return request_data
```

## After Response Hooks

After response hooks run AFTER the proxy receives the response from the backend. Use them to:
- Modify response body (HTML, JSON, text)
- Add/remove headers
- Log responses
- Inject scripts or content

### Example 1: Add Header to Response

```python
"""Add custom header to all responses."""

async def after_response(response, body):
    """Add X-Proxy-Version header to responses.

    Args:
        response: The response object from backend
        body: Response body as bytes

    Returns:
        Modified body as bytes
    """
    # Add header to response
    response.headers["X-Proxy-Version"] = "1.0.0"

    # Return body unchanged
    return body
```

### Example 2: Inject JavaScript

```python
"""Inject JavaScript into HTML pages."""

async def after_response(response, body):
    """Add analytics script to all HTML pages."""

    # Check if response is HTML
    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type:
        # Decode body
        html = body.decode("utf-8", errors="ignore")

        # Inject script before </head>
        script = '<script>console.log("Proxy injected this!");</script>'
        html = html.replace("</head>", f"{script}</head>")

        # Return modified HTML as bytes
        return html.encode("utf-8")

    # Not HTML, return unchanged
    return body
```

### Example 3: Modify JSON Responses

```python
"""Modify JSON API responses."""

import json

async def after_response(response, body):
    """Add extra field to JSON responses."""

    # Check if response is JSON
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            # Parse JSON
            data = json.loads(body.decode("utf-8"))

            # Add your field
            data["proxy_processed"] = True
            data["proxy_timestamp"] = "2025-01-01T00:00:00Z"

            # Return modified JSON
            return json.dumps(data).encode("utf-8")
        except json.JSONDecodeError:
            # Invalid JSON, return unchanged
            pass

    return body
```

### Example 4: Replace Text in HTML

```python
"""Replace branding in HTML pages."""

async def after_response(response, body):
    """Replace old company name with new one."""

    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type:
        # Decode HTML
        html = body.decode("utf-8", errors="ignore")

        # Replace text (case-insensitive)
        import re
        html = re.sub(
            r"OldCompanyName",
            "NewCompanyName",
            html,
            flags=re.IGNORECASE
        )

        return html.encode("utf-8")

    return body
```

## Using Hook Decorators

Decorators make your hooks more organized and easier to read. They're optional but recommended for larger projects.

```python
"""Example using decorators."""

from python_proxy.hooks import before_request, after_response

@before_request
async def add_auth_header(request, request_data):
    """Add auth header with decorator."""
    request_data["headers"]["Authorization"] = "Bearer TOKEN"
    return request_data

@after_response
async def add_proxy_header(response, body):
    """Add proxy header with decorator."""
    response.headers["X-Proxied-By"] = "Python-Proxy"
    return body
```

**Benefits of decorators:**
- Clearer intent (you can see it's a hook at a glance)
- Can have multiple hooks in one file
- More explicit naming (functions don't need special names)

## Real-World Examples

### Example 1: Mock API for Testing

```python
"""Mock API responses for testing."""

from aiohttp import web
import json

@before_request
async def mock_api_responses(request, request_data):
    """Return fake data for testing."""

    # Mock user API
    if "/api/users/123" in request_data["url"]:
        fake_user = {
            "id": 123,
            "name": "Test User",
            "email": "test@example.com",
            "role": "admin"
        }
        return web.Response(
            status=200,
            text=json.dumps(fake_user),
            content_type="application/json"
        )

    # Let other requests through
    return request_data
```

### Example 2: Rate Limiting

```python
"""Simple rate limiting hook."""

from datetime import datetime, timedelta
from collections import defaultdict
from aiohttp import web

# Store request counts (in production, use Redis)
request_counts = defaultdict(list)

@before_request
async def rate_limit(request, request_data):
    """Limit requests to 10 per minute per IP."""

    client_ip = request.remote
    now = datetime.now()

    # Remove old requests (older than 1 minute)
    request_counts[client_ip] = [
        req_time for req_time in request_counts[client_ip]
        if now - req_time < timedelta(minutes=1)
    ]

    # Check if over limit
    if len(request_counts[client_ip]) >= 10:
        return web.Response(
            status=429,
            text="Rate limit exceeded. Please try again later."
        )

    # Add this request
    request_counts[client_ip].append(now)

    return request_data
```

### Example 3: Response Caching

```python
"""Cache responses for faster repeated requests."""

from datetime import datetime, timedelta

# Simple cache (in production, use Redis)
cache = {}

@before_request
async def check_cache(request, request_data):
    """Return cached response if available."""

    from aiohttp import web

    cache_key = request_data["url"]

    if cache_key in cache:
        cached_data, cached_time = cache[cache_key]

        # Check if cache is still fresh (5 minutes)
        if datetime.now() - cached_time < timedelta(minutes=5):
            return web.Response(
                status=200,
                body=cached_data,
                content_type="text/html"
            )

    return request_data

@after_response
async def save_to_cache(response, body):
    """Save response to cache."""

    # Only cache successful GET requests
    if response.status == 200:
        # Store in cache with timestamp
        cache_key = str(response.url)
        cache[cache_key] = (body, datetime.now())

    return body
```

### Example 4: Debug Logger

```python
"""Detailed logging for debugging."""

import logging
import json

logger = logging.getLogger(__name__)

@before_request
async def log_request_details(request, request_data):
    """Log detailed request information."""

    logger.info("=" * 60)
    logger.info(f"REQUEST: {request_data['method']} {request_data['url']}")
    logger.info(f"Client: {request.remote}")
    logger.info(f"Host header: {request.host}")

    # Log headers
    logger.info("Headers:")
    for key, value in request_data["headers"].items():
        logger.info(f"  {key}: {value}")

    # Log body if present
    if request_data.get("body"):
        logger.info(f"Body length: {len(request_data['body'])} bytes")

    return request_data

@after_response
async def log_response_details(response, body):
    """Log detailed response information."""

    logger.info("-" * 60)
    logger.info(f"RESPONSE: {response.status} {response.reason}")
    logger.info(f"Content-Type: {response.headers.get('Content-Type')}")
    logger.info(f"Body length: {len(body)} bytes")

    # Log JSON responses
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            data = json.loads(body.decode("utf-8"))
            logger.info(f"JSON: {json.dumps(data, indent=2)}")
        except:
            pass

    logger.info("=" * 60)

    return body
```

## Testing Your Hooks

### 1. Test with curl

```bash
# Start proxy
python-proxy --hooks ./my-hooks --target http://httpbin.org

# Test your hook
curl -v -x http://localhost:8080 http://httpbin.org/get

# Check headers were added
curl -x http://localhost:8080 http://httpbin.org/headers
```

### 2. Test with Python

```python
"""test_my_hooks.py - Test your hooks"""

import requests

# Configure proxy
proxies = {
    'http': 'http://localhost:8080',
    'https': 'http://localhost:8080',
}

# Make request
response = requests.get('http://httpbin.org/get', proxies=proxies)

print(f"Status: {response.status_code}")
print(f"Headers: {response.headers}")
print(f"Body: {response.text}")
```

### 3. Write Unit Tests

```python
"""Unit tests for your hooks."""

import pytest
from my_hooks.my_first_hook import before_request

@pytest.mark.asyncio
async def test_adds_custom_header():
    """Test that custom header is added."""

    # Mock request
    class MockRequest:
        pass

    # Mock request data
    request_data = {
        "url": "http://example.com",
        "method": "GET",
        "headers": {},
        "body": None
    }

    # Call hook
    result = await before_request(MockRequest(), request_data)

    # Assert header was added
    assert "X-My-Custom-Header" in result["headers"]
    assert result["headers"]["X-My-Custom-Header"] == "Hello from my hook!"
```

## Troubleshooting

### Hook Not Running

**Problem:** Your hook isn't being called.

**Solutions:**
1. Check file name ends with `.py`
2. Check function is named `before_request` or `after_response` (or uses decorators)
3. Check function is `async def` not just `def`
4. Check hooks directory path is correct
5. Look for errors in proxy logs

### Import Errors

**Problem:** `ImportError` or `ModuleNotFoundError`

**Solutions:**
1. Install required packages: `pip install package-name`
2. Check your Python path
3. Use relative imports for local modules

### Hook Causes Proxy to Crash

**Problem:** Proxy crashes when hook runs.

**Solutions:**
1. Add try-except blocks to catch errors:
```python
async def before_request(request, request_data):
    try:
        # Your code here
        return request_data
    except Exception as e:
        import logging
        logging.error(f"Hook error: {e}")
        return request_data  # Return unchanged
```

2. Check you're returning the correct type:
   - `before_request` must return `request_data` dict or `web.Response`
   - `after_response` must return bytes

### Body Encoding Issues

**Problem:** Unicode errors or garbled text.

**Solutions:**
```python
# Always use errors="ignore" when decoding
text = body.decode("utf-8", errors="ignore")

# Always encode back to bytes
return text.encode("utf-8")
```

### Hook Runs But Doesn't Work

**Problem:** Hook runs but doesn't modify traffic.

**Solutions:**
1. Add logging to see what's happening:
```python
import logging
logger = logging.getLogger(__name__)
logger.info(f"Hook called with: {request_data}")
```

2. Check you're modifying the right thing:
   - Headers go in `request_data["headers"]`
   - URL goes in `request_data["url"]`
   - Body modifications must return new bytes

3. Make sure you return the modified data:
```python
# ❌ Wrong - forgot to return
async def before_request(request, request_data):
    request_data["headers"]["X-Test"] = "value"

# ✅ Correct
async def before_request(request, request_data):
    request_data["headers"]["X-Test"] = "value"
    return request_data
```

## Next Steps

### Learn More

- **[HOOKS.md](HOOKS.md)** - Complete hook reference with all built-in hooks
- **[config_with_hooks.yaml](config_with_hooks.yaml)** - Example config-based hooks
- **[json_hooks_example.yaml](json_hooks_example.yaml)** - JSON manipulation examples
- **[advanced_hooks.py](advanced_hooks.py)** - Advanced hook patterns
- **[NginxIntegration.md](NginxIntegration.md)** - Using hooks with nginx

### Example Hooks to Study

Located in the `examples/` directory:
- **[examples/hooks/](hooks/)** - Organized hook examples by hostname
- **Custom hook patterns** - See the test files in `tests/` directory

### Get Help

- Check the [GitHub Issues](https://github.com/parf/python-proxy/issues)
- Read the main [README.md](../README.md)
- Look at the test files in `tests/` for more examples

### Ideas for Your Own Hooks

1. **Authentication**
   - Add JWT tokens
   - OAuth2 integration
   - API key injection

2. **Testing**
   - Mock specific API endpoints
   - Simulate slow responses
   - Inject test data

3. **Debugging**
   - Log all traffic
   - Save responses to files
   - Add request timing

4. **Security**
   - Remove sensitive headers
   - Sanitize responses
   - Add security headers

5. **Performance**
   - Cache responses
   - Compress content
   - Rate limiting

6. **Content Modification**
   - Replace images
   - Inject analytics
   - Modify JSON responses
   - Transform XML to JSON

Happy hooking! 🎣

---

**Questions?** Open an issue on [GitHub](https://github.com/parf/python-proxy/issues)
