"""Tests for commandor.utils.file_ops."""
from pathlib import Path

import pytest

from commandor.utils import file_ops


class TestReadFile:
    def test_basic_read(self, tmp_project: Path):
        f = tmp_project / "a.txt"
        f.write_text("one\ntwo\nthree\n", encoding="utf-8")
        assert file_ops.read_file(str(f)) == "one\ntwo\nthree\n"

    def test_missing_raises(self, tmp_project: Path):
        with pytest.raises(FileNotFoundError):
            file_ops.read_file(str(tmp_project / "missing.txt"))

    def test_directory_raises(self, tmp_project: Path):
        with pytest.raises(ValueError):
            file_ops.read_file(str(tmp_project))

    def test_limit_truncates(self, tmp_project: Path):
        f = tmp_project / "a.txt"
        f.write_text("\n".join(f"line{i}" for i in range(100)), encoding="utf-8")
        out = file_ops.read_file(str(f), limit=5)
        assert "line0" in out
        assert "line4" in out
        assert "truncated" in out.lower()

    def test_binary_file_returns_marker(self, tmp_project: Path):
        f = tmp_project / "blob.bin"
        f.write_bytes(b"\x00\x01\x02\xff")
        out = file_ops.read_file(str(f))
        assert "Binary" in out


class TestWriteFile:
    def test_creates_parent_dirs(self, tmp_project: Path):
        f = tmp_project / "deep" / "nested" / "x.txt"
        file_ops.write_file(str(f), "hi", create_dirs=True)
        assert f.read_text(encoding="utf-8") == "hi"

    def test_overwrites_existing(self, tmp_project: Path):
        f = tmp_project / "a.txt"
        f.write_text("old", encoding="utf-8")
        file_ops.write_file(str(f), "new")
        assert f.read_text(encoding="utf-8") == "new"

    def test_return_value(self, tmp_project: Path):
        f = tmp_project / "a.txt"
        ret = file_ops.write_file(str(f), "x")
        assert "Successfully" in ret
        assert str(f) in ret


class TestEditFile:
    def test_basic_replacement(self, tmp_project: Path):
        f = tmp_project / "a.txt"
        f.write_text("hello world", encoding="utf-8")
        file_ops.edit_file(str(f), "world", "there")
        assert f.read_text(encoding="utf-8") == "hello there"

    def test_missing_old_raises(self, tmp_project: Path):
        f = tmp_project / "a.txt"
        f.write_text("hello", encoding="utf-8")
        with pytest.raises(ValueError):
            file_ops.edit_file(str(f), "goodbye", "hi")

    def test_missing_file_raises(self, tmp_project: Path):
        with pytest.raises(FileNotFoundError):
            file_ops.edit_file(str(tmp_project / "missing.txt"), "x", "y")

    def test_replaces_all_occurrences(self, tmp_project: Path):
        f = tmp_project / "a.txt"
        f.write_text("aaa", encoding="utf-8")
        file_ops.edit_file(str(f), "a", "b")
        assert f.read_text(encoding="utf-8") == "bbb"


class TestCreateDirectory:
    def test_creates_recursively(self, tmp_project: Path):
        d = tmp_project / "a" / "b" / "c"
        file_ops.create_directory(str(d))
        assert d.is_dir()


class TestListDirectory:
    def test_basic_listing(self, tmp_project: Path):
        (tmp_project / "a.txt").write_text("x", encoding="utf-8")
        (tmp_project / "b").mkdir()
        out = file_ops.list_directory(str(tmp_project))
        assert "a.txt" in out
        assert "b" in out

    def test_missing_raises(self, tmp_project: Path):
        with pytest.raises(FileNotFoundError):
            file_ops.list_directory(str(tmp_project / "missing"))

    def test_not_a_directory_raises(self, tmp_project: Path):
        f = tmp_project / "f.txt"
        f.write_text("x", encoding="utf-8")
        with pytest.raises(ValueError):
            file_ops.list_directory(str(f))

    def test_empty_directory(self, tmp_project: Path):
        out = file_ops.list_directory(str(tmp_project))
        assert "empty" in out.lower()


class TestGlobFiles:
    def test_simple_glob(self, tmp_project: Path):
        for name in ("a.py", "b.py", "c.txt"):
            (tmp_project / name).write_text("x", encoding="utf-8")
        out = file_ops.glob_files("*.py", str(tmp_project))
        assert "a.py" in out
        assert "b.py" in out
        assert "c.txt" not in out

    def test_no_matches(self, tmp_project: Path):
        out = file_ops.glob_files("*.zzz", str(tmp_project))
        assert "No files" in out


class TestSearchInFiles:
    def test_finds_pattern(self, tmp_project: Path):
        f = tmp_project / "a.py"
        f.write_text("def foo():\n    return 42\n", encoding="utf-8")
        out = file_ops.search_in_files("def foo", str(tmp_project), "*.py")
        assert "foo" in out
        assert "a.py:1" in out

    def test_no_match(self, tmp_project: Path):
        out = file_ops.search_in_files("zzz", str(tmp_project), "*.py")
        assert "No matches" in out


class TestDeleteFile:
    def test_delete_file(self, tmp_project: Path):
        f = tmp_project / "a.txt"
        f.write_text("x", encoding="utf-8")
        file_ops.delete_file(str(f))
        assert not f.exists()

    def test_delete_directory(self, tmp_project: Path):
        d = tmp_project / "d"
        d.mkdir()
        (d / "a").write_text("x", encoding="utf-8")
        file_ops.delete_file(str(d))
        assert not d.exists()

    def test_missing_raises(self, tmp_project: Path):
        with pytest.raises(FileNotFoundError):
            file_ops.delete_file(str(tmp_project / "missing"))


class TestGetFileInfo:
    def test_file_info(self, tmp_project: Path):
        f = tmp_project / "a.txt"
        f.write_text("hi\nthere\n", encoding="utf-8")
        out = file_ops.get_file_info(str(f))
        assert "Path:" in out
        assert "File" in out
        assert "Size:" in out
        assert "Lines:" in out

    def test_directory_info(self, tmp_project: Path):
        out = file_ops.get_file_info(str(tmp_project))
        assert "Directory" in out

    def test_missing_raises(self, tmp_project: Path):
        with pytest.raises(FileNotFoundError):
            file_ops.get_file_info(str(tmp_project / "missing"))
