"""Tests for commandor.utils.exporter."""
import json

import pytest

from commandor.utils.exporter import (
    EXPORTERS,
    export_for_format,
    export_html,
    export_json,
    export_markdown,
)


SAMPLE_LOG = [
    {"role": "user", "mode": "agent", "content": "Find the bug in foo.py"},
    {"role": "ai", "content": "I see a typo on line 3."},
    {"role": "user", "mode": "plan", "content": "Now plan a refactor"},
    {"role": "ai", "content": "1. Extract helper\n2. Add tests"},
]


class TestExportMarkdown:
    def test_basic_structure(self):
        out = export_markdown(SAMPLE_LOG, session_name="test-session")
        assert "# Commandor Session Export" in out
        assert "**Session:** test-session" in out
        assert "USER" in out
        assert "Commandor" in out
        assert "Find the bug" in out

    def test_no_session(self):
        out = export_markdown(SAMPLE_LOG)
        assert "# Commandor Session Export" in out
        assert "**Session:**" not in out

    def test_metadata_block(self):
        out = export_markdown(
            SAMPLE_LOG,
            session_name="s",
            metadata={"provider": "gemini", "model": "gemini-2.5-flash"},
        )
        assert "**provider:** gemini" in out
        assert "**model:** gemini-2.5-flash" in out

    def test_empty_log(self):
        out = export_markdown([])
        # Should not crash, should have the title
        assert "# Commandor Session Export" in out


class TestExportJson:
    def test_round_trip(self):
        out = export_json(SAMPLE_LOG, session_name="s")
        parsed = json.loads(out)
        assert parsed["session_name"] == "s"
        assert len(parsed["messages"]) == 4
        assert parsed["messages"][0]["role"] == "user"
        assert parsed["messages"][0]["content"] == "Find the bug in foo.py"
        assert "exported_at" in parsed
        assert isinstance(parsed["exported_at"], str)

    def test_metadata_sanitised(self):
        out = export_json([], metadata={"plain": "yes", "set": {1, 2, 3}})
        parsed = json.loads(out)
        # set is not JSON-serialisable, gets coerced to str
        assert parsed["metadata"]["plain"] == "yes"
        assert isinstance(parsed["metadata"]["set"], str)


class TestExportHtml:
    def test_basic_render(self):
        out = export_html(SAMPLE_LOG, session_name="s")
        assert "<!doctype html>" in out
        assert "s" in out
        assert "USER" in out
        assert "COMMANDOR" in out
        # Escapes angle brackets
        assert "<script>" not in out  # no user input has it; escape worked

    def test_escapes_dangerous_content(self):
        log = [{"role": "user", "content": "<script>alert(1)</script>"}]
        out = export_html(log)
        assert "<script>" not in out
        assert "&lt;script&gt;" in out

    def test_code_fence(self):
        log = [{"role": "ai", "content": "```python\nprint(1)\n```"}]
        out = export_html(log)
        assert "<pre>" in out
        assert "print(1)" in out

    def test_inline_code(self):
        log = [{"role": "ai", "content": "Use `foo()` to call foo."}]
        out = export_html(log)
        assert "<code>foo()</code>" in out

    def test_bold_and_italic(self):
        log = [{"role": "ai", "content": "**bold** and *italic*"}]
        out = export_html(log)
        assert "<strong>bold</strong>" in out
        assert "<em>italic</em>" in out

    def test_bullet_list(self):
        log = [{"role": "ai", "content": "- one\n- two\n- three"}]
        out = export_html(log)
        assert "<ul>" in out
        assert "<li>one</li>" in out
        assert "<li>two</li>" in out


class TestExportForFormat:
    def test_dispatch(self):
        for fmt in ("md", "markdown", "json", "html"):
            content, normalised = export_for_format(fmt, SAMPLE_LOG, "s")
            assert content
            assert normalised in {"md", "json", "html"}

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError):
            export_for_format("rtf", SAMPLE_LOG, "s")

    def test_extension_normalisation(self):
        content, normalised = export_for_format(".JSON", [], "s")
        assert normalised == "json"
        json.loads(content)  # valid JSON

    def test_exporters_registry(self):
        assert "md" in EXPORTERS
        assert "json" in EXPORTERS
        assert "html" in EXPORTERS
