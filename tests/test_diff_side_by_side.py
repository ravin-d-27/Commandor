"""Tests for commandor.utils.diff_side_by_side.

We avoid touching the global Rich Console (which writes to a real TTY);
we test the pure ``_compute_rows`` function directly.
"""
import pytest

from commandor.utils.diff_side_by_side import _compute_rows, _guess_lexer, _truncate


class TestGuessLexer:
    @pytest.mark.parametrize("path,expected", [
        ("foo.py", "python"),
        ("x.ts", "typescript"),
        ("X.PY", "python"),  # case insensitive
        ("no_ext", None),
        ("data.json", "json"),
        ("style.css", "css"),
    ])
    def test_known_extensions(self, path, expected):
        assert _guess_lexer(path) == expected

    def test_unknown_extension(self):
        assert _guess_lexer("file.qwerty") is None


class TestTruncate:
    def test_short_string_passes_through(self):
        assert _truncate("hello", 10) == "hello"

    def test_long_string_truncated_with_marker(self):
        out = _truncate("x" * 100, 10)
        assert out.endswith("…")
        assert len(out) == 10

    def test_zero_or_one_returns_empty(self):
        assert _truncate("hello", 0) == ""
        assert _truncate("hello", 1) == ""


class TestComputeRows:
    def test_identical_text_returns_no_rows(self):
        rows, _hunks = _compute_rows("a\nb\nc", "a\nb\nc")
        assert rows == []

    def test_pure_insertion(self):
        old = "line1\nline2\n"
        new = "line1\nline2\nline3\n"
        rows, _hunks = _compute_rows(old, new)
        kinds = [r[0] for r in rows]
        # Should have at least one "insert" and one hunk
        assert "insert" in kinds
        assert "hunk" in kinds

    def test_pure_deletion(self):
        old = "line1\nline2\nline3\n"
        new = "line1\nline3\n"
        rows, _hunks = _compute_rows(old, new)
        kinds = [r[0] for r in rows]
        assert "delete" in kinds
        assert "hunk" in kinds

    def test_replacement(self):
        old = "a\nb\nc\n"
        new = "a\nB\nc\n"
        rows, _hunks = _compute_rows(old, new)
        kinds = [r[0] for r in rows]
        assert "replace" in kinds

    def test_row_format_is_five_tuple(self):
        rows, _hunks = _compute_rows("a\n", "a\nb\n")
        assert all(len(r) == 5 for r in rows)
        kind, o_no, o_text, n_no, n_text = rows[0]
        # First row should be the hunk header
        assert kind == "hunk"
        assert o_text.startswith("@@")
        assert o_no is None and n_no is None

    def test_context_around_changes(self):
        # 10 lines of context, change line 3
        old = "\n".join(f"line{i}" for i in range(10))
        new = old.replace("line3", "CHANGED")
        rows, _hunks = _compute_rows(old, new, context=2)
        # We should see at least one 'equal' row from context
        kinds = [r[0] for r in rows]
        assert "equal" in kinds
