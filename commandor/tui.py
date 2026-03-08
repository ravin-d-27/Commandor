"""prompt_toolkit-based interactive prompt for Commandor.

Provides ``CommandorPrompt``, a thin wrapper around ``PromptSession`` that
adds:
  - Persistent file-backed history
  - Auto-suggestions from history
  - Tab-completion for all slash commands
  - Syntax highlighting: /commands in cyan, everything else default
  - Bottom toolbar showing: provider | session name | cwd  (read live each render)
  - Escape+Enter for multi-line input
  - ``update_session(name)`` to update the displayed session name
  - ``get_input(prompt_str) -> str`` main entrypoint
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import ANSI, HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style

# ---------------------------------------------------------------------------
# All slash commands (for completion)
# ---------------------------------------------------------------------------
SLASH_COMMANDS = [
    "/agent",
    "/assist",
    "/plan",
    "/chat",
    "/ask",
    "/ai",
    "/help",
    "/info",
    "/history",
    "/ask-history",
    "/ask-search",
    "/clear",
    "/config",
    "/reset-api",
    "/test-api",
    "/providers",
    "/provider",
    "/modes",
    "/setup",
    "/test-providers",
    "/api",
    "/api set",
    "/api model",
    "/api test",
    "/api remove",
    "/api default",
    "/sessions",
    "/sessions save",
    "/sessions new",
    "/sessions resume",
    "/sessions rename",
    "/sessions delete",
    "exit",
]


# ---------------------------------------------------------------------------
# Lexer: highlight /commands in cyan
# ---------------------------------------------------------------------------
class CommandorLexer(Lexer):
    """Minimal lexer: colours slash-commands cyan, everything else default."""

    def lex_document(self, document):  # type: ignore[override]
        lines = document.lines

        def get_tokens(line_number: int):
            line = lines[line_number]
            stripped = line.lstrip()
            if stripped.startswith("/") or stripped == "exit":
                return [("class:slash-command", line)]
            return [("", line)]

        return get_tokens


# ---------------------------------------------------------------------------
# Key bindings: Escape+Enter inserts a newline (Alt+Enter on most terminals)
# ---------------------------------------------------------------------------
def _build_key_bindings() -> KeyBindings:
    kb = KeyBindings()

    @kb.add("escape", "enter")
    def _insert_newline(event):
        event.current_buffer.insert_text("\n")

    return kb


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
COMMANDOR_STYLE = Style.from_dict(
    {
        "slash-command": "cyan bold",
        "bottom-toolbar": "bg:#1a1a2e #8be9fd",
        "bottom-toolbar.text": "bg:#1a1a2e #8be9fd",
        "prompt": "cyan bold",
        "completion-menu.completion": "bg:#1e1e2e #cdd6f4",
        "completion-menu.completion.current": "bg:#313244 #cba6f7 bold",
        "scrollbar.background": "bg:#313244",
        "scrollbar.button": "bg:#cba6f7",
    }
)


# ---------------------------------------------------------------------------
# CommandorPrompt
# ---------------------------------------------------------------------------
class CommandorPrompt:
    """Interactive prompt for Commandor powered by prompt_toolkit.

    Args:
        config_dir: Path to ``~/.commandor`` (used for history file location).
    """

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = config_dir
        self._session_name: Optional[str] = None

        history_path = config_dir / "pt_history"
        history_path.parent.mkdir(parents=True, exist_ok=True)

        completer = WordCompleter(
            SLASH_COMMANDS,
            match_middle=False,
            sentence=True,
        )

        self._session: PromptSession = PromptSession(
            history=FileHistory(str(history_path)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=completer,
            complete_while_typing=True,
            lexer=CommandorLexer(),
            style=COMMANDOR_STYLE,
            key_bindings=_build_key_bindings(),
            bottom_toolbar=self._get_toolbar,
            enable_open_in_editor=True,
            multiline=False,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_session(self, name: Optional[str]) -> None:
        """Update the session name shown in the toolbar."""
        self._session_name = name

    def get_input(self, prompt_str: str = "") -> str:
        """Prompt the user and return their stripped input.

        ``prompt_str`` may contain ANSI escape codes (from ``AITerminal.get_prompt()``);
        wrapping it in ``ANSI()`` tells prompt_toolkit to interpret them rather than
        render them as literal text.

        Raises ``KeyboardInterrupt`` on Ctrl-C / EOF so callers can handle
        graceful shutdown the same way as with ``input()``.
        """
        try:
            result = self._session.prompt(ANSI(prompt_str) if prompt_str else "")
            return result.strip() if result else ""
        except EOFError:
            raise KeyboardInterrupt

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_toolbar(self) -> HTML:
        """Build the bottom toolbar content — called live on every render."""
        try:
            from .config import get_config  # noqa: PLC0415
            cfg = get_config()
            provider = cfg.config.default_provider if cfg.config else "gemini"
        except Exception:
            provider = "gemini"

        session_part = (
            f" | session: <b>{self._session_name}</b>" if self._session_name else ""
        )

        try:
            cwd = os.getcwd()
            # Show last 2 path components to keep the toolbar short
            parts = Path(cwd).parts
            if len(parts) > 2:
                cwd_display = ".../" + "/".join(parts[-2:])
            else:
                cwd_display = cwd
        except Exception:
            cwd_display = "?"

        return HTML(
            f" provider: <b>{provider}</b>{session_part} | cwd: {cwd_display} "
        )
