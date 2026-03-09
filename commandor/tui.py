"""prompt_toolkit-based interactive prompt for Commandor.

Provides ``CommandorPrompt``, a thin wrapper around ``PromptSession`` that
adds:
  - Persistent file-backed history
  - Auto-suggestions from history
  - Tab-completion for all slash commands
  - Syntax highlighting: /commands in cyan, everything else default
  - Bottom toolbar (2 lines):
      Line 1: provider | session name + short ID | cwd
      Line 2: model | context tokens | last token usage | condensation count
  - Escape+Enter for multi-line input
  - ``update_session(name, session_id)`` to update the displayed session info
  - ``update_metrics(...)`` to refresh the metrics line after each agent run
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
        self._session_id: Optional[str] = None
        self._metrics: Optional[dict] = None

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

    def update_session(self, name: Optional[str], session_id: Optional[str] = None) -> None:
        """Update the session name and ID shown in the toolbar."""
        self._session_name = name
        if session_id is not None:
            self._session_id = session_id

    def update_metrics(
        self,
        model: Optional[str] = None,
        approx_tokens: Optional[int] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        condensations: int = 0,
        **_kwargs: object,
    ) -> None:
        """Refresh the metrics shown on the second toolbar line."""
        self._metrics = {
            "model": model,
            "approx_tokens": approx_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "condensations": condensations,
        }

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
        """Build the two-line bottom toolbar content — called live on every render."""
        # -- Provider --
        try:
            from .config import get_config  # noqa: PLC0415
            cfg = get_config()
            provider = cfg.config.default_provider if cfg.config else "gemini"
            model_from_config = ""
            if cfg.config:
                pconfig = cfg.get_provider_config(provider)
                model_from_config = pconfig.default_model if pconfig else ""
        except Exception:
            provider = "gemini"
            model_from_config = ""

        # -- Session --
        if self._session_name and self._session_id:
            short_id = self._session_id[:8]
            session_part = f" | session: <b>{self._session_name}</b> · {short_id}…"
        elif self._session_name:
            session_part = f" | session: <b>{self._session_name}</b>"
        elif self._session_id:
            short_id = self._session_id[:8]
            session_part = f" | session: {short_id}… (unsaved)"
        else:
            session_part = ""

        # -- CWD --
        try:
            cwd = os.getcwd()
            parts = Path(cwd).parts
            if len(parts) > 2:
                cwd_display = ".../" + "/".join(parts[-2:])
            else:
                cwd_display = cwd
        except Exception:
            cwd_display = "?"

        line1 = f" provider: <b>{provider}</b>{session_part} | cwd: {cwd_display} "

        # -- Metrics line --
        if self._metrics:
            model = self._metrics.get("model") or model_from_config or "—"
            ctx = self._metrics.get("approx_tokens")
            ctx_str = f"~{ctx:,} tok" if ctx else "—"
            inp = self._metrics.get("input_tokens")
            out = self._metrics.get("output_tokens")
            usage_str = f"in {inp:,} · out {out:,}" if inp and out else "—"
            cond = self._metrics.get("condensations", 0)
            cond_str = f" | condensed: {cond}×" if cond else ""
            line2 = f" model: <b>{model}</b> | context: {ctx_str} | last: {usage_str}{cond_str} "
        else:
            model_display = model_from_config or "—"
            line2 = f" model: <b>{model_display}</b> | context: — | ready "

        return HTML(f"{line1}\n{line2}")
