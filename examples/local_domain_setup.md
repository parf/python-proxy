# Local Domain Setup Guide

This guide shows how to use the `.local` domain feature for local development and testing.

## What is .local Domain Routing?

The proxy automatically strips the `.local` suffix from hostnames and routes requests to the actual domain on **port 80** (standard HTTP). Any port specified in the `.local` request is ignored. This allows you to:

- Test production URLs locally on port 80
- Intercept specific domains without changing DNS
- Use /etc/hosts for easy local routing

**Important:** All `.local` requests route to port 80, regardless of what port is specified in the `.local` URL.

## Example: Testing Production API Locally

### Setup

1. **Start your local development server** (e.g., on port 3000)
   ```bash
   # Your local API server
   npm start  # runs on localhost:3000
   ```

2. **Add /etc/hosts entry** (requires sudo)
   ```bash
   sudo nano /etc/hosts
   ```

   Add this line:
   ```
   127.0.0.1  api.mycompany.com.local
   ```

3. **Start the proxy**
   ```bash
   python-proxy --port 8080
   ```

4. **Configure your application to use the proxy**

   In your app's HTTP client configuration:
   ```javascript
   // JavaScript example
   const axios = require('axios');

   const api = axios.create({
     baseURL: 'http://api.mycompany.com.local',
     proxy: {
       host: 'localhost',
       port: 8080
     }
   });

   // Now api.mycompany.com.local routes through proxy
   // The proxy strips .local and forwards to api.mycompany.com:80
   ```

   ```python
   # Python example
   import requests

   proxies = {
       'http': 'http://localhost:8080',
       'https': 'http://localhost:8080'
   }

   # Request goes through proxy, .local is stripped, routes to port 80
   response = requests.get(
       'http://api.mycompany.com.local/users',
       proxies=proxies
   )
   # → Forwards to api.mycompany.com:80
   ```

## Example: Multi-Service Development

Set up multiple services with .local domains:

### /etc/hosts
```
# Development services - all point to localhost
127.0.0.1  api.myapp.com.local
127.0.0.1  web.myapp.com.local
127.0.0.1  cdn.myapp.com.local
```

### Start Services
```bash
# Terminal 1: API server
cd api && npm start  # port 3000

# Terminal 2: Web server
cd web && npm start  # port 3001

# Terminal 3: CDN/Assets server
cd cdn && npm start  # port 3002

# Terminal 4: Proxy with routing hooks
python-proxy --port 8080 --hooks ./my-hooks
```

### Routing Hook (my-hooks/route_by_subdomain.py)
```python
from python_proxy.hooks import before_request

@before_request
async def route_by_subdomain(request, request_data):
    """Route to different local ports based on subdomain."""
    url = request_data["url"]

    # Map subdomains to local ports
    if "api.myapp.com" in url:
        # Route API to port 3000
        request_data["url"] = url.replace(
            "api.myapp.com",
            "localhost:3000"
        )
    elif "web.myapp.com" in url:
        # Route web to port 3001
        request_data["url"] = url.replace(
            "web.myapp.com",
            "localhost:3001"
        )
    elif "cdn.myapp.com" in url:
        # Route CDN to port 3002
        request_data["url"] = url.replace(
            "cdn.myapp.com",
            "localhost:3002"
        )

    return request_data
```

### Test It
```bash
# API request - routes to localhost:3000
curl -x http://localhost:8080 http://api.myapp.com.local/users

# Web request - routes to localhost:3001
curl -x http://localhost:8080 http://web.myapp.com.local/

# CDN request - routes to localhost:3002
curl -x http://localhost:8080 http://cdn.myapp.com.local/logo.png
```

## Example: Testing Staging Environment

Test against staging servers while developing locally:

### /etc/hosts
```
# Point .local domains to staging IPs
10.0.1.50  api.staging.myapp.com.local
10.0.1.51  db.staging.myapp.com.local
```

### Start Proxy with Logging
```bash
python-proxy --port 8080 --hooks ./logging-hooks --log-level DEBUG
```

### Use in Tests
```python
# test_api.py
import pytest
import requests

PROXY = {'http': 'http://localhost:8080'}

def test_user_api():
    # Request to .local domain goes through proxy to staging
    response = requests.get(
        'http://api.staging.myapp.com.local/users',
        proxies=PROXY
    )
    assert response.status_code == 200
```

## Example: Browser Configuration

Configure your browser to use the proxy for easy manual testing:

### Firefox
1. Settings → Network Settings → Manual proxy configuration
2. HTTP Proxy: `localhost`, Port: `8080`
3. Use this proxy server for all protocols: ✓

### Chrome/Edge
Use system proxy settings or extensions like SwitchyOmega

### Set up /etc/hosts
```
127.0.0.1  myapp.com.local
127.0.0.1  api.myapp.com.local
```

Now browse to `http://myapp.com.local/` and the proxy will forward to `myapp.com`

## Tips

1. **Keep .local in /etc/hosts only** - Don't use .local in production DNS
2. **Use with hooks** - Combine with hooks for powerful local testing
3. **Port handling** - `.local` stripping works with ports: `api.example.com.local:8080`
4. **Explicit headers override** - `X-Proxy-Server` header takes precedence over .local stripping
5. **Log level DEBUG** - Use `--log-level DEBUG` to see .local routing in action

## Troubleshooting

**Request not routing correctly?**
```bash
# Check proxy logs with DEBUG level
python-proxy --log-level DEBUG

# You should see:
# INFO - Auto-routing .local domain: example.com.local -> example.com
```

**Connection refused?**
- Check your local service is actually running
- Verify the port in your .local URL matches your service port
- Try connecting directly without proxy first

**DNS issues?**
```bash
# Clear DNS cache (macOS)
sudo dscacheutil -flushcache

# Clear DNS cache (Linux)
sudo systemd-resolve --flush-caches

# Verify /etc/hosts entry
ping myapp.com.local  # Should ping 127.0.0.1
```
