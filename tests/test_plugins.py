"""Tests for commandor.agent.plugins.

The plugin system uses Python's entry-point metadata.  We register a
fake entry point in :func:`_install_fake_plugin` and then call
``load_plugins`` to verify discovery works.
"""
from types import SimpleNamespace

import pytest

from commandor.agent import plugins
from commandor.agent.plugins import (
    ENTRY_POINT_GROUP,
    get_all_tools_with_plugins,
    get_load_errors,
    load_plugins,
)


class _FakeTool:
    """A trivial duck-typed tool that quacks like a LangChain BaseTool."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description


def _fake_entry_point(name: str, tool: _FakeTool | None = None,
                      raises: Exception | None = None):
    """Return a SimpleNamespace that mimics importlib.metadata.EntryPoint."""

    def _load():
        if raises is not None:
            raise raises
        return _FakeTool if tool is None else _FakeTool

    ep = SimpleNamespace(
        name=name,
        group=ENTRY_POINT_GROUP,
        value="fake:register",
        load=_load,
    )
    return ep


def test_entry_point_group_constant():
    assert ENTRY_POINT_GROUP == "commandor.tools"


def test_load_plugins_returns_list():
    tools = load_plugins(force_reload=True)
    assert isinstance(tools, list)


def test_get_all_tools_with_plugins_returns_tools():
    tools = get_all_tools_with_plugins(force_reload=True)
    assert isinstance(tools, list)
    assert len(tools) > 0
    # Each item has a .name
    for t in tools:
        assert hasattr(t, "name")


def test_get_load_errors_is_list():
    errs = get_load_errors()
    assert isinstance(errs, list)


def test_duplicate_tool_name_recorded_as_error(monkeypatch):
    """If two plugins return tools with the same name, the second is dropped
    and an error is recorded."""

    class Tool1:
        name = "duplicated_tool"
        description = "first"

    class Tool2:
        name = "duplicated_tool"  # same name
        description = "second"

    def register1():
        return [Tool1()]

    def register2():
        return [Tool2()]

    fake_eps = [
        SimpleNamespace(name="plug1", group=ENTRY_POINT_GROUP, value="x:register", load=lambda: register1),
        SimpleNamespace(name="plug2", group=ENTRY_POINT_GROUP, value="x:register", load=lambda: register2),
    ]

    def fake_entry_points(*, group):
        return fake_eps if group == ENTRY_POINT_GROUP else []

    monkeypatch.setattr(plugins, "entry_points", fake_entry_points)
    tools = load_plugins(force_reload=True)

    names = [t.name for t in tools if t.name == "duplicated_tool"]
    assert len(names) == 1
    # And a load error was captured
    errs = get_load_errors()
    assert any("duplicated_tool" in str(e) for e in errs)


def test_loading_error_is_caught(monkeypatch):
    """If an entry point's load() raises, it's recorded and other tools still load."""

    def _bad_load():
        raise ImportError("simulated broken plugin")

    fake_eps = [
        SimpleNamespace(name="broken", group=ENTRY_POINT_GROUP, value="x:load", load=_bad_load),
    ]

    monkeypatch.setattr(
        plugins,
        "entry_points",
        lambda *, group: fake_eps if group == ENTRY_POINT_GROUP else [],
    )
    load_plugins(force_reload=True)
    errs = get_load_errors()
    assert any("broken" in str(e) for e in errs)


def test_register_callable_returning_non_list_is_rejected(monkeypatch):
    """A register() that returns a non-list is treated as an error, not a crash."""

    def bad_register():
        return "not a list"

    fake_eps = [
        SimpleNamespace(name="weird", group=ENTRY_POINT_GROUP, value="x:reg", load=lambda: bad_register),
    ]
    monkeypatch.setattr(
        plugins,
        "entry_points",
        lambda *, group: fake_eps if group == ENTRY_POINT_GROUP else [],
    )
    load_plugins(force_reload=True)
    errs = get_load_errors()
    assert any("weird" in str(e) for e in errs)
