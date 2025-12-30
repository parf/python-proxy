# python-proxy

Transparent Python HTTP Proxy (similar to nginx) with powerful request/response modification hooks. Allows you to intercept and modify HTTP traffic before forwarding to the target server or after receiving the response.

## Features

- **Async/Await Architecture**: Built on `aiohttp` for high-performance async I/O
- **Request Modification**: Modify requests before they're proxied (headers, body, URL, etc.)
- **Response Modification**: Modify responses after receiving from target (HTML injection, content replacement, etc.)
- **Hook System**: Simple Python-based hook system with automatic discovery
- **Configuration-Based Hooks**: Powerful built-in hooks (redirects, rewrites, HTML/text transformation) via YAML config - no coding required!
- **Flexible Configuration**: Configure via CLI arguments, environment variables, or YAML config file
- **Header-Based Routing**: Route requests to different targets using `X-Proxy-Target` header

## Installation

```bash
# Install from source
pip install -e .

# Or install dependencies directly
pip install -r requirements.txt
```

## Quick Start

### Basic Usage

```bash
# Start proxy on default port 8080
python-proxy

# Start with custom port
python-proxy --port 3128

# Proxy all requests to a specific target
python-proxy --target http://example.com

# Use a configuration file
python-proxy --config config.yaml
```

### Running on Port 80 (Privileged Port)

**Quick Install (Recommended):**
```bash
# Install wrapper and set up port 80 capability
./scripts/install_wrapper.sh

# Now use from anywhere
python-proxy --host 192.168.2.7 --port 80
```

**Manual Setup:**
```bash
# One-time setup (resolves symlinks if needed)
sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python3))

# Now run without sudo
python-proxy --host 192.168.2.7 --port 80
```

See [examples/port80_setup.md](examples/port80_setup.md) for detailed instructions and alternatives.

### Using Environment Variables

```bash
export PROXY_PORT=8080
export PROXY_TARGET=http://example.com
export PROXY_HOOKS_DIR=./hooks
python-proxy
```

### Making Requests Through the Proxy

The proxy supports multiple ways to specify the backend target:

1. **X-Proxy-Server** - Simple host or host:port format (recommended)
2. **X-Proxy-Target** - Full URL with scheme (legacy)
3. **Default target** - Configured via CLI or config file
4. **Automatic .local domains** - Requests to `hostname.local` automatically route to `hostname`

```bash
# Using X-Proxy-Server (simple format)
curl -x http://localhost:8080 \
     -H "X-Proxy-Server: example.com" \
     http://example.com/page

# Using X-Proxy-Server with custom port
curl -x http://localhost:8080 \
     -H "X-Proxy-Server: example.com:8080" \
     http://example.com/page

# Using X-Proxy-Target (full URL)
curl -x http://localhost:8080 \
     -H "X-Proxy-Target: http://example.com" \
     http://example.com/page

# Override the Host header sent to backend
curl -x http://localhost:8080 \
     -H "X-Proxy-Server: 192.168.1.100:8080" \
     -H "X-Proxy-Host: myapp.example.com" \
     http://example.com/page

# With default target configured
curl -x http://localhost:8080 http://example.com/page
```

#### Header Reference

- **X-Proxy-Server**: Backend server as `host` or `host:port`
  - Default port: 80 (http) if not specified
  - Port 443 automatically uses HTTPS
  - Examples: `example.com`, `example.com:8080`, `192.168.1.100:3000`

- **X-Proxy-Target**: Full backend URL (legacy, but still supported)
  - Must include scheme (http:// or https://)
  - Example: `http://example.com:8080`

- **X-Proxy-Host**: Override the Host header sent to backend server
  - Useful for virtual hosting or when backend expects specific hostname
  - Example: `myapp.example.com`

### Automatic .local Domain Routing

The proxy automatically strips the `.local` suffix from hostnames and routes to the actual domain on **port 80** (standard HTTP). Any port specified in the `.local` request is ignored. This is useful for local development and testing.

```bash
# Request to example.com.local routes to example.com:80
curl -x http://localhost:8080 http://example.com.local/page

# Port in .local URL is ignored - still routes to port 80
curl -x http://localhost:8080 http://api.example.com.local:8080/data
# → Routes to api.example.com:80

# Configure in /etc/hosts for easy testing:
# 127.0.0.1 myapp.com.local
curl -x http://localhost:8080 http://myapp.com.local/
```

**Behavior:**
- `hostname.local` → `hostname:80`
- `hostname.local:XXXX` → `hostname:80` (port ignored)
- Always uses HTTP (port 80), not HTTPS

**Use cases:**
- Local development: Test production URLs locally
- /etc/hosts testing: Add `.local` entries to route through proxy
- Network testing: Intercept specific domains without DNS changes

**Example /etc/hosts setup:**
```
# Add .local entries that proxy will strip and forward to port 80
127.0.0.1 api.example.com.local
127.0.0.1 cdn.example.com.local
```

Then requests to `api.example.com.local:8080` go through your proxy to `api.example.com:80`.

## Configuration-Based Hooks (New!)

Configure powerful hooks directly in your YAML config - no Python coding required! Perfect for redirects, URL rewrites, content modification, and more.

### Quick Example

```yaml
# config.yaml
host: "0.0.0.0"
port: 8080

hook_mappings:
  # Pre-hooks (execute before backend, can skip backend call)
  pre_hooks:
    - hostname: "example.com"
      url_pattern: "/old-page"
      hook: "redirect_301"
      params:
        location: "https://example.com/new-page"

  # Post-hooks (execute after backend, modify response)
  post_hooks:
    - hostname: "example.com"
      url_pattern: "/*"
      hook: "text_rewrite"
      params:
        pattern: "OldCompany"
        replacement: "NewCompany"
```

**Built-in hooks include:**
- **Pre-hooks**: `redirect_301`, `redirect_302`, `gone_410`, `not_found_404`, `static_html`
- **Post-hooks**: `url_rewrite`, `text_rewrite`, `link_rewrite`, `html_rewrite`, `xpath_replace_from_url`

**Features:**
- Hostname patterns with wildcards (`*.example.com`)
- URL patterns with glob (`/api/*`) or regex (`regex:^/api/v[0-9]+/`)
- Pre-hooks can skip backend calls (redirects, errors)
- Post-hooks modify content (HTML, text, JSON)

See [examples/HOOKS.md](examples/HOOKS.md) for complete documentation and [examples/config_with_hooks.yaml](examples/config_with_hooks.yaml) for a working example.

### Nginx Integration

Use python-proxy with nginx as a frontend reverse proxy for production deployments. Nginx handles SSL termination and load balancing, while python-proxy provides powerful hook-based content modification.

See [examples/NginxIntegration.md](examples/NginxIntegration.md) for complete nginx configuration examples including:
- Proxy entire site or specific paths through python-proxy
- Dynamic backend routing based on URL patterns
- Load balancing with multiple python-proxy instances
- Production-ready setup with SSL/TLS
- Performance optimization and security best practices

## Creating Custom Python Hooks

For advanced use cases, you can write custom Python hooks. Place them in a hooks directory.

### Simple Hook Example

Create a file `hooks/my_hooks.py`:

```python
async def before_request(request, request_data):
    """Modify request before proxying."""
    # Add custom header
    request_data["headers"]["X-Custom"] = "MyValue"
    return request_data

async def after_response(response, body):
    """Modify response after receiving."""
    # Modify HTML content
    if b"<html>" in body:
        body = body.replace(b"</body>", b"<!-- Modified --></body>")
    return body
```

Then run with:
```bash
python-proxy --hooks ./hooks --target http://example.com
```

### Advanced Hooks with Decorators

```python
from python_proxy.hooks import before_request, after_response

@before_request
async def add_auth(request, request_data):
    """Add authentication to API requests."""
    if "api.example.com" in request_data["url"]:
        request_data["headers"]["Authorization"] = "Bearer TOKEN"
    return request_data

@after_response
async def inject_script(response, body):
    """Inject JavaScript into HTML pages."""
    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type:
        html = body.decode("utf-8", errors="ignore")
        script = '<script>console.log("Proxied!")</script>'
        html = html.replace("</head>", f"{script}</head>")
        return html.encode("utf-8")
    return body
```

See `examples/` directory for more hook examples.

## Configuration

### Configuration File (YAML)

Create `config.yaml`:

```yaml
host: "0.0.0.0"
port: 8080
target_host: "http://example.com"
timeout: 30
hooks_dir: "./hooks"
log_level: "INFO"
```

### Configuration Priority

1. CLI arguments (highest priority)
2. Configuration file (`--config`)
3. Environment variables
4. Default values (lowest priority)

## Running on Port 80

Ports below 1024 require special permissions. The proxy provides helpful error messages and multiple solutions:

```bash
# Quick setup (recommended)
./scripts/setup_port80.sh

# Or manually
sudo setcap 'cap_net_bind_service=+ep' $(which python3)
python-proxy --host 192.168.2.7 --port 80
```

**Other options:**
- Run with sudo (not recommended for production)
- Use iptables port forwarding
- Use systemd socket activation

See [examples/port80_setup.md](examples/port80_setup.md) for complete guide.

## Development

### Install Development Dependencies

```bash
pip install -r requirements-dev.txt
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=python_proxy

# Run specific test file
pytest tests/test_config.py
```

### Linting

```bash
# Run ruff linter
ruff check .

# Auto-fix issues
ruff check --fix .
```

## Use Cases

- **Web Scraping**: Modify headers, inject credentials
- **Development**: Test how your app handles different responses
- **Security Testing**: Analyze and modify traffic
- **Content Injection**: Add scripts, styles, or content to proxied pages
- **API Testing**: Modify API requests/responses on the fly
- **Traffic Analysis**: Log and analyze HTTP traffic

## License

GPL v2
