"""Tests for terminal input routing and file-reference helpers."""

from commandor.widgets.terminal_widget import (
    _active_file_reference,
    _expand_files,
    _file_reference_completion,
    _file_reference_matches,
    _format_file_reference_completion,
    _shell_escape_command,
)


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


def test_active_file_reference_detects_current_token():
    assert _active_file_reference("explain @tests/test_", 20) == (
        8,
        20,
        "tests/test_",
    )


def test_active_file_reference_ignores_email_like_text():
    assert _active_file_reference("email user@example.com", 18) is None


def test_file_reference_matches_root_and_nested_files(tmp_path):
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("print(1)", encoding="utf-8")
    (src / "model.py").write_text("class Model: pass", encoding="utf-8")

    assert "README.md" in _file_reference_matches("", cwd=str(tmp_path))
    assert "src/" in _file_reference_matches("s", cwd=str(tmp_path))
    assert "src/main.py" in _file_reference_matches("main", cwd=str(tmp_path))


def test_file_reference_completion_unique_file_adds_full_path(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_config.py").write_text("x", encoding="utf-8")

    matches = _file_reference_matches("test_config", cwd=str(tmp_path))
    assert _file_reference_completion("test_config", matches) == "tests/test_config.py"


def test_file_reference_completion_multiple_matches_common_prefix():
    matches = ["tests/test_config.py", "tests/test_file_ops.py"]
    assert _file_reference_completion("tes", matches) == "tests/test_"


def test_file_reference_completion_quotes_paths_with_spaces():
    assert _format_file_reference_completion("docs/My File.md") == '"docs/My File.md"'


def test_expand_files_supports_quoted_paths_with_spaces(tmp_path):
    target = tmp_path / "My File.md"
    target.write_text("hello from spaced file", encoding="utf-8")

    expanded, loaded = _expand_files('explain @"My File.md"', cwd=str(tmp_path))

    assert "hello from spaced file" in expanded
    assert loaded == ["My File.md"]
