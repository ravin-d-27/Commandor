"""Tests for terminal input routing helpers."""

from commandor.widgets.terminal_widget import _shell_escape_command


def test_shell_escape_with_dollar_prefix():
    assert _shell_escape_command("$ ls -la") == "ls -la"


def test_shell_escape_with_bang_prefix():
    assert _shell_escape_command("!git status") == "git status"


def test_plain_text_is_not_shell():
    assert _shell_escape_command("fix the failing tests") is None


def test_dollar_variable_text_is_not_shell():
    assert _shell_escape_command("$HOME should stay natural text") is None


def test_empty_shell_escape_is_empty_string():
    assert _shell_escape_command("$") == ""
