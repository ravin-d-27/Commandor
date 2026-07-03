"""HTTP / web utilities used by the web-fetch and HTTP request tools.

Public API:
    fetch_url(url, timeout, max_chars) -> str
        Fetch a URL, strip HTML tags, return plain text.  Truncates very
        long pages to keep context consumption sane.
    http_request(method, url, headers, body, timeout, max_chars) -> str
        Generic HTTP request — GET / POST / PUT / DELETE / PATCH.  Returns
        status, headers, and body (body truncated to max_chars).
    is_safe_url(url) -> bool
        Reject file://, gopher:// and other non-http schemes to avoid
        SSRF / local-file-read abuse.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx

# Sensible default headers (some sites 403 default UAs)
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) Commandor/0.2 "
        "(+https://github.com/ravin-d-27/Commandor)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
}

_ALLOWED_SCHEMES = {"http", "https"}


def is_safe_url(url: str) -> bool:
    """True if the URL uses a permitted scheme and a real hostname."""
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme.lower() not in _ALLOWED_SCHEMES:
        return False
    if not p.netloc:
        return False
    return True


def fetch_url(url: str, timeout: int = 30, max_chars: int = 50_000) -> str:
    """Fetch *url* and return plain-text content (HTML tags stripped).

    Args:
        url:       http(s) URL to fetch.
        timeout:   Seconds to wait before giving up.
        max_chars: Truncate response to this many characters.

    Returns:
        A string with the page title (if any) and visible text.
    """
    if not is_safe_url(url):
        return f"Error: refused to fetch URL with non-http(s) scheme: {url}"

    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            resp = client.get(url, headers=_DEFAULT_HEADERS)
    except httpx.HTTPError as exc:
        return f"Error fetching {url}: {exc}"

    return _format_response(url, resp, max_chars)


def http_request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: str = "",
    timeout: int = 30,
    max_chars: int = 50_000,
) -> str:
    """Send a generic HTTP request and return the response as text.

    Args:
        method:    HTTP verb (GET, POST, PUT, PATCH, DELETE, HEAD).
        url:       Target URL (http/https only).
        headers:   Optional extra request headers (dict).
        body:      Optional request body (string).  If the body looks like
                   JSON, it is sent as-is with Content-Type: application/json.
        timeout:   Seconds before giving up.
        max_chars: Truncate response body to this many characters.

    Returns:
        A formatted string with status, content-type, and the body.
    """
    if not is_safe_url(url):
        return f"Error: refused to fetch URL with non-http(s) scheme: {url}"

    method = method.upper().strip()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
        return f"Error: unsupported HTTP method: {method}"

    req_headers = dict(_DEFAULT_HEADERS)
    if headers:
        req_headers.update(headers)

    content: Any = None
    if body:
        # If body parses as JSON, send it as JSON automatically
        stripped = body.strip()
        if stripped.startswith(("{", "[")) and stripped.endswith(("}", "]")):
            try:
                content = json.loads(stripped)
                req_headers.setdefault("Content-Type", "application/json")
            except json.JSONDecodeError:
                content = body
        else:
            content = body
            # form-style if it looks like key=value pairs, else raw text
            if "=" in stripped and "\n" not in stripped:
                req_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            resp = client.request(method, url, headers=req_headers, content=content)
    except httpx.HTTPError as exc:
        return f"Error {method} {url}: {exc}"

    return _format_response(url, resp, max_chars, method=method)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_response(
    url: str,
    resp: httpx.Response,
    max_chars: int,
    method: str = "GET",
) -> str:
    """Format an httpx.Response as a plain-text block, stripping HTML if needed."""
    status_line = f"HTTP {resp.status_code} {resp.reason_phrase}"
    content_type = resp.headers.get("content-type", "").lower()
    is_json = "json" in content_type
    is_html = "html" in content_type

    text = resp.text
    truncated = False
    if len(text) > max_chars:
        text = text[:max_chars]
        truncated = True

    if is_json:
        try:
            parsed = json.loads(text)
            text = json.dumps(parsed, indent=2)[:max_chars]
        except json.JSONDecodeError:
            pass  # leave raw text if it's not valid JSON
    elif is_html:
        text = _html_to_text(text)

    suffix = f"\n\n… (truncated to {max_chars:,} chars)" if truncated else ""
    header = f"[{method} {url}] {status_line}  ({content_type or 'unknown'})"
    return f"{header}\n\n{text}{suffix}"


def _html_to_text(html: str) -> str:
    """Best-effort HTML → plain text using BeautifulSoup.

    Falls back to a crude regex strip if bs4 is unavailable.
    """
    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html, "html.parser")
        # Drop script/style entirely
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        # Get text with a sensible separator
        text = soup.get_text(separator="\n", strip=True)
        # Collapse 3+ blank lines down to 2
        lines = [line.rstrip() for line in text.splitlines()]
        cleaned: list[str] = []
        blank = 0
        for line in lines:
            if not line:
                blank += 1
                if blank <= 1:
                    cleaned.append("")
            else:
                blank = 0
                cleaned.append(line)
        return "\n".join(cleaned)
    except Exception:
        # Crude fallback
        import re
        no_tags = re.sub(r"<[^>]+>", " ", html)
        no_tags = re.sub(r"\s+", " ", no_tags)
        return no_tags.strip()
