"""textual_app.py — Commandor single-pane terminal application.

Single unified pane where:
  - Shell commands run directly (like a real terminal)
  - AI features are invoked via /slash commands
  - Batman dark theme (pure black and gold)

Keyboard shortcuts:
  Ctrl+Q   Quit
  Ctrl+L   Clear terminal
  Up/Down  Command history (handled in TerminalWidget)
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer

from .widgets.terminal_widget import TerminalWidget

# ---------------------------------------------------------------------------
# CSS — Batman dark theme (pure black and gold)
# ---------------------------------------------------------------------------

COMMANDOR_CSS = """
Screen {
    background: #000000;
}

TerminalWidget {
    height: 100%;
    layout: vertical;
    border: solid #ffd700;
    background: #000000;
}

#log {
    height: 1fr;
    background: #000000;
    color: #f5ecd0;
    scrollbar-color: #2a1f00;
    scrollbar-color-hover: #ffd700;
    padding: 0 1;
}

#status-bar {
    height: 1;
    background: #0a0a0a;
    color: #7a6b4a;
    padding: 0 1;
    border-bottom: solid #2a1f00;
}

#plan-panel {
    height: auto;
    background: #0a0a0a;
    border-bottom: solid #2a1f00;
    padding: 0 2;
    color: #f5ecd0;
}

#stream-preview {
    height: auto;
    background: #000000;
    border-left: solid #ffd700;
    padding: 0 2;
    color: #f5ecd0;
}

#input-bar {
    height: 3;
    background: #0a0a0a;
    border-top: solid #2a1f00;
    layout: horizontal;
}

#prompt-label {
    width: auto;
    height: 3;
    padding: 1 0 1 1;
    color: #c8a800;
    text-style: bold;
}

#cmd-input {
    width: 1fr;
    height: 3;
    background: #0a0a0a;
    color: #f5ecd0;
    border: solid #0a0a0a;
    padding: 0 1;
}

#cmd-input:focus {
    border: solid #0a0a0a;
}

Footer {
    background: #0a0a0a;
    color: #7a6b4a;
}
"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class CommandorApp(App):
    """Commandor — AI-powered single-pane terminal."""

    CSS = COMMANDOR_CSS
    TITLE = "◆  Commandor"
    SUB_TITLE = "AI Terminal"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+l", "clear_terminal", "Clear", show=True),
    ]

    def __init__(
        self,
        initial_mode: str = "agent",
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__()
        self._initial_mode = initial_mode
        self._provider = provider
        self._model = model

    def compose(self) -> ComposeResult:
        yield TerminalWidget(
            initial_mode=self._initial_mode,
            provider=self._provider,
            model=self._model,
            id="terminal",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#terminal", TerminalWidget).focus_input()

    def action_clear_terminal(self) -> None:
        self.query_one("#terminal", TerminalWidget).clear()
