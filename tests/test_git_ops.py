"""Tests for commandor.utils.git_ops.

These tests shell out to the real ``git`` binary inside a throwaway
repository created with :class:`tmp_project`.  Skipped automatically
if git is not available on PATH.
"""
import shutil
import subprocess

import pytest

from commandor.utils.git_ops import (
    get_git_diff,
    get_git_status,
    git_commit,
    git_log,
    is_git_repo,
)


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git binary not available on this system",
)


@pytest.fixture
def git_repo(tmp_project):
    """A freshly-initialised git repo with one commit."""
    def _run(*args):
        return subprocess.run(
            ["git", *args],
            cwd=tmp_project,
            capture_output=True,
            text=True,
            check=True,
        )

    _run("init", "-q", "--initial-branch=main")
    _run("config", "user.email", "test@example.com")
    _run("config", "user.name", "Test User")
    (tmp_project / "README.md").write_text("hello\n", encoding="utf-8")
    _run("add", "README.md")
    _run("commit", "-q", "-m", "initial")
    return tmp_project


class TestIsGitRepo:
    def test_inside_repo(self, git_repo):
        assert is_git_repo(cwd=str(git_repo)) is True

    def test_outside_repo(self, tmp_project):
        assert is_git_repo(cwd=str(tmp_project)) is False


class TestGetGitStatus:
    def test_clean_tree(self, git_repo):
        out = get_git_status(cwd=str(git_repo))
        assert "clean" in out.lower()

    def test_dirty_tree(self, git_repo):
        (git_repo / "README.md").write_text("hello world\n", encoding="utf-8")
        (git_repo / "new.txt").write_text("new\n", encoding="utf-8")
        out = get_git_status(cwd=str(git_repo))
        assert "README.md" in out
        assert "new.txt" in out

    def test_not_a_repo(self, tmp_project):
        out = get_git_status(cwd=str(tmp_project))
        assert "not a git repository" in out.lower()


class TestGetGitDiff:
    def test_working_tree_diff(self, git_repo):
        (git_repo / "README.md").write_text("hello world\n", encoding="utf-8")
        out = get_git_diff(cwd=str(git_repo))
        assert "hello world" in out
        assert "diff" in out.lower() or "git diff" in out.lower()

    def test_no_diff_returns_placeholder(self, git_repo):
        out = get_git_diff(cwd=str(git_repo))
        assert "no" in out.lower() and "changes" in out.lower()

    def test_path_filter(self, git_repo):
        (git_repo / "a.txt").write_text("aaa\n", encoding="utf-8")
        (git_repo / "b.txt").write_text("bbb\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "."], cwd=git_repo, check=True, capture_output=True
        )
        out = get_git_diff(cwd=str(git_repo), staged=True, path="a.txt")
        assert "a.txt" in out
        assert "b.txt" not in out

    def test_staged_diff(self, git_repo):
        (git_repo / "README.md").write_text("staged change\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "README.md"], cwd=git_repo, check=True, capture_output=True
        )
        out = get_git_diff(cwd=str(git_repo), staged=True)
        assert "staged" in out.lower()
        assert "staged change" in out


class TestGitCommit:
    def test_basic_commit(self, git_repo):
        (git_repo / "new.txt").write_text("x\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "new.txt"], cwd=git_repo, check=True, capture_output=True
        )
        out = git_commit("add new file", cwd=str(git_repo))
        assert "Committed" in out
        assert "add new file" in out

    def test_add_all(self, git_repo):
        (git_repo / "untracked.txt").write_text("z\n", encoding="utf-8")
        out = git_commit("auto add", add_all=True, cwd=str(git_repo))
        assert "Committed" in out
        # Verify the file is now tracked
        proc = subprocess.run(
            ["git", "ls-files"], cwd=git_repo, capture_output=True, text=True
        )
        assert "untracked.txt" in proc.stdout

    def test_empty_message_refused(self, git_repo):
        out = git_commit("   ", cwd=str(git_repo))
        assert "refused" in out.lower() or "empty" in out.lower()

    def test_not_a_repo(self, tmp_project):
        out = git_commit("x", cwd=str(tmp_project))
        assert "not a git" in out.lower()


class TestGitLog:
    def test_returns_commits(self, git_repo):
        # We already have the initial commit
        out = git_log(n=5, cwd=str(git_repo))
        assert "initial" in out

    def test_empty_repo(self, tmp_project):
        # No commits at all
        subprocess.run(
            ["git", "init", "-q"], cwd=tmp_project, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "a@b.c"],
            cwd=tmp_project, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "X"],
            cwd=tmp_project, check=True, capture_output=True,
        )
        out = git_log(n=5, cwd=str(tmp_project))
        assert "no commits" in out.lower()

    def test_not_a_repo(self, tmp_project):
        out = git_log(n=5, cwd=str(tmp_project))
        assert "not a git" in out.lower()
