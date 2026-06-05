"""Example Commandor plugin: a stub weather tool.

This file is here to document the plugin contract.  It is NOT installed
by default — it lives in the examples/ directory.  To use it:

    cd examples/commandor_weather
    pip install -e .
    # ... then run commandor and use /plugins to see it loaded

The real implementation would call a weather API; for the example we
return a deterministic stub so the wiring can be tested offline.
"""

from langchain_core.tools import tool


@tool
def get_weather_tool(city: str) -> str:
    """Return the current weather for *city*.

    This is a stub — a real plugin would call a weather API.  The point
    of this example is to demonstrate the registration pattern.

    Args:
        city: City name, e.g. 'Paris' or 'New York'.
    """
    return (
        f"(stub) The weather in {city} is sunny, 22°C, light breeze.  "
        "Replace this stub with a real API call (e.g. OpenWeatherMap)."
    )


def register():
    """Entry point called by Commandor.  Must return a list of tools."""
    return [get_weather_tool]
