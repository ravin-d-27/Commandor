"""Tests for commandor.utils.shell (the non-LLM parts only).

We do NOT call the real LLM API.  The ``run_command`` function spawns a
subprocess via /bin/sh, so we do exercise it with a benign command.
"""
import sys

import pytest

from commandor.utils.shell import get_working_directory, run_command


class TestRunCommand:
    def test_simple_command(self):
        out = run_command(f"{sys.executable} -c \"print('hello')\"", timeout=10)
        assert "hello" in out

    def test_nonzero_exit(self):
        out = run_command(f"{sys.executable} -c \"import sys; sys.exit(3)\"", timeout=10)
        assert "exit code" in out.lower() or "3" in out

    def test_stderr_captured(self):
        out = run_command(
            f"{sys.executable} -c \"import sys; sys.stderr.write('oops')\"",
            timeout=10,
        )
        assert "oops" in out

    def test_timeout_returns_error(self):
        out = run_command(f"{sys.executable} -c \"import time; time.sleep(10)\"", timeout=1)
        assert "timed out" in out.lower() or "timeout" in out.lower()

    def test_cwd_honoured(self, tmp_project):
        out = run_command("pwd", cwd=str(tmp_project), timeout=10)
        assert str(tmp_project) in out


class TestGetWorkingDirectory:
    def test_returns_string(self):
        cwd = get_working_directory()
        assert isinstance(cwd, str)
        assert cwd  # not empty
