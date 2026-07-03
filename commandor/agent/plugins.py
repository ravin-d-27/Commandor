"""Plugin system for Commandor.

Plugins are Python packages that expose an entry-point group called
``commandor.tools``.  Each entry point must be a callable that returns a
list of LangChain ``@tool``-decorated objects (or any object that quacks
like a BaseTool).

Example project layout::

    my_commandor_plugin/
        pyproject.toml
        my_commandor_plugin/
            __init__.py
            tools.py

    # pyproject.toml
    [project.entry-points."commandor.tools"]
    my_plugin = "my_commandor_plugin.tools:register"

    # tools.py
    from langchain_core.tools import tool

    @tool
    def my_special_tool(query: str) -> str: ...

    def register():
        return [my_special_tool]

Public API:
    load_plugins() -> list[BaseTool]
        Discover and return all registered plugin tools.  Cached.
    get_all_tools_with_plugins() -> list[BaseTool]
        The base ALL_TOOLS list + loaded plugin tools.
"""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Callable

ENTRY_POINT_GROUP = "commandor.tools"

_cache: list | None = None
_load_errors: list[str] = []


def _discover_entry_points() -> list:
    """Iterate over every registered entry point in the commandor.tools group."""
    try:
        eps = entry_points(group=ENTRY_POINT_GROUP)
    except Exception as exc:
        _load_errors.append(f"entry-point discovery failed: {exc}")
        return []
    # Python 3.10+ returns a SelectableView; older versions a dict-like.
    if hasattr(eps, "select"):
        eps = eps.select(group=ENTRY_POINT_GROUP)
    return list(eps)


def _resolve_registrar(ep) -> Callable | None:
    """Load the entry point's target object.  Returns None on failure."""
    try:
        return ep.load()
    except Exception as exc:  # noqa: BLE001
        _load_errors.append(f"plugin {ep.name!r} failed to load: {exc}")
        return None


def _call_registrar(registrar, ep_name: str) -> list:
    """Call *registrar* (a callable) and return its list of tools."""
    if not callable(registrar):
        _load_errors.append(
            f"plugin {ep_name!r}: registrar is not callable ({type(registrar).__name__})"
        )
        return []
    try:
        result = registrar()
    except Exception as exc:  # noqa: BLE001
        _load_errors.append(f"plugin {ep_name!r}: registrar raised {exc}")
        return []
    if not isinstance(result, list):
        _load_errors.append(
            f"plugin {ep_name!r}: registrar must return a list, got {type(result).__name__}"
        )
        return []
    return result


def load_plugins(force_reload: bool = False) -> list:
    """Return all plugin-discovered tools.  Result is cached.

    Args:
        force_reload: If True, ignore the cache and re-discover.

    Returns:
        A flat list of BaseTool / tool-decorated objects.
    """
    global _cache
    if _cache is not None and not force_reload:
        return list(_cache)

    _load_errors.clear()
    tools: list = []
    seen_names: set[str] = set()

    for ep in _discover_entry_points():
        registrar = _resolve_registrar(ep)
        if registrar is None:
            continue
        for tool_obj in _call_registrar(registrar, ep.name):
            name = getattr(tool_obj, "name", None) or getattr(tool_obj, "__name__", "?")
            if name in seen_names:
                _load_errors.append(
                    f"plugin {ep.name!r}: duplicate tool name {name!r} (skipped)"
                )
                continue
            seen_names.add(name)
            tools.append(tool_obj)

    _cache = tools
    return list(tools)


def get_load_errors() -> list[str]:
    """Return a copy of plugin-load errors (useful for /plugins diagnostics)."""
    return list(_load_errors)


def get_all_tools_with_plugins(force_reload: bool = False) -> list:
    """Return ALL_TOOLS plus any plugin tools.

    Imports ALL_TOOLS lazily to avoid a circular import (lc_tools imports
    plugin-aware code at call-time, not at module-load time).
    """
    from .lc_tools import ALL_TOOLS  # noqa: PLC0415
    return list(ALL_TOOLS) + load_plugins(force_reload=force_reload)
