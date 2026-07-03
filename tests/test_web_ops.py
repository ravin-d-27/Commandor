"""Tests for commandor.utils.web_ops.

We don't hit the network — only the URL-safety filter and the JSON
auto-detection helper logic.  The full request path is exercised
via a mocked httpx.Client in test_http_request.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from commandor.utils.web_ops import (
    _ALLOWED_SCHEMES,
    _format_response,
    http_request,
    is_safe_url,
)


class TestIsSafeUrl:
    @pytest.mark.parametrize("url", [
        "http://example.com/",
        "https://example.com/path?q=1",
        "https://localhost:8080",
        "http://192.168.1.1/",
    ])
    def test_accepted(self, url):
        assert is_safe_url(url) is True

    @pytest.mark.parametrize("url", [
        "file:///etc/passwd",
        "gopher://evil.example/",
        "ftp://example.com/file",
        "javascript:alert(1)",
        "",
        "not-a-url",
    ])
    def test_rejected(self, url):
        assert is_safe_url(url) is False

    def test_scheme_check_is_case_insensitive(self):
        assert is_safe_url("HTTPS://Example.com/") is True

    def test_allowed_schemes_set(self):
        assert _ALLOWED_SCHEMES == {"http", "https"}


class TestHttpRequest:
    def test_unsafe_url_short_circuits(self):
        out = http_request("GET", "file:///etc/passwd")
        assert "refused" in out.lower()

    def test_unsupported_method(self):
        # Bypass the URL safety check by using a safe URL
        with patch("commandor.utils.web_ops.httpx.Client") as MockClient:
            out = http_request("BREW", "https://example.com/")
        assert "unsupported" in out.lower()
        MockClient.assert_not_called()

    def test_get_passes_through(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.reason_phrase = "OK"
        fake_resp.headers = {"content-type": "text/plain"}
        fake_resp.text = "hello"
        fake_client = MagicMock()
        fake_client.__enter__ = MagicMock(return_value=fake_client)
        fake_client.__exit__ = MagicMock(return_value=False)
        fake_client.request.return_value = fake_resp

        with patch("commandor.utils.web_ops.httpx.Client", return_value=fake_client):
            out = http_request("GET", "https://example.com/")

        assert "HTTP 200" in out
        assert "hello" in out
        # Default UA was sent
        called = fake_client.request.call_args
        assert called.args[0] == "GET"
        assert "User-Agent" in called.kwargs["headers"]

    def test_post_json_body_detected(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 201
        fake_resp.reason_phrase = "Created"
        fake_resp.headers = {"content-type": "application/json"}
        fake_resp.text = json.dumps({"ok": True})
        fake_client = MagicMock()
        fake_client.__enter__ = MagicMock(return_value=fake_client)
        fake_client.__exit__ = MagicMock(return_value=False)
        fake_client.request.return_value = fake_resp

        with patch("commandor.utils.web_ops.httpx.Client", return_value=fake_client):
            out = http_request("POST", "https://api.example/x", body='{"a":1}')

        assert "HTTP 201" in out
        kwargs = fake_client.request.call_args.kwargs
        assert kwargs["content"] == {"a": 1}
        assert kwargs["headers"]["Content-Type"] == "application/json"

    def test_post_form_body_detected(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.reason_phrase = "OK"
        fake_resp.headers = {"content-type": "text/plain"}
        fake_resp.text = "ok"
        fake_client = MagicMock()
        fake_client.__enter__ = MagicMock(return_value=fake_client)
        fake_client.__exit__ = MagicMock(return_value=False)
        fake_client.request.return_value = fake_resp

        with patch("commandor.utils.web_ops.httpx.Client", return_value=fake_client):
            http_request("POST", "https://api.example/x", body="a=1&b=2")

        kwargs = fake_client.request.call_args.kwargs
        assert kwargs["headers"]["Content-Type"] == "application/x-www-form-urlencoded"

    def test_truncation_marker(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.reason_phrase = "OK"
        fake_resp.headers = {"content-type": "text/plain"}
        fake_resp.text = "x" * 10_000
        fake_client = MagicMock()
        fake_client.__enter__ = MagicMock(return_value=fake_client)
        fake_client.__exit__ = MagicMock(return_value=False)
        fake_client.request.return_value = fake_resp

        with patch("commandor.utils.web_ops.httpx.Client", return_value=fake_client):
            out = http_request("GET", "https://example.com/", max_chars=100)

        assert "truncated" in out


class TestFormatResponse:
    def test_html_stripped(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.reason_phrase = "OK"
        resp.headers = {"content-type": "text/html"}
        resp.text = "<html><body><h1>Hi</h1><p>world</p></body></html>"
        out = _format_response("https://x", resp, max_chars=10_000)
        # <h1> / <p> tags should be gone
        assert "<h1>" not in out
        assert "Hi" in out
        assert "world" in out

    def test_json_pretty_printed(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.reason_phrase = "OK"
        resp.headers = {"content-type": "application/json"}
        resp.text = '{"a":1,"b":2}'
        out = _format_response("https://x", resp, max_chars=10_000)
        parsed = json.loads(out.split("\n\n", 1)[1])
        assert parsed == {"a": 1, "b": 2}
