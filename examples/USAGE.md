# Usage Examples

## Basic Usage

### Start the proxy server

```bash
# Start on default port 8080
python-proxy

# Start with specific configuration
python-proxy --host 127.0.0.1 --port 3128
```

## Using Headers to Route Requests

### X-Proxy-Server (Simple Format - Recommended)

The `X-Proxy-Server` header accepts a simple `host` or `host:port` format:

```bash
# Route to example.com (default port 80, http)
curl -x http://localhost:8080 \
     -H "X-Proxy-Server: example.com" \
     http://example.com/page

# Route to custom port
curl -x http://localhost:8080 \
     -H "X-Proxy-Server: api.example.com:8080" \
     http://api.example.com/data

# Route to HTTPS (port 443 automatically uses https)
curl -x http://localhost:8080 \
     -H "X-Proxy-Server: secure.example.com:443" \
     https://secure.example.com/secure-page

# Route to IP address
curl -x http://localhost:8080 \
     -H "X-Proxy-Server: 192.168.1.100:3000" \
     http://192.168.1.100:3000/api
```

### X-Proxy-Target (Full URL - Legacy)

The `X-Proxy-Target` header accepts a full URL with scheme:

```bash
# Using full URL
curl -x http://localhost:8080 \
     -H "X-Proxy-Target: http://example.com:8080" \
     http://example.com:8080/page
```

### X-Proxy-Host (Host Header Override)

Use `X-Proxy-Host` to override the Host header sent to the backend server. This is useful for:
- Virtual hosting (multiple sites on one IP)
- Testing with /etc/hosts entries
- Accessing services behind load balancers

```bash
# Connect to IP but send specific Host header
curl -x http://localhost:8080 \
     -H "X-Proxy-Server: 192.168.1.100:8080" \
     -H "X-Proxy-Host: myapp.example.com" \
     http://192.168.1.100:8080/

# Access staging site by IP with production hostname
curl -x http://localhost:8080 \
     -H "X-Proxy-Server: 10.0.0.50:80" \
     -H "X-Proxy-Host: www.production.com" \
     http://staging.example.com/

# Test load balancer backend directly
curl -x http://localhost:8080 \
     -H "X-Proxy-Server: backend1.internal:8080" \
     -H "X-Proxy-Host: api.example.com" \
     http://api.example.com/health
```

## Using with Python

```python
import requests

# Set up proxy
proxies = {
    'http': 'http://localhost:8080',
    'https': 'http://localhost:8080'
}

# Using X-Proxy-Server
headers = {
    'X-Proxy-Server': 'example.com:8080'
}
response = requests.get('http://example.com/api/data',
                       proxies=proxies,
                       headers=headers)

# Using X-Proxy-Host override
headers = {
    'X-Proxy-Server': '192.168.1.100:8080',
    'X-Proxy-Host': 'myapp.example.com'
}
response = requests.get('http://myapp.example.com/api',
                       proxies=proxies,
                       headers=headers)
```

## Advanced Scenarios

### Testing with Local Backend

```bash
# Test your local development server through the proxy with hooks
python-proxy --hooks ./my-hooks

# In another terminal, make requests
curl -x http://localhost:8080 \
     -H "X-Proxy-Server: localhost:3000" \
     http://localhost:3000/api/test
```

### Multi-Backend Setup

```bash
# Route different paths to different backends using hooks
# See examples/header_routing_hooks.py

# API requests go to api backend
curl -x http://localhost:8080 http://example.com/api/users

# Static files go to CDN
curl -x http://localhost:8080 http://example.com/static/logo.png

# Admin requests go to admin backend
curl -x http://localhost:8080 http://example.com/admin/dashboard
```

### Load Balancing

```bash
# Use hooks to distribute requests across multiple backends
# See examples/header_routing_hooks.py

# Each request is routed to a different backend server
for i in {1..10}; do
    curl -x http://localhost:8080 http://example.com/api/test
done
```

## Using with Configuration File

Create `config.yaml`:

```yaml
host: "0.0.0.0"
port: 8080
target_host: "http://example.com"  # Default target
timeout: 30
hooks_dir: "./hooks"
log_level: "INFO"
```

Run with:

```bash
python-proxy --config config.yaml

# Requests without headers use default target
curl -x http://localhost:8080 http://example.com/page

# Headers override default
curl -x http://localhost:8080 \
     -H "X-Proxy-Server: other.com" \
     http://other.com/page
```

## Browser Configuration

Configure your browser to use the proxy:

1. **Firefox**: Settings → Network Settings → Manual proxy configuration
   - HTTP Proxy: `localhost`, Port: `8080`

2. **Chrome/Edge**: Use with system proxy or extensions like SwitchyOmega

3. **cURL**: Use `-x` flag as shown above

Then browse normally - use hooks to modify requests/responses as needed.
