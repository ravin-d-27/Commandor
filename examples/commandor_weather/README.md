# Commandor Weather — example plugin

A minimal example showing how to add a custom tool to Commandor without
forking the project.

## Layout

    commandor_weather/
        pyproject.toml
        commandor_weather/
            __init__.py
            tools.py

## Install

    pip install -e .

## How it works

`pyproject.toml` declares an entry point in the `commandor.tools` group:

```toml
[project.entry-points."commandor.tools"]
register = "commandor_weather.tools:register"
```

When Commandor starts, it calls `importlib.metadata.entry_points(group="commandor.tools")`,
loads each entry point, calls it, and appends the returned tools to the
agent's tool list.  Use `/plugins` in the TUI to see loaded plugins.

## Writing your own

1. Create a new Python package with a `pyproject.toml`.
2. In your tools module, define `@tool`-decorated functions.
3. Expose a `register()` function that returns a list of tools.
4. Declare the entry point in `pyproject.toml` under
   `[project.entry-points."commandor.tools"]`.

The tools you return will be available to the agent in every mode
(`/agent`, `/assist`, `/plan`).  Tool names must be unique across all
loaded plugins and built-in tools.
