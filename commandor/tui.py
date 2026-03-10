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
from prompt_toolkit.completion import Completer, Completion, WordCompleter
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
# Completer: /commands + @file references
# ---------------------------------------------------------------------------
class CommandorCompleter(Completer):
    """Completes slash-commands and @filepath references.

    When the cursor is immediately after an ``@`` token with no space,
    file-system paths are suggested.  Otherwise, slash-command completion
    falls through to a ``WordCompleter``.
    """

    def __init__(self, slash_words: list) -> None:
        self._slash = WordCompleter(slash_words, match_middle=False, sentence=True)

    def get_completions(self, document, complete_event):
        text_before = document.text_before_cursor

        # Walk backwards to find an '@' that is not preceded by alnum
        # and has no whitespace between it and the cursor.
        at_idx = -1
        for i in range(len(text_before) - 1, -1, -1):
            ch = text_before[i]
            if ch == "@":
                at_idx = i
                break
            if ch == " ":
                break  # space before reaching @  → no @-completion

        if at_idx >= 0:
            partial = text_before[at_idx + 1:]
            # Only complete if partial has no spaces (still a single token)
            if " " not in partial:
                yield from self._complete_path(partial)
                return

        yield from self._slash.get_completions(document, complete_event)

    def _complete_path(self, partial: str):
        """Yield Completion objects for file-system paths matching *partial*."""
        # Split into directory part + filename prefix
        if "/" in partial:
            dir_str, file_prefix = partial.rsplit("/", 1)
            search_dir = (
                Path(dir_str) if Path(dir_str).is_absolute()
                else Path.cwd() / dir_str
            )
        else:
            dir_str = ""
            file_prefix = partial
            search_dir = Path.cwd()

        try:
            entries = sorted(
                (e for e in search_dir.iterdir() if e.name.startswith(file_prefix)),
                key=lambda e: (e.is_file(), e.name),
            )
        except (OSError, PermissionError):
            return

        for entry in entries[:30]:
            trail = "/" if entry.is_dir() else ""
            rel = (dir_str + "/" + entry.name if dir_str else entry.name) + trail
            yield Completion(
                rel,
                start_position=-len(partial),
                display=entry.name + trail,
            )


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
        # Input area: slash-commands highlighted in bright cyan
        "slash-command": "bold #06b6d4",
        # Bottom toolbar: very dark bg, muted gray text
        "bottom-toolbar":      "bg:#0d0d1a #6b7280",
        "bottom-toolbar.text": "bg:#0d0d1a #6b7280",
        # Completion menu
        "completion-menu.completion":         "bg:#1e1e2e #cdd6f4",
        "completion-menu.completion.current": "bg:#313244 #c6a0f6 bold",
        # Scrollbar
        "scrollbar.background": "bg:#313244",
        "scrollbar.button":     "bg:#c6a0f6",
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

        completer = CommandorCompleter(SLASH_COMMANDS)

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

        SEP = "  \xb7  "  # visual separator between toolbar segments (middle dot)

        # -- Session --
        if self._session_name and self._session_id:
            short_id = self._session_id[:6]
            session_part = (
                SEP
                + f'<style fg="#c6a0f6">{self._session_name}</style>'
                + f' <style fg="#6b7280">({short_id}…)</style>'
            )
        elif self._session_name:
            session_part = SEP + f'<style fg="#c6a0f6">{self._session_name}</style>'
        elif self._session_id:
            short_id = self._session_id[:6]
            session_part = SEP + f'<style fg="#6b7280">{short_id}… (unsaved)</style>'
        else:
            session_part = ""

        # -- CWD --
        try:
            home = str(Path.home())
            cwd = os.getcwd()
            if cwd.startswith(home):
                cwd = "~" + cwd[len(home):]
        except Exception:
            cwd = "?"

        brand   = '<style fg="#c6a0f6">◆</style>'
        prov    = f'<style fg="#06b6d4">{provider}</style>'
        cwd_seg = SEP + f'<style fg="#6b7280">{cwd}</style>'

        line1 = f" {brand} {prov}{session_part}{cwd_seg} "

        # -- Metrics line --
        if self._metrics:
            model = self._metrics.get("model") or model_from_config or "—"
            ctx   = self._metrics.get("approx_tokens")
            ctx_str   = f"~{ctx:,} tok" if ctx else "—"
            inp = self._metrics.get("input_tokens")
            out = self._metrics.get("output_tokens")
            usage_str = f"in {inp:,} · out {out:,}" if inp and out else "—"
            cond      = self._metrics.get("condensations", 0)
            cond_seg  = SEP + f'<style fg="#6b7280">condensed {cond}×</style>' if cond else ""
            model_seg = f'<style fg="#06b6d4">{model}</style>'
            ctx_seg   = f'<style fg="#06b6d4">{ctx_str}</style>'
            usage_seg = f'<style fg="#06b6d4">{usage_str}</style>'
            line2 = f"   {model_seg}{SEP}{ctx_seg}{SEP}{usage_seg}{cond_seg} "
        else:
            model_display = model_from_config or "—"
            model_seg = f'<style fg="#06b6d4">{model_display}</style>'
            line2 = f"   {model_seg}{SEP}<style fg=\"#6b7280\">ready</style> "

        return HTML(f"{line1}\n{line2}")
