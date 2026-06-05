"""Pytest configuration & shared fixtures.

Keep this module lightweight: no LLM/network imports.  Anything that
needs heavy deps should live in its own conftest.py.
"""

import os
import sys
from pathlib import Path

import pytest

# Make the project root importable so `import commandor.*` works
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Return a clean empty directory for the duration of one test."""
    return tmp_path


@pytest.fixture
def isolated_config(monkeypatch, tmp_path: Path):
    """Force ConfigManager to read/write inside tmp_path instead of ~/.commandor.

    Clears the cached global config manager so each test gets a fresh
    ConfigManager pointed at the temp dir.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))  # Windows
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))

    # Reset the module-level cache in config.py
    import commandor.config as _cfg

    monkeypatch.setattr(_cfg, "_config_manager", None)
    yield fake_home / ".commandor"
