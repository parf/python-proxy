# Nginx Integration with Python-Proxy

This guide shows how to configure nginx to proxy traffic through python-proxy, leveraging its powerful hook system for request/response modification, URL rewriting, content injection, and more.

## Overview

Nginx acts as the frontend server, forwarding requests to python-proxy with special headers (`X-Proxy-Server` or `X-Proxy-Target`). Python-proxy then applies configured hooks before proxying to the actual backend.

**Architecture:**
```
Client → Nginx → Python-Proxy (with hooks) → Backend Server
                     ↓
              Hook Processing
```

## Prerequisites

1. **Python-proxy running:**
   ```bash
   # Start python-proxy on port 8080
   python-proxy --port 8080 --config config.yaml
   ```

2. **Nginx installed:**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install nginx

   # CentOS/RHEL/Fedora
   sudo dnf install nginx
   ```

## Basic Configuration

**Note:** In all examples below, `python-proxy-ip:8080` should be replaced with:
- `localhost:8080` if python-proxy runs on the same server as nginx
- `192.168.1.100:8080` (or actual IP) if python-proxy runs on a different server
- `python-proxy.local:8080` (or hostname) if using DNS/hosts file

### Example 1: Proxy Entire Site Through Python-Proxy

Forward all traffic to python-proxy, which then proxies to the backend.

**nginx.conf:**
```nginx
server {
    listen 80;
    server_name example.com;

    location / {
        # Proxy to python-proxy
        proxy_pass http://python-proxy-ip:8080;

        # Set backend server using X-Proxy-Server header
        proxy_set_header X-Proxy-Server backend.example.com;

        # Preserve original host
        proxy_set_header Host $host;

        # Forward client info
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**What this does:**
- All requests to `example.com` go through python-proxy
- Python-proxy applies configured hooks (URL rewriting, content modification, etc.)
- Python-proxy forwards to `backend.example.com`

### Example 2: Proxy Specific Paths Only

Only certain URLs go through python-proxy, others go directly to backend.

**nginx.conf:**
```nginx
server {
    listen 80;
    server_name example.com;

    # Only proxy /api/* through python-proxy for modification
    location /api/ {
        proxy_pass http://python-proxy-ip:8080;
        proxy_set_header X-Proxy-Server api-backend.example.com;
        proxy_set_header Host $host;
    }

    # Static content goes directly to backend
    location /static/ {
        proxy_pass http://backend.example.com;
        proxy_set_header Host $host;
    }

    # Everything else also goes through python-proxy
    location / {
        proxy_pass http://python-proxy-ip:8080;
        proxy_set_header X-Proxy-Server backend.example.com;
        proxy_set_header Host $host;
    }
}
```

### Example 3: Using X-Proxy-Target (Full URL)

Use `X-Proxy-Target` when you need to specify the full backend URL including scheme.

**nginx.conf:**
```nginx
server {
    listen 80;
    server_name example.com;

    location / {
        proxy_pass http://python-proxy-ip:8080;

        # Full URL including scheme
        proxy_set_header X-Proxy-Target https://secure-backend.example.com;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Advanced Configurations

### Example 4: Route Different Paths to Different Backends

Route different URL patterns to different backend servers through python-proxy.

**nginx.conf:**
```nginx
server {
    listen 80;
    server_name example.com;

    # API requests go to API backend
    location /api/ {
        proxy_pass http://python-proxy-ip:8080;
        proxy_set_header X-Proxy-Server api.backend.local:8000;
        proxy_set_header Host $host;
    }

    # Blog requests go to WordPress backend
    location /blog/ {
        proxy_pass http://python-proxy-ip:8080;
        proxy_set_header X-Proxy-Server wordpress.backend.local;
        proxy_set_header Host $host;
    }

    # Admin panel goes to admin backend with HTTPS
    location /admin/ {
        proxy_pass http://python-proxy-ip:8080;
        proxy_set_header X-Proxy-Target https://admin.backend.local;
        proxy_set_header Host $host;
    }

    # Everything else
    location / {
        proxy_pass http://python-proxy-ip:8080;
        proxy_set_header X-Proxy-Server main.backend.local;
        proxy_set_header Host $host;
    }
}
```

### Example 5: Dynamic Backend Based on Request

Use nginx variables to dynamically set the backend server.

**nginx.conf:**
```nginx
map $request_uri $backend_server {
    ~^/api/v1/     "api-v1.backend.local:8001";
    ~^/api/v2/     "api-v2.backend.local:8002";
    ~^/legacy/     "legacy.backend.local:9000";
    default        "main.backend.local";
}

server {
    listen 80;
    server_name example.com;

    location / {
        proxy_pass http://python-proxy-ip:8080;
        proxy_set_header X-Proxy-Server $backend_server;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Example 6: Override Backend Host Header

Use `X-Proxy-Host` to override the Host header sent to the backend.

**nginx.conf:**
```nginx
server {
    listen 80;
    server_name public.example.com;

    location / {
        proxy_pass http://python-proxy-ip:8080;

        # Backend server is an IP
        proxy_set_header X-Proxy-Server 192.168.1.100:8080;

        # But backend expects this hostname
        proxy_set_header X-Proxy-Host internal.backend.local;

        # Keep original host for client
        proxy_set_header Host $host;
    }
}
```

### Example 7: Load Balancing with Python-Proxy

Combine nginx load balancing with python-proxy hooks.

**nginx.conf:**
```nginx
upstream python_proxy_cluster {
    server 127.0.0.1:8080;
    server 127.0.0.1:8081;
    server 127.0.0.1:8082;
}

upstream backend_cluster {
    server backend1.example.com;
    server backend2.example.com;
    server backend3.example.com;
}

server {
    listen 80;
    server_name example.com;

    location / {
        # Load balance across python-proxy instances
        proxy_pass http://python_proxy_cluster;

        # All python-proxy instances will forward to backend cluster
        # (python-proxy can also do its own backend selection)
        proxy_set_header X-Proxy-Server backend1.example.com;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Python-Proxy Configuration for Nginx

When using with nginx, configure python-proxy hooks for your use cases:

**config.yaml:**
```yaml
host: "0.0.0.0"
port: 8080
log_level: "INFO"

hook_mappings:
  pre_hooks:
    # Redirect old URLs before hitting backend
    - hostname: "example.com"
      url_pattern: "/old-api/*"
      hook: "redirect_301"
      params:
        location: "https://example.com/api/"

  post_hooks:
    # Add .local to all links for local testing
    - hostname: "example.com.local"
      url_pattern: "/*"
      hook: "link_rewrite"
      params:
        from_domain: "example.com"
        to_domain: "example.com.local"

    # Inject analytics script
    - hostname: "*"
      url_pattern: "/*.html"
      hook: "html_rewrite"
      params:
        xpath: "//head"
        action: "insert_before"
        value: '<script src="/analytics.js"></script>'
```

## Use Cases

### Use Case 1: Local Development with .local Domains

**Problem:** Test production site locally without modifying /etc/hosts for every resource.

**Solution:**
```nginx
# /etc/nginx/sites-available/local-dev
server {
    listen 80;
    server_name myapp.local;

    location / {
        proxy_pass http://python-proxy-ip:8080;
        # Python-proxy will strip .local and forward to production
        proxy_set_header Host myapp.local;
    }
}
```

**Python-proxy config:**
- Automatic .local domain stripping is built-in!
- Links are rewritten using `link_rewrite` hook

### Use Case 2: Content Injection for A/B Testing

**Problem:** Inject A/B testing scripts without modifying backend code.

**nginx.conf:**
```nginx
server {
    listen 80;
    server_name example.com;

    location / {
        proxy_pass http://python-proxy-ip:8080;
        proxy_set_header X-Proxy-Server backend.example.com;
        proxy_set_header Host $host;
    }
}
```

**Python-proxy config:**
```yaml
hook_mappings:
  post_hooks:
    - hostname: "example.com"
      url_pattern: "/*"
      hook: "html_rewrite"
      params:
        xpath: "//head"
        action: "insert_before"
        value: '<script src="https://cdn.example.com/ab-testing.js"></script>'
```

### Use Case 3: API Version Migration

**Problem:** Migrate from `/api/v1/` to `/api/v2/` URLs in responses.

**nginx.conf:**
```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://python-proxy-ip:8080;
        proxy_set_header X-Proxy-Server api-backend.example.com;
    }
}
```

**Python-proxy config:**
```yaml
hook_mappings:
  post_hooks:
    - hostname: "api.example.com"
      url_pattern: "/*"
      hook: "url_rewrite"
      params:
        pattern: '"/api/v1/'
        replacement: '"/api/v2/'
        content_types: ["application/json", "text/html"]
```

### Use Case 4: WordPress + Static Site Integration

**Problem:** Fetch blog content from WordPress, inject into static site.

**nginx.conf:**
```nginx
server {
    listen 80;
    server_name example.com;

    # Static site
    location / {
        proxy_pass http://python-proxy-ip:8080;
        proxy_set_header X-Proxy-Server static.backend.local;
    }
}
```

**Python-proxy config:**
```yaml
hook_mappings:
  post_hooks:
    - hostname: "example.com"
      url_pattern: "/blog/*"
      hook: "xpath_replace_from_url"
      params:
        target_xpath: '//div[@id="blog-content"]'
        source_url: 'https://wordpress.example.com/wp-json/wp/v2/posts/123'
        source_xpath: '//article[@class="post"]'
        action: "replace_content"
```

### Use Case 5: Multi-Tenant Backend Routing

**Problem:** Route different domains to different backend servers.

**nginx.conf:**
```nginx
map $host $backend_server {
    tenant1.example.com  "tenant1.backend.local:8001";
    tenant2.example.com  "tenant2.backend.local:8002";
    tenant3.example.com  "tenant3.backend.local:8003";
    default              "default.backend.local:8000";
}

server {
    listen 80;
    server_name *.example.com;

    location / {
        proxy_pass http://python-proxy-ip:8080;
        proxy_set_header X-Proxy-Server $backend_server;
        proxy_set_header Host $host;
    }
}
```

## Performance Considerations

### Caching

Enable nginx caching to reduce load on python-proxy:

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m max_size=1g inactive=60m;

server {
    listen 80;
    server_name example.com;

    location / {
        proxy_pass http://python-proxy-ip:8080;
        proxy_set_header X-Proxy-Server backend.example.com;

        # Cache responses from python-proxy
        proxy_cache my_cache;
        proxy_cache_valid 200 10m;
        proxy_cache_valid 404 1m;
        proxy_cache_key "$scheme$request_method$host$request_uri";

        add_header X-Cache-Status $upstream_cache_status;
    }
}
```

### Connection Pooling

Keep connections alive between nginx and python-proxy:

```nginx
upstream python_proxy {
    server 127.0.0.1:8080;
    keepalive 32;
}

server {
    listen 80;
    server_name example.com;

    location / {
        proxy_pass http://python_proxy;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header X-Proxy-Server backend.example.com;
    }
}
```

## Debugging

### Enable Debug Logging

**Nginx:**
```nginx
error_log /var/log/nginx/error.log debug;

server {
    access_log /var/log/nginx/access.log combined;

    location / {
        proxy_pass http://python-proxy-ip:8080;
        proxy_set_header X-Proxy-Server backend.example.com;

        # Log headers
        add_header X-Debug-Backend backend.example.com;
    }
}
```

**Python-proxy:**
```yaml
log_level: "DEBUG"
```

### Test Configuration

```bash
# Test nginx config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# Test python-proxy
curl -v http://localhost:8080/test \
  -H "X-Proxy-Server: backend.example.com" \
  -H "Host: example.com"

# Test through nginx
curl -v http://example.com/test
```

## Security Considerations

### Restrict Python-Proxy Access

Python-proxy should only accept connections from nginx:

```nginx
# Nginx config - no changes needed

# Python-proxy - bind to localhost only
python-proxy --host 127.0.0.1 --port 8080
```

### Sanitize Headers

Prevent clients from sending proxy control headers:

```nginx
server {
    listen 80;
    server_name example.com;

    location / {
        # Remove any client-set proxy headers
        proxy_set_header X-Proxy-Server "";
        proxy_set_header X-Proxy-Target "";
        proxy_set_header X-Proxy-Host "";

        # Set your own backend
        proxy_set_header X-Proxy-Server backend.example.com;

        proxy_pass http://python-proxy-ip:8080;
    }
}
```

### SSL/TLS Termination

Let nginx handle SSL, python-proxy handles HTTP:

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /etc/ssl/certs/example.com.crt;
    ssl_certificate_key /etc/ssl/private/example.com.key;

    location / {
        # Nginx handles HTTPS, forwards HTTP to python-proxy
        proxy_pass http://python-proxy-ip:8080;
        proxy_set_header X-Proxy-Server backend.example.com;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Complete Example: Production Setup

**Complete nginx configuration:**
```nginx
# /etc/nginx/sites-available/example.com

upstream python_proxy {
    server 127.0.0.1:8080;
    server 127.0.0.1:8081;
    keepalive 32;
}

# HTTP redirect to HTTPS
server {
    listen 80;
    server_name example.com www.example.com;
    return 301 https://example.com$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name example.com www.example.com;

    ssl_certificate /etc/ssl/certs/example.com.crt;
    ssl_certificate_key /etc/ssl/private/example.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    # Logging
    access_log /var/log/nginx/example.com-access.log combined;
    error_log /var/log/nginx/example.com-error.log warn;

    # API routes through python-proxy
    location /api/ {
        proxy_pass http://python_proxy;
        proxy_http_version 1.1;
        proxy_set_header Connection "";

        proxy_set_header X-Proxy-Server api.backend.local:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Blog through python-proxy with WordPress integration
    location /blog/ {
        proxy_pass http://python_proxy;
        proxy_http_version 1.1;
        proxy_set_header Connection "";

        proxy_set_header X-Proxy-Server wordpress.backend.local;
        proxy_set_header Host $host;
    }

    # Static assets bypass python-proxy
    location /static/ {
        proxy_pass http://static.backend.local;
        proxy_cache my_cache;
        proxy_cache_valid 200 1h;
    }

    # Everything else through python-proxy
    location / {
        proxy_pass http://python_proxy;
        proxy_http_version 1.1;
        proxy_set_header Connection "";

        proxy_set_header X-Proxy-Server main.backend.local;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Corresponding python-proxy config:**
```yaml
host: "127.0.0.1"
port: 8080
log_level: "INFO"

hook_mappings:
  pre_hooks:
    # Maintenance mode for specific paths
    - hostname: "example.com"
      url_pattern: "/maintenance"
      hook: "static_html"
      params:
        html: |
          <!DOCTYPE html>
          <html><body><h1>Under Maintenance</h1></body></html>
        status: 503

  post_hooks:
    # Inject analytics on all HTML pages
    - hostname: "*"
      url_pattern: "/*.html"
      hook: "html_rewrite"
      params:
        xpath: "//head"
        action: "insert_before"
        value: '<script src="/analytics.js"></script>'

    # Fetch WordPress content
    - hostname: "example.com"
      url_pattern: "/blog/*"
      hook: "xpath_replace_from_url"
      params:
        target_xpath: '//div[@id="blog-content"]'
        source_url: 'https://wordpress.backend.local/wp-json/wp/v2/posts/123'
        source_xpath: '//article'
```

## Troubleshooting

### Problem: Backend not receiving requests

**Check:**
1. Python-proxy is running: `curl http://localhost:8080`
2. Headers are set correctly in nginx: Check access logs
3. Python-proxy can reach backend: Test manually

### Problem: Infinite redirect loop

**Cause:** Python-proxy or backend returning redirects to nginx URL

**Solution:** Set `X-Forwarded-Host` properly:
```nginx
proxy_set_header X-Forwarded-Host $host;
proxy_set_header X-Forwarded-Proto $scheme;
```

### Problem: Headers not being set

**Check nginx config:**
```bash
# Verify configuration
sudo nginx -t

# Check what headers are actually sent
tcpdump -i lo -A 'port 8080'
```

## Summary

Nginx + Python-Proxy provides a powerful combination:
- **Nginx**: High-performance frontend, SSL termination, load balancing
- **Python-Proxy**: Flexible request/response modification with hooks

This architecture enables:
- ✅ Dynamic content injection
- ✅ URL rewriting and normalization
- ✅ Multi-source content aggregation
- ✅ A/B testing and experimentation
- ✅ Legacy system integration
- ✅ Local development workflows

For more information, see:
- [HOOKS.md](HOOKS.md) - Complete hook documentation
- [config_with_hooks.yaml](config_with_hooks.yaml) - Hook examples
- [USAGE.md](USAGE.md) - General usage guide
