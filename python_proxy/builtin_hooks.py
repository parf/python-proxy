"""Built-in hooks for common proxy operations."""

import logging
import re
from typing import Any, Dict, Optional

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


# Hook registry for easy lookup
BUILTIN_PRE_HOOKS = {
    "redirect_301": redirect_301,
    "redirect_302": redirect_302,
    "gone_410": gone_410,
    "not_found_404": not_found_404,
}

BUILTIN_POST_HOOKS = {
    "url_rewrite": url_rewrite,
    "text_rewrite": text_rewrite,
    "html_rewrite": html_rewrite,
}
