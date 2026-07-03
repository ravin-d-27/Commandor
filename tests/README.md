# Tests

This directory contains the pytest-based test suite for Commandor.

## Layout

    tests/
        conftest.py              shared fixtures (tmp dirs, isolated config)
        test_ignore.py           .commandorignore pattern matching
        test_multimodal.py       image encoding + multimodal message builder
        test_exporter.py         /export for md / json / html
        test_tokenizer.py        tiktoken wrapper (incl. fallback)
        test_git_ops.py          /diff, git_status, git_commit, git_log
        test_diff_side_by_side.py side-by-side diff row builder
        test_web_ops.py          is_safe_url + http_request (mocked)
        test_file_ops.py         read / write / edit / glob / grep / etc.
        test_shell.py            run_command (no LLM)
        test_config.py           ConfigManager + get_api_key
        test_plugins.py          entry-point-based plugin loader
        test_agent_bridge.py     stream recovery/current-turn helpers
        test_terminal_widget.py  shell escape + @file reference helpers

Tests deliberately avoid live LLM calls and the network. Agent bridge
coverage focuses on pure helper behavior and recovery logic that can be
validated without calling a provider.

## Running

    python -m pip install -e ".[dev]"
    python -m pytest -v

The git tests are skipped automatically on systems without a ``git``
binary on ``$PATH``.

## CI

`.github/workflows/tests.yml` runs the suite on push / PR against
Python 3.10, 3.11, and 3.12.
