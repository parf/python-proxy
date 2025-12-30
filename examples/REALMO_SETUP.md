# Setting Up realmo.com.local - Step by Step Guide

This guide walks you through setting up a local proxy for realmo.com, allowing you to test and develop locally while accessing the production site through your proxy.

## What This Does

1. Proxies requests from `realmo.com.local` to `realmo.com`
2. Automatically rewrites all links to keep traffic going through the proxy
3. Allows you to modify requests/responses for testing
4. No changes needed to realmo.com backend

## Prerequisites

- Python 3.8 or higher
- python-proxy installed
- Ability to edit `/etc/hosts` (requires sudo)
- Port 80 available (or use different port)

## Quick Start (3 Steps)

### Step 1: Configure /etc/hosts

Add realmo.com.local to your hosts file:

```bash
# Edit hosts file
sudo nano /etc/hosts

# Add this line:
127.0.0.1 realmo.com.local

# Save and exit (Ctrl+X, Y, Enter in nano)
```

**Why?** This makes your computer resolve `realmo.com.local` to your local machine instead of trying to find it on the internet.

### Step 2: Setup Port 80 (One-Time)

Python-proxy needs permission to bind to port 80:

```bash
# Quick setup (recommended)
cd /path/to/python-proxy
./scripts/setup_port80.sh

# Verify
getcap $(readlink -f $(which python3))
# Should show: cap_net_bind_service=ep
```

**Why?** Ports below 1024 require special permissions. This gives Python permission to use port 80 without running as root.

**Alternative:** Use a different port (skip this step):
```bash
# Use port 8080 instead
python-proxy --config examples/realmo.com.local-example.yaml --port 8080

# Then browse to: http://realmo.com.local:8080
```

### Step 3: Start the Proxy

```bash
# Start python-proxy with realmo.com.local configuration
python-proxy --config examples/realmo.com.local-example.yaml

# You should see:
# INFO - Proxy server started on http://0.0.0.0:80
```

**That's it!** Now open your browser and go to `http://realmo.com.local`

## Verification

Test that everything is working:

```bash
# Test with curl
curl -I http://realmo.com.local

# You should see HTTP response headers
# Check proxy logs for the request
```

**In your browser:**
1. Go to `http://realmo.com.local`
2. Open browser DevTools (F12)
3. Check Network tab - all requests should go to `.local` domain
4. Check links on the page - should all point to `realmo.com.local`

## Understanding What's Happening

```
Your Browser → realmo.com.local (port 80)
             → Python-Proxy (strips .local)
             → realmo.com (port 80)
             ← Response comes back
             ← Python-Proxy rewrites links
             ← Browser receives modified response
```

**Key behaviors:**
- Browser requests `http://realmo.com.local/page`
- Proxy strips `.local` → requests `http://realmo.com:80/page`
- Response comes back with links to `realmo.com`
- `link_rewrite` hook changes all `realmo.com` → `realmo.com.local`
- Browser receives page with all `.local` links
- Clicking any link keeps you in the proxy

## Configuration Explained

The configuration file does this:

```yaml
# Listen on port 80 for all interfaces
host: "0.0.0.0"
port: 80

# Post-hook: Rewrite links after receiving response
post_hooks:
  - hostname: "realmo.com.local"
    url_pattern: "/*"          # Apply to all URLs
    hook: "link_rewrite"        # Use link rewriting hook
    params:
      from_domain: "realmo.com"
      to_domain: "realmo.com.local"
      attributes: ["href", "src", "action", "data", "poster", "srcset"]
```

## Customization

### Add Multiple Subdomains

If realmo.com has subdomains, add them to `/etc/hosts`:

```bash
# /etc/hosts
127.0.0.1 realmo.com.local
127.0.0.1 www.realmo.com.local
127.0.0.1 api.realmo.com.local
127.0.0.1 cdn.realmo.com.local
```

Then add hooks for each subdomain in the config:

```yaml
post_hooks:
  # Main domain
  - hostname: "realmo.com.local"
    url_pattern: "/*"
    hook: "link_rewrite"
    params:
      from_domain: "realmo.com"
      to_domain: "realmo.com.local"

  # API subdomain
  - hostname: "api.realmo.com.local"
    url_pattern: "/*"
    hook: "link_rewrite"
    params:
      from_domain: "api.realmo.com"
      to_domain: "api.realmo.com.local"

  # CDN subdomain
  - hostname: "cdn.realmo.com.local"
    url_pattern: "/*"
    hook: "link_rewrite"
    params:
      from_domain: "cdn.realmo.com"
      to_domain: "cdn.realmo.com.local"
```

### Add Development Banner

Show a visual indicator that you're on the local proxy:

```yaml
post_hooks:
  # ... existing link_rewrite hook ...

  # Add banner
  - hostname: "realmo.com.local"
    url_pattern: "/*.html"
    hook: "html_rewrite"
    params:
      xpath: "//body"
      action: "insert_before"
      value: |
        <div style="position: fixed; top: 0; left: 0; right: 0;
                    background: #ff6b6b; color: white; padding: 5px;
                    text-align: center; z-index: 999999;">
          🔧 Development Mode - realmo.com.local
        </div>
```

### Inject Custom JavaScript

Add debugging scripts or modify behavior:

```yaml
post_hooks:
  # ... existing hooks ...

  # Add custom JavaScript
  - hostname: "realmo.com.local"
    url_pattern: "/*.html"
    hook: "html_rewrite"
    params:
      xpath: "//head"
      action: "insert_before"
      value: |
        <script>
        console.log('🔧 Python-proxy active');

        // Highlight all external links
        document.addEventListener('DOMContentLoaded', function() {
          const links = document.querySelectorAll('a[href*="realmo.com"]');
          links.forEach(link => {
            link.style.border = '2px solid red';
          });
        });
        </script>
```

### Modify Content for Testing

Replace specific content:

```yaml
post_hooks:
  # ... existing hooks ...

  # Change prices for testing
  - hostname: "realmo.com.local"
    url_pattern: "/products/*"
    hook: "text_rewrite"
    params:
      pattern: '\$([0-9]+\.[0-9]{2})'
      replacement: '$0.99 (TEST)'
      flags: "MULTILINE"
```

### Mock API Responses

Return fake data for testing:

```yaml
pre_hooks:
  # Mock API endpoint
  - hostname: "api.realmo.com.local"
    url_pattern: "/api/user/profile"
    hook: "static_html"
    params:
      html: |
        {
          "id": 123,
          "name": "Test User",
          "email": "test@example.com",
          "role": "admin"
        }
      status: 200
      content_type: "application/json"
```

## Troubleshooting

### Problem: "Permission denied" when starting on port 80

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied
```

**Solutions:**

1. **Run setup script** (recommended):
   ```bash
   ./scripts/setup_port80.sh
   ```

2. **Use a different port**:
   ```bash
   python-proxy --config examples/realmo.com.local-example.yaml --port 8080
   # Browse to: http://realmo.com.local:8080
   ```

3. **Use sudo** (not recommended):
   ```bash
   sudo python-proxy --config examples/realmo.com.local-example.yaml
   ```

### Problem: Links still point to realmo.com (not .local)

**Symptoms:** Clicking links takes you away from the proxy.

**Diagnosis:**
```bash
# Enable debug logging
python-proxy --config examples/realmo.com.local-example.yaml --log-level DEBUG

# Check if link_rewrite hook is executing
# Look for: "link_rewrite: Replaced ... links"
```

**Solutions:**

1. **Check Content-Type**: Hook only works on HTML
   ```bash
   curl -I http://realmo.com.local/page
   # Look for: Content-Type: text/html
   ```

2. **Check hook matches hostname**:
   - Hook: `hostname: "realmo.com.local"`
   - Must exactly match the Host header

3. **Check attributes list**:
   - Add more attributes if needed: `["href", "src", "action", "data"]`

### Problem: Page loads but looks broken/missing CSS/images

**Symptoms:** Page shows but no styling, broken images.

**Cause:** Resources loaded from different domains (CDN, subdomains).

**Diagnosis:**
```bash
# Open browser DevTools (F12)
# Check Console tab for errors like:
# Failed to load resource: net::ERR_NAME_NOT_RESOLVED
# Look at the domain in the error
```

**Solution:** Add those domains to /etc/hosts and create hooks:

```bash
# /etc/hosts
127.0.0.1 cdn.realmo.com.local
127.0.0.1 assets.realmo.com.local
```

```yaml
# config
post_hooks:
  - hostname: "cdn.realmo.com.local"
    url_pattern: "/*"
    hook: "link_rewrite"
    params:
      from_domain: "cdn.realmo.com"
      to_domain: "cdn.realmo.com.local"
```

### Problem: Infinite redirect loop

**Symptoms:** Browser shows "Too many redirects" error.

**Cause:** Site forces HTTPS redirect, but proxy is HTTP only.

**Solutions:**

1. **Use nginx with SSL** (see NginxIntegration.md)
2. **Disable HTTPS redirect** (if you control backend)
3. **Add HTTPS support**:
   ```bash
   # Generate self-signed cert
   openssl req -x509 -newkey rsa:4096 -nodes \
     -keyout key.pem -out cert.pem -days 365 \
     -subj "/CN=realmo.com.local"

   # Start with HTTPS (requires aiohttp-sslcontext)
   # Note: This is advanced - see documentation
   ```

### Problem: Some requests still go to realmo.com

**Symptoms:** Network tab shows mix of `.local` and non-`.local` requests.

**Cause:** Hardcoded URLs in JavaScript or API calls.

**Solutions:**

1. **Rewrite JavaScript**:
   ```yaml
   post_hooks:
     - hostname: "realmo.com.local"
       url_pattern: "/*.js"
       hook: "text_rewrite"
       params:
         pattern: '"https://realmo.com"'
         replacement: '"http://realmo.com.local"'
   ```

2. **Modify JSON responses**:
   ```yaml
   post_hooks:
     - hostname: "api.realmo.com.local"
       url_pattern: "/*"
       hook: "json_modify"
       params:
         path: "base_url"
         action: "set"
         value: "http://realmo.com.local"
   ```

## Advanced: Use with Nginx

For production-like setup with SSL:

**nginx.conf:**
```nginx
server {
    listen 80;
    server_name realmo.com.local;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header X-Proxy-Server realmo.com;
        proxy_set_header Host realmo.com.local;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

**Start python-proxy on 8080:**
```bash
python-proxy --config examples/realmo.com.local-example.yaml --port 8080
```

See [NginxIntegration.md](NginxIntegration.md) for complete guide.

## Cleanup

To stop using the proxy:

```bash
# 1. Stop python-proxy (Ctrl+C)

# 2. Remove from /etc/hosts
sudo nano /etc/hosts
# Delete or comment out: 127.0.0.1 realmo.com.local

# 3. Clear browser cache (optional)
#    Some cached resources might still have .local URLs
```

## Next Steps

- **[HOOKS.md](HOOKS.md)** - Learn about all available hooks
- **[CUSTOM_HOOKS_FOR_DUMMIES.md](CUSTOM_HOOKS_FOR_DUMMIES.md)** - Write your own hooks
- **[NginxIntegration.md](NginxIntegration.md)** - Production nginx setup
- **[json_hooks_example.yaml](json_hooks_example.yaml)** - API response modification

## Getting Help

If you run into issues:

1. Enable debug logging: `--log-level DEBUG`
2. Check the examples directory for similar use cases
3. Open an issue: https://github.com/parf/python-proxy/issues

## Example Use Cases

### Use Case 1: Test Payment Flow Locally

```yaml
pre_hooks:
  # Mock payment API
  - hostname: "api.realmo.com.local"
    url_pattern: "/api/payment/charge"
    hook: "static_html"
    params:
      html: '{"status":"success","transaction_id":"test_12345"}'
      content_type: "application/json"
```

### Use Case 2: Inject Analytics for Testing

```yaml
post_hooks:
  - hostname: "realmo.com.local"
    url_pattern: "/*.html"
    hook: "html_rewrite"
    params:
      xpath: "//head"
      action: "insert_before"
      value: '<script src="http://localhost:3000/analytics-test.js"></script>'
```

### Use Case 3: Replace Images for Testing

```yaml
post_hooks:
  - hostname: "realmo.com.local"
    url_pattern: "/*"
    hook: "text_rewrite"
    params:
      pattern: 'https://cdn.realmo.com/images/product-(\d+).jpg'
      replacement: 'http://localhost:8000/test-images/product-$1.jpg'
```

---

**Happy proxying!** 🚀
