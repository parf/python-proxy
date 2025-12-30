"""Built-in hooks for common proxy operations.

Copyright (C) 2025 Sergey Porfiriev <parf@difive.com>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp
from aiohttp import web
from lxml import html as lxml_html

logger = logging.getLogger(__name__)


# ============================================================================
# PRE-HOOKS (prevent backend calls)
# ============================================================================


async def redirect_301(
    request: web.Request,
    request_data: Dict[str, Any],
    params: Dict[str, Any],
) -> Optional[web.Response]:
    """Return a 301 Moved Permanently redirect.

    Params:
        location: Target URL for redirect
        preserve_query: Whether to preserve query string (default: True)

    Example config:
        hook: redirect_301
        params:
          location: "https://example.com/new-path/"
          preserve_query: true
    """
    location = params.get("location")
    if not location:
        logger.error("redirect_301: missing 'location' parameter")
        return None

    # Optionally preserve query string
    if params.get("preserve_query", True) and request.query_string:
        location = f"{location}?{request.query_string}"

    logger.info(f"301 Redirect: {request.path} -> {location}")
    return web.Response(
        status=301,
        headers={"Location": location},
        text="Moved Permanently",
    )


async def redirect_302(
    request: web.Request,
    request_data: Dict[str, Any],
    params: Dict[str, Any],
) -> Optional[web.Response]:
    """Return a 302 Found (temporary redirect).

    Params:
        location: Target URL for redirect
        preserve_query: Whether to preserve query string (default: True)

    Example config:
        hook: redirect_302
        params:
          location: "https://example.com/temp-page/"
    """
    location = params.get("location")
    if not location:
        logger.error("redirect_302: missing 'location' parameter")
        return None

    if params.get("preserve_query", True) and request.query_string:
        location = f"{location}?{request.query_string}"

    logger.info(f"302 Redirect: {request.path} -> {location}")
    return web.Response(
        status=302,
        headers={"Location": location},
        text="Found",
    )


async def gone_410(
    request: web.Request,
    request_data: Dict[str, Any],
    params: Dict[str, Any],
) -> Optional[web.Response]:
    """Return a 410 Gone response.

    Params:
        message: Optional custom message (default: "This resource is no longer available")

    Example config:
        hook: gone_410
        params:
          message: "This content has been permanently removed"
    """
    message = params.get("message", "This resource is no longer available")
    logger.info(f"410 Gone: {request.path}")
    return web.Response(
        status=410,
        text=message,
        content_type="text/plain",
    )


async def not_found_404(
    request: web.Request,
    request_data: Dict[str, Any],
    params: Dict[str, Any],
) -> Optional[web.Response]:
    """Return a 404 Not Found response.

    Params:
        message: Optional custom message (default: "Not Found")
        html: Whether to return HTML response (default: False)

    Example config:
        hook: not_found_404
        params:
          message: "Page not found"
          html: true
    """
    message = params.get("message", "Not Found")
    use_html = params.get("html", False)

    logger.info(f"404 Not Found: {request.path}")

    if use_html:
        html_content = f"""<!DOCTYPE html>
<html>
<head><title>404 Not Found</title></head>
<body>
<h1>404 Not Found</h1>
<p>{message}</p>
</body>
</html>"""
        return web.Response(
            status=404,
            text=html_content,
            content_type="text/html",
        )
    else:
        return web.Response(
            status=404,
            text=message,
            content_type="text/plain",
        )


async def static_html(
    request: web.Request,
    request_data: Dict[str, Any],
    params: Dict[str, Any],
) -> Optional[web.Response]:
    """Return static HTML content without calling backend.

    Useful for serving custom pages, maintenance pages, or static content.

    Params:
        html: HTML content to return (inline or from file)
        file: Path to HTML file (alternative to inline html)
        status: HTTP status code (default: 200)
        content_type: Content type (default: "text/html")

    Example configs:
        # Inline HTML
        hook: static_html
        params:
          html: '<html><body><h1>Maintenance Mode</h1></body></html>'
          status: 503

        # From file
        hook: static_html
        params:
          file: '/path/to/page.html'
          status: 200
    """
    html_content = params.get("html")
    file_path = params.get("file")
    status = params.get("status", 200)
    content_type = params.get("content_type", "text/html")

    # Get HTML content from inline or file
    if html_content:
        # Use inline HTML
        pass
    elif file_path:
        # Load from file
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"static_html: File not found: {file_path}")
                return None
            html_content = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"static_html: Error reading file {file_path}: {e}")
            return None
    else:
        logger.error("static_html: missing 'html' or 'file' parameter")
        return None

    logger.info(f"static_html: Returning static content for {request.path}")
    return web.Response(
        status=status,
        text=html_content,
        content_type=content_type,
    )


# ============================================================================
# POST-HOOKS (modify responses)
# ============================================================================


async def url_rewrite(
    response: web.Response,
    body: bytes,
    params: Dict[str, Any],
) -> bytes:
    """Rewrite URLs in response body.

    Converts URL path segments to query parameters using regex.

    Params:
        pattern: Regex pattern to match in URLs
        replacement: Replacement string (supports $1, $2, etc. for capture groups)
        content_types: List of content types to process (default: ["text/html", "text/xml"])

    Example config:
        hook: url_rewrite
        params:
          pattern: '"/api/users/([^/"]+)"'
          replacement: '"/api/users?id=$1"'
    """
    pattern = params.get("pattern")
    replacement = params.get("replacement")

    if not pattern or not replacement:
        logger.error("url_rewrite: missing 'pattern' or 'replacement' parameter")
        return body

    # Check content type
    content_type = response.headers.get("Content-Type", "")
    allowed_types = params.get("content_types", ["text/html", "text/xml", "application/json"])

    if not any(ct in content_type for ct in allowed_types):
        return body

    try:
        text = body.decode("utf-8", errors="ignore")
        # Convert $1, $2 to \1, \2 for Python's re.sub
        py_replacement = replacement.replace("$", "\\")
        rewritten = re.sub(pattern, py_replacement, text)

        if rewritten != text:
            logger.info(f"url_rewrite: Applied pattern {pattern}")

        return rewritten.encode("utf-8")
    except Exception as e:
        logger.error(f"url_rewrite error: {e}")
        return body


async def text_rewrite(
    response: web.Response,
    body: bytes,
    params: Dict[str, Any],
) -> bytes:
    """Rewrite text content using regex patterns.

    Params:
        pattern: Regex pattern to search for
        replacement: Replacement string
        flags: Regex flags as string (e.g., "IGNORECASE", "MULTILINE")
        content_types: List of content types to process

    Example config:
        hook: text_rewrite
        params:
          pattern: 'oldword'
          replacement: 'newword'
          flags: 'IGNORECASE'
    """
    pattern = params.get("pattern")
    replacement = params.get("replacement")

    if not pattern or replacement is None:
        logger.error("text_rewrite: missing 'pattern' or 'replacement' parameter")
        return body

    # Check content type
    content_type = response.headers.get("Content-Type", "")
    allowed_types = params.get("content_types", ["text/html", "text/plain", "text/xml"])

    if not any(ct in content_type for ct in allowed_types):
        return body

    try:
        # Parse flags
        flag_names = params.get("flags", "").split("|")
        regex_flags = 0
        for flag_name in flag_names:
            flag_name = flag_name.strip()
            if flag_name and hasattr(re, flag_name):
                regex_flags |= getattr(re, flag_name)

        text = body.decode("utf-8", errors="ignore")
        rewritten = re.sub(pattern, replacement, text, flags=regex_flags)

        if rewritten != text:
            logger.info(f"text_rewrite: Applied pattern {pattern}")

        return rewritten.encode("utf-8")
    except Exception as e:
        logger.error(f"text_rewrite error: {e}")
        return body


async def html_rewrite(
    response: web.Response,
    body: bytes,
    params: Dict[str, Any],
) -> bytes:
    """Rewrite HTML content using XPath selectors.

    Params:
        xpath: XPath expression to select elements
        action: Action to perform (set_text, set_attr, remove, insert_before, insert_after)
        value: Value for the action
        attribute: Attribute name (for set_attr action)

    Example configs:
        # Change text content
        hook: html_rewrite
        params:
          xpath: '//h1[@id="title"]'
          action: 'set_text'
          value: 'New Title'

        # Set attribute
        hook: html_rewrite
        params:
          xpath: '//img[@class="logo"]'
          action: 'set_attr'
          attribute: 'src'
          value: '/new-logo.png'

        # Remove elements
        hook: html_rewrite
        params:
          xpath: '//div[@class="ads"]'
          action: 'remove'

        # Insert HTML before element
        hook: html_rewrite
        params:
          xpath: '//body'
          action: 'insert_before'
          value: '<div class="header">Header</div>'
    """
    xpath = params.get("xpath")
    action = params.get("action")

    if not xpath or not action:
        logger.error("html_rewrite: missing 'xpath' or 'action' parameter")
        return body

    # Check content type
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return body

    try:
        text = body.decode("utf-8", errors="ignore")
        tree = lxml_html.fromstring(text)
        elements = tree.xpath(xpath)

        if not elements:
            logger.debug(f"html_rewrite: No elements matched XPath {xpath}")
            return body

        modified = False

        for element in elements:
            if action == "set_text":
                value = params.get("value", "")
                element.text = value
                modified = True

            elif action == "set_attr":
                attribute = params.get("attribute")
                value = params.get("value", "")
                if attribute:
                    element.set(attribute, value)
                    modified = True

            elif action == "remove":
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)
                    modified = True

            elif action == "insert_before":
                value = params.get("value", "")
                parent = element.getparent()
                if parent is not None:
                    # Parse the HTML fragment
                    fragment = lxml_html.fromstring(value)
                    index = parent.index(element)
                    parent.insert(index, fragment)
                    modified = True

            elif action == "insert_after":
                value = params.get("value", "")
                parent = element.getparent()
                if parent is not None:
                    fragment = lxml_html.fromstring(value)
                    index = parent.index(element)
                    parent.insert(index + 1, fragment)
                    modified = True

        if modified:
            logger.info(f"html_rewrite: Applied XPath {xpath} with action {action}")
            result = lxml_html.tostring(tree, encoding="unicode")
            return result.encode("utf-8")

        return body

    except Exception as e:
        logger.error(f"html_rewrite error: {e}")
        return body


async def link_rewrite(
    response: web.Response,
    body: bytes,
    params: Dict[str, Any],
) -> bytes:
    """Rewrite domain names in all HTML links and resources.

    Replaces hostnames in href, src, and other URL attributes throughout the HTML.
    Perfect for changing domains (e.g., realmo.com -> realmo.com.local) or creating
    local testing environments.

    Params:
        from_domain: Domain to replace (e.g., "realmo.com")
        to_domain: Replacement domain (e.g., "realmo.com.local")
        attributes: List of attributes to rewrite (default: ["href", "src", "action", "data"])
        case_sensitive: Whether matching is case-sensitive (default: false)

    Example configs:
        # Add .local suffix for local testing
        hook: link_rewrite
        params:
          from_domain: "realmo.com"
          to_domain: "realmo.com.local"

        # Replace domain completely
        hook: link_rewrite
        params:
          from_domain: "old-domain.com"
          to_domain: "new-domain.com"
          attributes: ["href", "src", "action", "data", "poster"]
    """
    from_domain = params.get("from_domain")
    to_domain = params.get("to_domain")

    if not from_domain or not to_domain:
        logger.error("link_rewrite: missing 'from_domain' or 'to_domain' parameter")
        return body

    # Check content type
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return body

    # Get attributes to rewrite
    attributes = params.get("attributes", ["href", "src", "action", "data"])
    case_sensitive = params.get("case_sensitive", False)

    try:
        text = body.decode("utf-8", errors="ignore")
        tree = lxml_html.fromstring(text)
        modified = False

        # Build XPath query for all specified attributes
        xpath_parts = [f".//*[@{attr}]" for attr in attributes]
        xpath_query = " | ".join(xpath_parts)

        elements = tree.xpath(xpath_query)

        for element in elements:
            for attr in attributes:
                if attr not in element.attrib:
                    continue

                original_value = element.get(attr, "")
                if not original_value:
                    continue

                # Replace domain in the attribute value
                # Handle various URL formats: //domain, http://domain, https://domain
                new_value = original_value

                # Escape special regex characters in domains
                from_escaped = re.escape(from_domain)

                # Prepare replacement flags
                flags = 0 if case_sensitive else re.IGNORECASE

                # Replace protocol-relative URLs
                new_value = re.sub(
                    f"//({from_escaped})",
                    f"//{to_domain}",
                    new_value,
                    flags=flags,
                )
                # Replace http URLs
                new_value = re.sub(
                    f"http://({from_escaped})",
                    f"http://{to_domain}",
                    new_value,
                    flags=flags,
                )
                # Replace https URLs
                new_value = re.sub(
                    f"https://({from_escaped})",
                    f"https://{to_domain}",
                    new_value,
                    flags=flags,
                )

                if new_value != original_value:
                    element.set(attr, new_value)
                    modified = True

        if modified:
            logger.info(f"link_rewrite: Replaced {from_domain} with {to_domain}")
            result = lxml_html.tostring(tree, encoding="unicode")
            return result.encode("utf-8")

        return body

    except Exception as e:
        logger.error(f"link_rewrite error: {e}")
        return body


async def xpath_replace_from_url(
    response: web.Response,
    body: bytes,
    params: Dict[str, Any],
) -> bytes:
    """Fetch content from external URL and replace XPath content in response.

    Fetches content from a source URL, extracts specific elements using XPath,
    and replaces elements in the current response. Perfect for combining content
    from multiple sources (e.g., WordPress articles into another site).

    Params:
        target_xpath: XPath in the response where content will be placed
        source_url: URL to fetch content from
        source_xpath: XPath to extract from the source URL
        action: How to replace content (default: "replace_content")
                - replace_content: Replace element's content with source content
                - replace_element: Replace entire element with source element
                - insert_before: Insert source before target element
                - insert_after: Insert source after target element
        timeout: Request timeout in seconds (default: 10)

    Example configs:
        # Get WordPress article and place it on another site
        hook: xpath_replace_from_url
        params:
          target_xpath: '//div[@id="article-content"]'
          source_url: 'https://wordpress-blog.com/article/123'
          source_xpath: '//article[@class="post-content"]'
          action: 'replace_content'

        # Insert external content before an element
        hook: xpath_replace_from_url
        params:
          target_xpath: '//main'
          source_url: 'https://api.example.com/banner'
          source_xpath: '//div[@class="banner"]'
          action: 'insert_before'
    """
    target_xpath = params.get("target_xpath")
    source_url = params.get("source_url")
    source_xpath = params.get("source_xpath")
    action = params.get("action", "replace_content")
    timeout = params.get("timeout", 10)

    if not target_xpath or not source_url or not source_xpath:
        logger.error(
            "xpath_replace_from_url: missing 'target_xpath', 'source_url', or 'source_xpath'"
        )
        return body

    # Check content type
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return body

    try:
        # Parse the response HTML
        text = body.decode("utf-8", errors="ignore")
        tree = lxml_html.fromstring(text)
        target_elements = tree.xpath(target_xpath)

        if not target_elements:
            logger.debug(f"xpath_replace_from_url: No target elements matched {target_xpath}")
            return body

        # Fetch content from source URL
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    source_url, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    if resp.status != 200:
                        logger.error(
                            f"xpath_replace_from_url: Source URL returned status {resp.status}"
                        )
                        return body

                    source_text = await resp.text()
                    source_tree = lxml_html.fromstring(source_text)
                    source_elements = source_tree.xpath(source_xpath)

                    if not source_elements:
                        logger.warning(
                            f"xpath_replace_from_url: No source elements matched {source_xpath}"
                        )
                        return body

            except asyncio.TimeoutError:
                logger.error(f"xpath_replace_from_url: Timeout fetching {source_url}")
                return body
            except Exception as e:
                logger.error(f"xpath_replace_from_url: Error fetching {source_url}: {e}")
                return body

        # Replace content based on action
        modified = False

        for target_element in target_elements:
            for source_element in source_elements:
                if action == "replace_content":
                    # Replace the content (children) of target with source's content
                    target_element.clear()
                    target_element.text = source_element.text
                    target_element.tail = source_element.tail
                    for child in source_element:
                        target_element.append(child)
                    modified = True

                elif action == "replace_element":
                    # Replace the entire target element with source element
                    parent = target_element.getparent()
                    if parent is not None:
                        index = parent.index(target_element)
                        parent.remove(target_element)
                        parent.insert(index, source_element)
                        modified = True

                elif action == "insert_before":
                    # Insert source before target
                    parent = target_element.getparent()
                    if parent is not None:
                        index = parent.index(target_element)
                        parent.insert(index, source_element)
                        modified = True

                elif action == "insert_after":
                    # Insert source after target
                    parent = target_element.getparent()
                    if parent is not None:
                        index = parent.index(target_element)
                        parent.insert(index + 1, source_element)
                        modified = True

                # Only use first source element for each target
                break

        if modified:
            logger.info(
                f"xpath_replace_from_url: Replaced content from {source_url} "
                f"into {target_xpath} with action {action}"
            )
            result = lxml_html.tostring(tree, encoding="unicode")
            return result.encode("utf-8")

        return body

    except Exception as e:
        logger.error(f"xpath_replace_from_url error: {e}")
        return body


async def json_modify(
    response: web.Response,
    body: bytes,
    params: Dict[str, Any],
) -> bytes:
    """Modify JSON response by adding, deleting, or modifying nodes.

    Supports JSONPath-like syntax for selecting nodes in the JSON structure.

    Params:
        path: JSON path to the node (e.g., "user.name", "items[0].price", "users[*].status")
        action: Operation to perform (set, delete, append, increment)
        value: Value for set/append operations (optional for delete)

    Actions:
        - set: Set a value (creates if doesn't exist)
        - delete: Remove a field or array element
        - append: Add to an array
        - increment: Increment a numeric value by amount (default 1)

    Examples:
        # Set a value
        path: "user.email"
        action: "set"
        value: "new@example.com"

        # Delete a field
        path: "user.password"
        action: "delete"

        # Append to array
        path: "tags"
        action: "append"
        value: "new-tag"

        # Increment counter
        path: "views"
        action: "increment"
        value: 1
    """
    try:
        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            return body

        # Parse JSON
        text = body.decode("utf-8", errors="ignore")
        data = json.loads(text)

        path = params.get("path")
        action = params.get("action", "set")
        value = params.get("value")

        if not path:
            logger.warning("json_modify: path parameter is required")
            return body

        # Parse path and navigate to target
        modified = _modify_json_path(data, path, action, value)

        if modified:
            logger.info(f"json_modify: Applied {action} to path '{path}'")
            result = json.dumps(data, ensure_ascii=False, indent=2)
            return result.encode("utf-8")

        return body

    except json.JSONDecodeError as e:
        logger.error(f"json_modify: Invalid JSON - {e}")
        return body
    except Exception as e:
        logger.error(f"json_modify error: {e}")
        return body


def _modify_json_path(data: Any, path: str, action: str, value: Any) -> bool:
    """Modify JSON data at specified path.

    Args:
        data: JSON data structure
        path: Dot-notation path (e.g., "user.name", "items[0].price")
        action: Operation (set, delete, append, increment)
        value: Value for operation

    Returns:
        True if modification was made, False otherwise
    """
    # Split path into segments
    segments = _parse_json_path(path)

    if not segments:
        return False

    # Navigate to parent of target
    current = data
    for i, segment in enumerate(segments[:-1]):
        if isinstance(segment, int):
            # Array index
            if not isinstance(current, list) or segment >= len(current):
                return False
            current = current[segment]
        else:
            # Object key
            if not isinstance(current, dict):
                return False
            if segment not in current:
                # Create intermediate objects as needed for set operations
                if action == "set":
                    current[segment] = {}
                else:
                    return False
            current = current[segment]

    # Apply action to final segment
    final_segment = segments[-1]

    if action == "set":
        if isinstance(final_segment, int):
            if isinstance(current, list):
                if final_segment < len(current):
                    current[final_segment] = value
                    return True
        else:
            if isinstance(current, dict):
                current[final_segment] = value
                return True

    elif action == "delete":
        if isinstance(final_segment, int):
            if isinstance(current, list) and final_segment < len(current):
                del current[final_segment]
                return True
        else:
            if isinstance(current, dict) and final_segment in current:
                del current[final_segment]
                return True

    elif action == "append":
        if isinstance(final_segment, str):
            target = current.get(final_segment)
            if isinstance(target, list):
                target.append(value)
                return True
            elif target is None and isinstance(current, dict):
                # Create new array
                current[final_segment] = [value]
                return True

    elif action == "increment":
        amount = value if value is not None else 1
        if isinstance(final_segment, int):
            if isinstance(current, list) and final_segment < len(current):
                if isinstance(current[final_segment], (int, float)):
                    current[final_segment] += amount
                    return True
        else:
            if isinstance(current, dict) and final_segment in current:
                if isinstance(current[final_segment], (int, float)):
                    current[final_segment] += amount
                    return True

    return False


def _parse_json_path(path: str) -> list:
    """Parse JSON path into segments.

    Examples:
        "user.name" -> ["user", "name"]
        "items[0].price" -> ["items", 0, "price"]
        "users[*].status" -> ["users", "*", "status"]

    Args:
        path: Dot-notation path with optional array indices

    Returns:
        List of path segments (strings and ints)
    """
    segments = []
    parts = path.split(".")

    for part in parts:
        # Check for array index notation
        if "[" in part and "]" in part:
            # Split into key and index
            key, rest = part.split("[", 1)
            if key:
                segments.append(key)

            # Extract index
            index_str = rest.split("]", 1)[0]
            if index_str == "*":
                segments.append("*")
            else:
                try:
                    segments.append(int(index_str))
                except ValueError:
                    segments.append(index_str)
        else:
            segments.append(part)

    return segments


# Hook registry for easy lookup
BUILTIN_PRE_HOOKS = {
    "redirect_301": redirect_301,
    "redirect_302": redirect_302,
    "gone_410": gone_410,
    "not_found_404": not_found_404,
    "static_html": static_html,
}

BUILTIN_POST_HOOKS = {
    "url_rewrite": url_rewrite,
    "text_rewrite": text_rewrite,
    "html_rewrite": html_rewrite,
    "link_rewrite": link_rewrite,
    "xpath_replace_from_url": xpath_replace_from_url,
    "json_modify": json_modify,
}
