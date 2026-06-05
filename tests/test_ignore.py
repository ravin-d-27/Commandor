"""Tests for commandor.utils.ignore.IgnoreMatcher."""
from pathlib import Path

import pytest

from commandor.utils.ignore import IgnoreMatcher, _match_one, _parse_patterns


# ---------------------------------------------------------------------------
# Pattern parsing
# ---------------------------------------------------------------------------

class TestParsePatterns:
    def test_blank_and_comment_lines_are_skipped(self):
        ignores, reincludes = _parse_patterns(
            "# this is a comment\n"
            "\n"
            "  \n"
            "*.secret\n"
        )
        assert ignores == ["*.secret"]
        assert reincludes == []

    def test_reinclude_marker(self):
        ignores, reincludes = _parse_patterns(
            "*.secret\n"
            "!README.secret\n"
        )
        assert ignores == ["*.secret"]
        assert reincludes == ["README.secret"]

    def test_strips_whitespace(self):
        ignores, reincludes = _parse_patterns("   *.log   \n")
        assert ignores == ["*.log"]
        assert reincludes == []


# ---------------------------------------------------------------------------
# Single-pattern matching
# ---------------------------------------------------------------------------

class TestMatchOne:
    def test_simple_glob(self):
        assert _match_one("*.log", "foo.log") is True
        assert _match_one("*.log", "foo.txt") is False

    def test_anchored_pattern(self):
        assert _match_one("/build/", "build/x.o") is True
        # build/x.o is NOT matchable by an unanchored "build" either, but
        # the trailing-slash convention is directory-only.
        assert _match_one("/build/", "src/build/x.o") is False

    def test_double_star(self):
        assert _match_one("**/*.key", "a/b/c/secret.key") is True

    def test_literal_name(self):
        assert _match_one("id_rsa", "a/b/id_rsa") is True
        assert _match_one("id_rsa", "a/b/not_me") is False

    def test_directory_pattern(self):
        # Pattern "node_modules" with no slash should match the dir anywhere
        assert _match_one("node_modules", "node_modules/foo.js") is True


# ---------------------------------------------------------------------------
# IgnoreMatcher against a real project tree
# ---------------------------------------------------------------------------

class TestIgnoreMatcher:
    def _write_ignore(self, base: Path, text: str) -> Path:
        f = base / ".commandorignore"
        f.write_text(text, encoding="utf-8")
        return f

    def test_empty_tree_loads_no_rules(self, tmp_project: Path):
        m = IgnoreMatcher(base_dir=str(tmp_project))
        assert m.source is None
        assert m.pattern_count == 0
        assert m.matches("anything") is False

    def test_glob_pattern(self, tmp_project: Path):
        self._write_ignore(tmp_project, "*.secret\n")
        m = IgnoreMatcher(base_dir=str(tmp_project))
        assert m.matches("foo.secret") is True
        assert m.matches("foo.txt") is False

    def test_anchored_vs_unanchored(self, tmp_project: Path):
        self._write_ignore(tmp_project, "/build/\n")
        m = IgnoreMatcher(base_dir=str(tmp_project))
        assert m.matches("build") is True
        assert m.matches("build/output.o") is True
        # Anchored → not matched when nested under another dir
        assert m.matches("src/build/output.o") is False

    def test_reinclude_toggles_off(self, tmp_project: Path):
        self._write_ignore(
            tmp_project,
            "*.secret\n"
            "!README.secret\n",
        )
        m = IgnoreMatcher(base_dir=str(tmp_project))
        assert m.matches("foo.secret") is True
        assert m.matches("README.secret") is False

    def test_is_ignored_absolute_path(self, tmp_project: Path):
        self._write_ignore(tmp_project, "*.log\n")
        m = IgnoreMatcher(base_dir=str(tmp_project))
        (tmp_project / "a.log").write_text("x", encoding="utf-8")
        (tmp_project / "a.txt").write_text("x", encoding="utf-8")
        assert m.is_ignored(str(tmp_project / "a.log")) is True
        assert m.is_ignored(str(tmp_project / "a.txt")) is False

    def test_is_ignored_outside_base_returns_false(self, tmp_project: Path):
        self._write_ignore(tmp_project, "*.log\n")
        m = IgnoreMatcher(base_dir=str(tmp_project))
        # Path outside base_dir is treated as not-ignored
        assert m.is_ignored("/etc/passwd") is False

    def test_filter_drops_ignored(self, tmp_project: Path):
        self._write_ignore(tmp_project, "*.log\n")
        m = IgnoreMatcher(base_dir=str(tmp_project))
        paths = [
            str(tmp_project / "a.log"),
            str(tmp_project / "b.txt"),
            str(tmp_project / "c.log"),
        ]
        kept = m.filter(paths)
        assert len(kept) == 1
        assert kept[0].endswith("b.txt")

    def test_walks_upward(self, tmp_project: Path):
        # Place the ignore in a parent and a child subdir; child should win.
        parent = tmp_project / "parent"
        parent.mkdir()
        (parent / ".commandorignore").write_text("*.ignore_me\n", encoding="utf-8")
        child = parent / "child"
        child.mkdir()
        m = IgnoreMatcher(base_dir=str(child))
        assert m.source == parent / ".commandorignore"
        assert m.matches("foo.ignore_me") is True

    def test_summary_text(self, tmp_project: Path):
        f = self._write_ignore(tmp_project, "*.log\n!keep.log\n")
        m = IgnoreMatcher(base_dir=str(tmp_project))
        s = m.summary()
        assert "1 ignore" in s
        assert "1 re-include" in s
        assert str(f) in s

    def test_summary_when_no_rules(self, tmp_project: Path):
        m = IgnoreMatcher(base_dir=str(tmp_project))
        assert m.summary() == "no .commandorignore loaded"
