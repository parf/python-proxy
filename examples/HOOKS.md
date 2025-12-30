# Configuration-Based Hooks

Python-proxy now supports powerful configuration-based hooks that allow you to intercept and modify HTTP traffic without writing any Python code. Simply configure hooks in your YAML config file!

## Overview

Hooks are divided into two categories:

1. **Pre-Hooks**: Execute **before** proxying to the backend
   - Can return an early response to **skip the backend call entirely**
   - Perfect for redirects, error pages, or blocking requests

2. **Post-Hooks**: Execute **after** receiving the response from backend
   - Modify response content (HTML, text, JSON, etc.)
   - Rewrite URLs, inject content, or transform data

## Configuration Structure

```yaml
hook_mappings:
  pre_hooks:
    - hostname: "example.com"          # Hostname pattern (supports wildcards)
      url_pattern: "/old-path"         # URL pattern (glob or regex)
      hook: "redirect_301"             # Built-in hook name
      params:                          # Hook-specific parameters
        location: "/new-path"

  post_hooks:
    - hostname: "*.example.com"
      url_pattern: "/api/*"
      hook: "url_rewrite"
      params:
        pattern: '"/api/users/([^/"]+)"'
        replacement: '"/api/users?id=$1"'
```

## Organizing Hooks with Includes

For better organization, especially when managing many hooks for a single hostname, you can separate hooks into dedicated files using the `include` directive.

### Include Syntax

```yaml
hook_mappings:
  pre_hooks:
    - hostname: "example.com"
      include: "hooks/example.com-pre.yaml"

  post_hooks:
    - hostname: "example.com"
      include: "hooks/example.com-post.yaml"
```

### Include File Format

In the included file, you only need to specify the hook details (no `hostname` field required):

**hooks/example.com-pre.yaml:**
```yaml
- url_pattern: "/old-page"
  hook: "redirect_301"
  params:
    location: "/new-page"

- url_pattern: "/deleted/*"
  hook: "gone_410"
  params:
    message: "Content removed"
```

The `hostname` is automatically added to each hook from the include directive.

### Include Features

- **Relative paths**: Resolved relative to the config file directory
- **Absolute paths**: Fully qualified paths also supported
- **Mixed mode**: Combine includes with inline hooks
- **Automatic hostname**: Hostname from include directive is added to all hooks
- **Override hostname**: Hooks can specify their own hostname if needed
- **Error handling**: Missing files log errors but don't stop config loading

### Complete Include Example

**config.yaml:**
```yaml
host: "0.0.0.0"
port: 8080

hook_mappings:
  pre_hooks:
    # Include organized hooks from separate files
    - hostname: "example.com"
      include: "hooks/example.com-pre.yaml"

    - hostname: "api.example.com"
      include: "hooks/api.example.com-pre.yaml"

    # Mix with inline hooks
    - hostname: "other.com"
      url_pattern: "/maintenance"
      hook: "static_html"
      params:
        html: "<h1>Maintenance Mode</h1>"
        status: 503

  post_hooks:
    - hostname: "example.com"
      include: "hooks/example.com-post.yaml"

    - hostname: "api.example.com"
      include: "hooks/api.example.com-post.yaml"
```

**hooks/example.com-pre.yaml:**
```yaml
# Redirects for example.com
- url_pattern: "/old-page"
  hook: "redirect_301"
  params:
    location: "/new-page"

- url_pattern: "/old-blog/*"
  hook: "redirect_301"
  params:
    location: "/blog/"
```

**hooks/example.com-post.yaml:**
```yaml
# Content modifications for example.com
- url_pattern: "/*"
  hook: "text_rewrite"
  params:
    pattern: "OldBrand"
    replacement: "NewBrand"

- url_pattern: "/*"
  hook: "link_rewrite"
  params:
    from_domain: "example.com"
    to_domain: "example.com.local"
```

### Benefits of Using Includes

1. **Better Organization**: Group hooks by hostname in separate files
2. **Easier Maintenance**: Update hooks for a hostname in one place
3. **Team Collaboration**: Different team members can manage different hostnames
4. **Reusability**: Share common hook files across configurations
5. **Cleaner Config**: Main config stays small and readable

See [config_with_includes.yaml](config_with_includes.yaml) and the `hooks/` directory for a complete working example.

## Pattern Matching

### Hostname Patterns

Hostname matching is **case-insensitive** and supports wildcards:

- `"example.com"` - Exact match
- `"*.example.com"` - Wildcard subdomain (matches `api.example.com`, `www.example.com`, etc.)
- `"*"` - Matches **all** hostnames

### URL Patterns

URL patterns default to **glob matching**, but also support regex:

**Glob patterns** (default):
- `"/api/*"` - Matches `/api/users`, `/api/posts`, etc.
- `"/users/*/profile"` - Matches `/users/123/profile`, `/users/abc/profile`
- `"/*.html"` - Matches all `.html` files in root directory

**Regex patterns** (prefix with `regex:`):
- `"regex:^/api/v[0-9]+/"` - Matches `/api/v1/`, `/api/v2/`, etc.
- `"regex:^/(deprecated|removed)/.*"` - Matches paths starting with `/deprecated/` or `/removed/`

## Built-In Pre-Hooks

Pre-hooks execute before proxying and can return an HTTP response to skip the backend call.

### redirect_301

Returns a 301 Permanent Redirect.

**Parameters:**
- `location` (required): Target URL for redirect
- `preserve_query` (optional, default: `true`): Whether to preserve query string

**Example:**
```yaml
pre_hooks:
  - hostname: "example.com"
    url_pattern: "/old-page"
    hook: "redirect_301"
    params:
      location: "https://example.com/new-page"
      preserve_query: true
```

### redirect_302

Returns a 302 Temporary Redirect.

**Parameters:**
- `location` (required): Target URL for redirect
- `preserve_query` (optional, default: `true`): Whether to preserve query string

**Example:**
```yaml
pre_hooks:
  - hostname: "example.com"
    url_pattern: "/temp"
    hook: "redirect_302"
    params:
      location: "https://example.com/temporary-page"
```

### gone_410

Returns a 410 Gone response (content permanently removed).

**Parameters:**
- `message` (optional): Custom message (default: "This resource is no longer available")

**Example:**
```yaml
pre_hooks:
  - hostname: "example.com"
    url_pattern: "/deleted/*"
    hook: "gone_410"
    params:
      message: "This content has been permanently removed"
```

### not_found_404

Returns a 404 Not Found response.

**Parameters:**
- `message` (optional): Custom message (default: "Not Found")
- `html` (optional, default: `false`): Return HTML response instead of plain text

**Example:**
```yaml
pre_hooks:
  - hostname: "example.com"
    url_pattern: "/hidden/*"
    hook: "not_found_404"
    params:
      message: "Page not found"
      html: true
```

### static_html

Return static HTML content without calling the backend. Perfect for maintenance pages, custom error pages, or serving static content.

**Parameters:**
- `html` (optional): Inline HTML content to return
- `file` (optional): Path to HTML file to serve (alternative to inline html)
- `status` (optional, default: `200`): HTTP status code
- `content_type` (optional, default: `"text/html"`): Content type header

**Examples:**
```yaml
pre_hooks:
  # Inline maintenance page
  - hostname: "example.com"
    url_pattern: "/maintenance"
    hook: "static_html"
    params:
      html: |
        <!DOCTYPE html>
        <html>
        <head><title>Maintenance Mode</title></head>
        <body>
          <h1>Site Under Maintenance</h1>
          <p>We'll be back soon!</p>
        </body>
        </html>
      status: 503

  # Serve from file
  - hostname: "example.com"
    url_pattern: "/custom-page"
    hook: "static_html"
    params:
      file: "/var/www/custom-page.html"
      status: 200
```

## Built-In Post-Hooks

Post-hooks execute after receiving the response and modify the content before returning it to the client.

### url_rewrite

Rewrite URLs in response body using regex patterns. Useful for converting REST-style URLs to query parameters.

**Parameters:**
- `pattern` (required): Regex pattern to match in URLs
- `replacement` (required): Replacement string (supports `$1`, `$2`, etc. for capture groups)
- `content_types` (optional): List of content types to process (default: `["text/html", "text/xml", "application/json"]`)

**Examples:**
```yaml
post_hooks:
  # Convert /api/users/123 to /api/users?id=123
  - hostname: "api.example.com"
    url_pattern: "/v1/users/*"
    hook: "url_rewrite"
    params:
      pattern: '"/v1/users/([^/"]+)"'
      replacement: '"/v1/users?id=$1"'

  # Convert /posts/456/comments/789 to /posts?post_id=456&comment_id=789
  - hostname: "api.example.com"
    url_pattern: "/v1/posts/*/comments/*"
    hook: "url_rewrite"
    params:
      pattern: '"/v1/posts/([^/"]+)/comments/([^/"]+)"'
      replacement: '"/v1/posts?post_id=$1&comment_id=$2"'
```

### text_rewrite

Rewrite text content using regex patterns. Works on any text-based content.

**Parameters:**
- `pattern` (required): Regex pattern to search for
- `replacement` (required): Replacement string
- `flags` (optional): Regex flags as string (e.g., `"IGNORECASE"`, `"MULTILINE"`, combine with `"|"`)
- `content_types` (optional): List of content types to process (default: `["text/html", "text/plain", "text/xml"]`)

**Examples:**
```yaml
post_hooks:
  # Simple find and replace (case-insensitive)
  - hostname: "example.com"
    url_pattern: "/blog/*"
    hook: "text_rewrite"
    params:
      pattern: "OldCompanyName"
      replacement: "NewCompanyName"
      flags: "IGNORECASE"

  # Redact phone numbers
  - hostname: "example.com"
    url_pattern: "/contact"
    hook: "text_rewrite"
    params:
      pattern: '\d{3}-\d{3}-\d{4}'
      replacement: "XXX-XXX-XXXX"
```

### link_rewrite

Rewrite domain names in all HTML links and resources (href, src, action, etc.). Perfect for adding `.local` suffixes, changing CDN domains, or migrating between domains.

**Parameters:**
- `from_domain` (required): Domain to replace (e.g., "realmo.com")
- `to_domain` (required): Replacement domain (e.g., "realmo.com.local")
- `attributes` (optional): List of attributes to rewrite (default: `["href", "src", "action", "data"]`)
- `case_sensitive` (optional, default: `false`): Whether matching is case-sensitive

**Examples:**
```yaml
post_hooks:
  # Add .local suffix for local testing (perfect for your use case!)
  - hostname: "realmo.com.local"
    url_pattern: "/*"
    hook: "link_rewrite"
    params:
      from_domain: "realmo.com"
      to_domain: "realmo.com.local"

  # Replace CDN domain
  - hostname: "example.com"
    url_pattern: "/*"
    hook: "link_rewrite"
    params:
      from_domain: "old-cdn.com"
      to_domain: "new-cdn.com"
      attributes: ["href", "src", "action", "data", "poster"]

  # Domain migration
  - hostname: "new-domain.com"
    url_pattern: "/*"
    hook: "link_rewrite"
    params:
      from_domain: "old-domain.com"
      to_domain: "new-domain.com"
```

### html_rewrite

Rewrite HTML content using XPath selectors. Powerful for precise HTML modifications.

**Parameters:**
- `xpath` (required): XPath expression to select elements
- `action` (required): Action to perform
  - `set_text`: Set text content of element
  - `set_attr`: Set attribute value
  - `remove`: Remove element
  - `insert_before`: Insert HTML before element
  - `insert_after`: Insert HTML after element
- `value` (optional): Value for the action
- `attribute` (optional): Attribute name (for `set_attr` action)

**Examples:**
```yaml
post_hooks:
  # Change page title
  - hostname: "example.com"
    url_pattern: "/index.html"
    hook: "html_rewrite"
    params:
      xpath: "//title"
      action: "set_text"
      value: "Welcome to Our Modified Site"

  # Change image source
  - hostname: "example.com"
    url_pattern: "/products/*"
    hook: "html_rewrite"
    params:
      xpath: '//img[@class="logo"]'
      action: "set_attr"
      attribute: "src"
      value: "/new-logo.png"

  # Remove ads
  - hostname: "example.com"
    url_pattern: "/*"
    hook: "html_rewrite"
    params:
      xpath: '//div[@class="advertisement"]'
      action: "remove"

  # Insert analytics script
  - hostname: "example.com"
    url_pattern: "/*.html"
    hook: "html_rewrite"
    params:
      xpath: "//head"
      action: "insert_before"
      value: '<script>console.log("Analytics loaded");</script>'
```

### xpath_replace_from_url

Fetch content from an external URL and replace XPath content in the response. Perfect for combining content from multiple sources, such as fetching WordPress articles and inserting them into another site.

**Parameters:**
- `target_xpath` (required): XPath in the response where content will be placed
- `source_url` (required): URL to fetch content from
- `source_xpath` (required): XPath to extract from the source URL
- `action` (optional, default: `"replace_content"`): How to replace content
  - `replace_content`: Replace element's content with source content
  - `replace_element`: Replace entire element with source element
  - `insert_before`: Insert source before target element
  - `insert_after`: Insert source after target element
- `timeout` (optional, default: `10`): Request timeout in seconds

**Examples:**
```yaml
post_hooks:
  # Fetch WordPress article and insert into page
  - hostname: "example.com"
    url_pattern: "/blog/*"
    hook: "xpath_replace_from_url"
    params:
      target_xpath: '//div[@id="article-content"]'
      source_url: 'https://wordpress-blog.example.com/article/123'
      source_xpath: '//article[@class="post-content"]'
      action: "replace_content"
      timeout: 10

  # Insert external banner before main content
  - hostname: "example.com"
    url_pattern: "/products/*"
    hook: "xpath_replace_from_url"
    params:
      target_xpath: '//main'
      source_url: 'https://api.example.com/banner/promo'
      source_xpath: '//div[@class="banner"]'
      action: "insert_before"
      timeout: 5

  # Replace entire news section with external content
  - hostname: "example.com"
    url_pattern: "/news"
    hook: "xpath_replace_from_url"
    params:
      target_xpath: '//section[@id="latest-news"]'
      source_url: 'https://news-api.example.com/latest'
      source_xpath: '//div[@class="news-feed"]'
      action: "replace_element"
```

### json_modify

Modify JSON responses by adding, deleting, or modifying fields. Perfect for API response manipulation, sanitization, and testing.

**Parameters:**
- `path` (required): JSON path to the node (e.g., "user.name", "items[0].price")
- `action` (required): Operation to perform
  - `set`: Set a value (creates nested objects if needed)
  - `delete`: Remove a field or array element
  - `append`: Add item to an array
  - `increment`: Increment numeric value by amount
- `value` (optional): Value for set/append/increment operations

**Path Syntax:**
- Dot notation: `"user.profile.name"`
- Array indices: `"items[0].price"`
- Nested: `"data.users[0].email"`

**Examples:**

```yaml
post_hooks:
  # Add a new field
  - hostname: "api.example.com"
    url_pattern: "/users/*"
    hook: "json_modify"
    params:
      path: "user.verified"
      action: "set"
      value: true

  # Add nested field (creates intermediate objects)
  - hostname: "api.example.com"
    url_pattern: "/users/*"
    hook: "json_modify"
    params:
      path: "user.profile.avatar_url"
      action: "set"
      value: "https://cdn.example.com/default-avatar.png"

  # Delete sensitive field
  - hostname: "api.example.com"
    url_pattern: "/users/*"
    hook: "json_modify"
    params:
      path: "user.password"
      action: "delete"

  # Delete API key from config
  - hostname: "api.example.com"
    url_pattern: "/config"
    hook: "json_modify"
    params:
      path: "api_key"
      action: "delete"

  # Modify existing value
  - hostname: "api.example.com"
    url_pattern: "/users/*"
    hook: "json_modify"
    params:
      path: "user.status"
      action: "set"
      value: "active"

  # Modify array element
  - hostname: "api.example.com"
    url_pattern: "/products/*"
    hook: "json_modify"
    params:
      path: "items[0].quantity"
      action: "set"
      value: 100

  # Append to array
  - hostname: "api.example.com"
    url_pattern: "/users/*"
    hook: "json_modify"
    params:
      path: "user.tags"
      action: "append"
      value: "premium"

  # Append object to array
  - hostname: "api.example.com"
    url_pattern: "/notifications"
    hook: "json_modify"
    params:
      path: "notifications"
      action: "append"
      value:
        id: "notification-123"
        type: "info"
        message: "Welcome!"

  # Increment counter
  - hostname: "api.example.com"
    url_pattern: "/posts/*"
    hook: "json_modify"
    params:
      path: "post.views"
      action: "increment"
      value: 1

  # Decrement stock
  - hostname: "api.example.com"
    url_pattern: "/products/*/purchase"
    hook: "json_modify"
    params:
      path: "product.stock"
      action: "increment"
      value: -1

  # Add metadata to all API responses
  - hostname: "api.example.com"
    url_pattern: "/api/*"
    hook: "json_modify"
    params:
      path: "metadata.proxy_version"
      action: "set"
      value: "1.0.0"
```

**Use Cases:**
- **Sanitization**: Remove passwords, tokens, API keys from responses
- **Enhancement**: Add computed fields, metadata, timestamps
- **A/B Testing**: Modify prices, features, configurations
- **Analytics**: Increment counters, add tracking IDs
- **Compatibility**: Transform API structure for legacy clients
- **Development**: Mock field values, test edge cases
- **Multi-tenancy**: Add tenant IDs, filter data

See [json_hooks_example.yaml](json_hooks_example.yaml) for comprehensive examples of all JSON operations.

## Complete Example

Here's a complete configuration file demonstrating various hooks:

```yaml
host: "0.0.0.0"
port: 8080
target_host: "http://example.com"
log_level: "INFO"

hook_mappings:
  pre_hooks:
    # Redirect old URLs
    - hostname: "example.com"
      url_pattern: "/old-page"
      hook: "redirect_301"
      params:
        location: "https://example.com/new-page"

    # Return 404 for hidden paths
    - hostname: "example.com"
      url_pattern: "/admin/*"
      hook: "not_found_404"
      params:
        message: "Access denied"
        html: true

    # Mark deprecated API as gone
    - hostname: "api.example.com"
      url_pattern: "regex:^/v0/.*"
      hook: "gone_410"
      params:
        message: "API v0 is deprecated. Please use v2."

  post_hooks:
    # Rewrite API URLs
    - hostname: "api.example.com"
      url_pattern: "/v1/*"
      hook: "url_rewrite"
      params:
        pattern: '"/v1/users/([^/"]+)"'
        replacement: '"/v1/users?id=$1"'

    # Replace company name
    - hostname: "example.com"
      url_pattern: "/*"
      hook: "text_rewrite"
      params:
        pattern: "OldCorp"
        replacement: "NewCorp"
        flags: "IGNORECASE"

    # Remove tracking scripts
    - hostname: "example.com"
      url_pattern: "/*.html"
      hook: "html_rewrite"
      params:
        xpath: '//script[contains(@src, "tracking")]'
        action: "remove"
```

## Running with Configuration

```bash
# Save your config to a file
# config.yaml

# Run proxy with config
python-proxy --config config.yaml

# Or specify config path
python-proxy --config /path/to/config_with_hooks.yaml
```

## Combining with Custom Hooks

You can use both configuration-based hooks AND custom Python hooks simultaneously:

```bash
# Run with both config hooks and custom Python hooks
python-proxy --config config_with_hooks.yaml --hooks ./my-custom-hooks/
```

**Execution order:**
1. Configuration-based pre-hooks (first match wins)
2. Custom Python before_request hooks
3. **Backend call** (skipped if pre-hook returned a response)
4. Custom Python after_response hooks
5. Configuration-based post-hooks (all matches applied)

## Use Cases

### Website Migration
```yaml
# Redirect all old domain traffic to new domain
pre_hooks:
  - hostname: "*.old-domain.com"
    url_pattern: "/*"
    hook: "redirect_301"
    params:
      location: "https://new-domain.com/"
      preserve_query: true
```

### API Deprecation
```yaml
# Mark old API versions as gone
pre_hooks:
  - hostname: "api.example.com"
    url_pattern: "regex:^/v[01]/.*"
    hook: "gone_410"
    params:
      message: "This API version is deprecated. Use /v2/"
```

### Content Filtering
```yaml
# Remove ads and tracking
post_hooks:
  - hostname: "*"
    url_pattern: "/*"
    hook: "html_rewrite"
    params:
      xpath: '//div[@class="ads"]'
      action: "remove"

  - hostname: "*"
    url_pattern: "/*"
    hook: "html_rewrite"
    params:
      xpath: '//script[contains(@src, "analytics")]'
      action: "remove"
```

### Development/Testing
```yaml
# Rewrite API responses for testing
post_hooks:
  - hostname: "api.example.com"
    url_pattern: "/users/*"
    hook: "text_rewrite"
    params:
      pattern: '"status":"active"'
      replacement: '"status":"inactive"'
      content_types: ["application/json"]
```

## Debugging

Enable debug logging to see hook matching and execution:

```yaml
log_level: "DEBUG"
```

This will show:
- Which hooks matched for each request
- Hook execution results
- Pattern matching details

## Performance Considerations

- **Pre-hooks**: Very fast (no backend call if returning response)
- **Post-hooks**: Performance depends on hook type
  - `url_rewrite` and `text_rewrite`: Fast (regex-based)
  - `html_rewrite`: Moderate (parses HTML with lxml)
- **Pattern matching**: Optimized with early exit
- **Multiple post-hooks**: Applied sequentially (order matters)

## Tips

1. **Order matters for pre-hooks**: First match wins, so place specific patterns before general ones
2. **Test patterns carefully**: Use regex testers for complex patterns
3. **Use wildcards wisely**: `"*"` matches everything (use as fallback)
4. **Content-type filtering**: Specify `content_types` to avoid processing binary files
5. **Combine hooks**: Use multiple post-hooks for complex transformations

## See Also

- **[CUSTOM_HOOKS_FOR_DUMMIES.md](CUSTOM_HOOKS_FOR_DUMMIES.md)** - Step-by-step tutorial for creating custom Python hooks (START HERE!)
- [config_with_hooks.yaml](config_with_hooks.yaml) - Complete working example
- [config_with_includes.yaml](config_with_includes.yaml) - Example using hostname-specific includes
- [json_hooks_example.yaml](json_hooks_example.yaml) - JSON manipulation examples
- [NginxIntegration.md](NginxIntegration.md) - Using python-proxy with nginx
- [../README.md](../README.md) - Main documentation
