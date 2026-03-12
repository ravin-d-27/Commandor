"""Agent modes — slim dict-based implementation replacing the old ABC classes."""

from typing import Dict

# Map of mode name → human-readable description
MODES: Dict[str, str] = {
    "agent": "Fully autonomous — the AI uses tools freely, plans as needed, and executes until the task is done.",
    "chat":  "Conversation only — no tool access, just AI knowledge and reasoning.",
}


def list_modes() -> Dict[str, str]:
    """Return all available mode names and their descriptions."""
    return dict(MODES)


def get_mode(name: str) -> str:
    """Return the description for a mode, or raise ValueError for unknown modes."""
    if name not in MODES:
        raise ValueError(
            f"Unknown mode: '{name}'. Valid modes: {', '.join(MODES)}"
        )
    return MODES[name]
