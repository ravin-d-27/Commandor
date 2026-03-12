"""terminal_widget.py — Unified single-pane terminal widget for Commandor.

Handles:
  - Direct shell command execution (subprocess in worker thread)
  - AI commands via /slash syntax: /agent, /chat, /ask, /plan, /assist
  - /setup interactive wizard (multi-step state machine)
  - /provider, /model, /providers, /sessions sub-commands
  - Command history (Up/Down)
  - CWD tracking (cd handled specially)
"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.events import Key
from textual.widget import Widget
from textual.widgets import Input, RichLog, Static

from ..agent_bridge import (
    DoneEvent,
    ErrorEvent,
    PlanCreatedEvent,
    PlanItemDoneEvent,
    StatusEvent,
    ThinkingEvent,
    TokenEvent,
    ToolCallEvent,
    ToolOutputEvent,
    stream_agent_events,
)
from ..config import get_config
from ..session_manager import SessionManager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROVIDERS = ("gemini", "anthropic", "openai", "openrouter")

_AI_CMDS = {"/agent", "/chat"}

_MODE_MAP = {
    "/agent": "agent",
    "/chat": "chat",
}

# Context window limits per model (tokens)
_MODEL_CTX_LIMITS: dict[str, int] = {
    "gemini-2.5-flash": 1_048_576,
    "gemini-2.5-pro": 2_097_152,
    "gemini-2.0-flash": 1_048_576,
    "gemini-1.5-pro": 2_097_152,
    "gemini-1.5-flash": 1_048_576,
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
    "claude-3-opus-20240229": 200_000,
    "claude-3-7-sonnet-20250219": 200_000,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "o1": 200_000,
    "o3-mini": 200_000,
    "anthropic/claude-3.5-sonnet": 200_000,
    "openai/gpt-4o": 128_000,
    "google/gemini-2.5-pro": 2_097_152,
}

_ALL_SLASH_CMDS = sorted([
    "/agent", "/chat", "/clear",
    "/export", "/help", "/model", "/pipe", "/provider",
    "/providers", "/reset", "/retry", "/sessions", "/setup",
])

_HISTORY_FILE = Path.home() / ".commandor" / "history"
_HISTORY_MAX = 1000

HELP_TEXT = """\
# Commandor — AI Terminal Help

## AI Commands
| Command | Description |
|---------|-------------|
| `/agent <task>` | Run the AI agent (plans, uses tools, executes autonomously) |
| `/chat <message>` | Conversational Q&A — no tools, just reasoning |

## Provider / Model
| Command | Description |
|---------|-------------|
| `/providers` | List all providers and status |
| `/provider <name>` | Switch active provider |
| `/model <id>` | Switch model for current provider |

## Sessions
| Command | Description |
|---------|-------------|
| `/sessions` | List all saved sessions |
| `/sessions save <name>` | Save current session |
| `/sessions new <name>` | Start a fresh named session |
| `/sessions resume <name>` | Resume a saved session |
| `/sessions rename <old> <new>` | Rename a session |
| `/sessions delete <name>` | Delete a session |

## Setup
| Command | Description |
|---------|-------------|
| `/setup` | Interactive API key configuration wizard |
| `/setup <provider>` | Start setup for a specific provider |

## Other
| Command | Description |
|---------|-------------|
| `/help` | Show this help |
| `/clear` | Clear the terminal |
| `/pipe <cmd> [pipe] <prompt>` | Pipe shell output to AI |
| `Ctrl+L` | Clear the terminal |
| `Ctrl+Q` | Quit |
| `Up / Down` | Navigate command history |
| `Tab` | Auto-complete slash commands |

## Context & Session
| Command | Description |
|---------|-------------|
| `/retry` | Re-run the last AI command |
| `/reset` | Clear conversation memory (new thread) |
| `/export [file]` | Save session as markdown file |

## Shell
Any command that doesn't start with `/` is run as a shell command.
`cd` is handled natively and updates the prompt path.

## Notes
The agent decides internally whether to plan, ask clarifying questions,
or execute directly based on the complexity of the task.

## Copy / Paste
Use **Shift+drag** to select text (bypasses mouse reporting).
Standard terminal copy (Ctrl+Shift+C / right-click) then works normally.
"""


# ---------------------------------------------------------------------------
# TerminalWidget
# ---------------------------------------------------------------------------

class TerminalWidget(Widget):
    """Unified terminal: shell + AI commands in a single pane."""

    BINDINGS = [
        Binding("up", "history_prev", "Previous command", priority=True, show=False),
        Binding("down", "history_next", "Next command", priority=True, show=False),
    ]

    def __init__(
        self,
        initial_mode: str = "agent",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._mode = initial_mode
        self._provider = provider
        self._model = model

        # CWD — start exactly where the user launched commandor
        self._cwd: str = os.getcwd()

        # Session state
        self._session_id: str = str(uuid.uuid4())
        self._session_name: Optional[str] = None
        self._session_mgr = SessionManager()

        # Command history
        self._history: list[str] = []
        self._history_pos: int = -1
        self._history_draft: str = ""

        # Setup wizard state machine
        self._setup_state: Optional[dict] = None

        # Streaming state
        self._stream_tokens: list[str] = []
        self._think_tokens: list[str] = []
        self._ai_worker = None

        # Context / retry / export state
        self._last_ai_task: Optional[str] = None
        self._last_ai_mode: str = "agent"
        self._ctx_tokens: int = 0
        self._ctx_model: str = ""
        self._conversation_log: list[dict] = []

        # Plan tracking state
        self._plan_items: list = []
        self._plan_done: set = set()

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static("", id="status-bar")
        yield RichLog(id="log", highlight=False, markup=False, wrap=True)
        yield Static("", id="plan-panel")
        yield Static("", id="stream-preview")
        with Horizontal(id="input-bar"):
            yield Static(self._prompt_text(), id="prompt-label")
            yield Input(placeholder="", id="cmd-input")

    def on_mount(self) -> None:
        self.query_one("#stream-preview").display = False
        self.query_one("#plan-panel").display = False
        self._load_history()
        self._update_status_bar()
        self._show_welcome()
        self.query_one("#cmd-input").focus()

    # ------------------------------------------------------------------
    # Prompt helpers
    # ------------------------------------------------------------------

    def _prompt_text(self) -> str:
        """Short path prompt like  ~/projects/foo ❯"""
        home = str(Path.home())
        path = self._cwd
        if path.startswith(home):
            path = "~" + path[len(home):]
        # Shorten very long paths to last 2 components
        parts = path.split(os.sep)
        if len(parts) > 4:
            path = os.sep.join(["…"] + parts[-2:])
        return f" {path} ❯ "

    def _refresh_prompt(self) -> None:
        self.query_one("#prompt-label", Static).update(self._prompt_text())

    def focus_input(self) -> None:
        self.query_one("#cmd-input", Input).focus()

    def clear(self) -> None:
        self.query_one("#log", RichLog).clear()
        preview = self.query_one("#stream-preview", Static)
        preview.update("")
        preview.display = False

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _ctx_bar_text(self, tokens: int, model: str) -> str:
        """Return a compact context-window usage string with optional bar."""
        limit = _MODEL_CTX_LIMITS.get(model, 0)
        if not limit:
            # Fuzzy fallback: find the first key that is a substring of model, or vice-versa
            model_lower = model.lower()
            for key, lim in _MODEL_CTX_LIMITS.items():
                if key in model_lower or model_lower in key:
                    limit = lim
                    break
        if tokens >= 1_000_000:
            tok_str = f"{tokens / 1_000_000:.1f}M"
        elif tokens >= 1_000:
            tok_str = f"{tokens / 1_000:.1f}k"
        else:
            tok_str = str(tokens)
        if limit:
            pct = min(tokens / limit, 1.0)
            bar = "▓" * round(pct * 8) + "░" * (8 - round(pct * 8))
            lim_str = f"{limit // 1_000_000}M" if limit >= 1_000_000 else f"{limit // 1_000}k"
            return f"{bar} {tok_str}/{lim_str} ({pct * 100:.0f}%)"
        return f"{tok_str} ctx tokens"

    def _update_status_bar(self) -> None:
        cfg = get_config()
        provider = self._provider or cfg.config.default_provider
        pcfg = cfg.get_provider_config(provider) if provider else None
        model = self._ctx_model or self._model or (pcfg.default_model if pcfg else "—")
        parts = [f"◆  {provider or '—'} · {model}"]
        bar_color = "#7a6b4a"  # default muted gold
        if self._ctx_tokens > 0:
            ctx_text = self._ctx_bar_text(self._ctx_tokens, model)
            parts.append(ctx_text)
            # Compute usage pct for color warning
            limit = _MODEL_CTX_LIMITS.get(model, 0)
            if not limit:
                m_lower = model.lower()
                for key, lim in _MODEL_CTX_LIMITS.items():
                    if key in m_lower or m_lower in key:
                        limit = lim
                        break
            if limit:
                pct = self._ctx_tokens / limit
                if pct > 0.8:
                    bar_color = "#cc2200"   # red — critical
                elif pct > 0.6:
                    bar_color = "#d4a017"   # amber — warning
        if self._session_name:
            parts.append(f"session: {self._session_name}")
        bar = self.query_one("#status-bar", Static)
        bar.update(Text("  " + "  │  ".join(parts), style=bar_color))

    # ------------------------------------------------------------------
    # Welcome banner
    # ------------------------------------------------------------------

    def _show_welcome(self) -> None:
        log = self.query_one("#log", RichLog)
        cfg = get_config()
        provider = self._provider or cfg.config.default_provider
        pcfg = cfg.get_provider_config(provider)
        model = self._model or (pcfg.default_model if pcfg else "—")

        log.write(Text("◆  Commandor", style="bold #ffd700"))
        log.write(Text(f"   Provider: {provider}  ·  Model: {model}", style="#7a6b4a"))
        log.write(Text(
            "   Type a shell command or /agent <task> to start. /help for more.",
            style="#7a6b4a",
        ))
        log.write(Text(""))

    # ------------------------------------------------------------------
    # Input handler
    # ------------------------------------------------------------------

    def on_key(self, event: Key) -> None:
        """Intercept Tab for slash-command completion (Input consumes Tab by default)."""
        if event.key == "tab":
            event.prevent_default()
            event.stop()
            self.action_tab_complete()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Show live slash-command hints in the stream-preview as the user types."""
        # Never overwrite an active AI stream
        if self._ai_worker is not None and self._ai_worker.is_running:
            return
        val = event.value
        preview = self.query_one("#stream-preview", Static)
        if val.startswith("/") and " " not in val:
            matches = [c for c in _ALL_SLASH_CMDS if c.startswith(val)]
            if matches:
                preview.display = True
                preview.update(Text("  " + "   ".join(matches), style="#7a6b4a"))
                return
        preview.display = False

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return

        # Clear the input immediately
        inp = self.query_one("#cmd-input", Input)
        inp.value = ""

        # Add to history (deduplicate consecutive identical)
        if not self._history or self._history[-1] != value:
            self._history.append(value)
        self._history_pos = -1
        self._history_draft = ""
        self._save_history_entry(value)

        if self._setup_state is not None:
            self._handle_setup_input(value)
        else:
            self._dispatch(value)

    # ------------------------------------------------------------------
    # Command dispatcher
    # ------------------------------------------------------------------

    def _dispatch(self, text: str) -> None:
        log = self.query_one("#log", RichLog)

        # Echo command
        log.write(Text(f"  {self._prompt_text()}{text}", style="#c8a800"))

        parts = text.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in _AI_CMDS:
            if not arg:
                log.write(Text(f"  Usage: {cmd} <task>", style="#cc2200"))
                return
            expanded, files = _expand_files(arg, cwd=self._cwd)
            if files:
                log.write(Text.from_markup(
                    f"  [#c8a800]◈[/#c8a800]  Loaded {len(files)} file(s): "
                    + ", ".join(f"[bold]{f}[/bold]" for f in files[:5])
                    + ("…" if len(files) > 5 else "")
                ))
            self._run_ai(expanded, mode=_MODE_MAP[cmd])

        elif cmd == "/help":
            log.write(Markdown(HELP_TEXT))

        elif cmd == "/clear":
            self.clear()

        elif cmd == "/setup":
            self._start_setup(arg)

        elif cmd == "/provider":
            self._cmd_provider(arg, log)

        elif cmd == "/model":
            self._cmd_model(arg, log)

        elif cmd == "/providers":
            self._cmd_providers(log)

        elif cmd == "/sessions":
            self._cmd_sessions(arg, log)

        elif cmd == "/retry":
            self._cmd_retry(log)

        elif cmd == "/reset":
            self._cmd_reset(log)

        elif cmd == "/export":
            self._cmd_export(arg, log)

        elif cmd == "/pipe":
            self._cmd_pipe(arg, log)

        elif cmd.startswith("/"):
            log.write(Text(f"  Unknown command: {cmd}  (try /help)", style="#cc2200"))

        else:
            self._run_shell(text)

    # ------------------------------------------------------------------
    # Shell execution
    # ------------------------------------------------------------------

    def _run_shell(self, cmd: str) -> None:
        log = self.query_one("#log", RichLog)

        # Handle `cd` natively
        parts = cmd.strip().split(None, 1)
        if parts[0] == "cd":
            target = parts[1].strip() if len(parts) > 1 else str(Path.home())
            # Expand ~ and env vars
            target = os.path.expandvars(os.path.expanduser(target))
            if not os.path.isabs(target):
                target = os.path.join(self._cwd, target)
            target = os.path.normpath(target)
            if os.path.isdir(target):
                self._cwd = target
                self._refresh_prompt()
            else:
                log.write(Text(f"  cd: {target}: No such directory", style="#cc2200"))
            return

        self.run_worker(
            lambda: self._exec_shell(cmd),
            thread=True,
            exclusive=False,
            name="shell",
        )

    def _exec_shell(self, cmd: str) -> None:
        """Run shell command in worker thread; write output via call_from_thread."""
        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"
        env["TERM"] = "xterm-256color"
        shell = os.environ.get("SHELL", "/bin/bash")

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                executable=shell,
                cwd=self._cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.stdout:
                self.app.call_from_thread(self._write_ansi, result.stdout, False)
            if result.stderr:
                self.app.call_from_thread(self._write_ansi, result.stderr, True)
        except subprocess.TimeoutExpired:
            self.app.call_from_thread(
                self._write_markup, "[#cc2200]  Command timed out (300s limit)[/#cc2200]"
            )
        except Exception as exc:
            self.app.call_from_thread(
                self._write_markup, f"[#cc2200]  Error: {exc}[/#cc2200]"
            )

    def _write_ansi(self, text: str, is_err: bool = False) -> None:
        log = self.query_one("#log", RichLog)
        rich_text = Text.from_ansi(text.rstrip())
        if is_err:
            rich_text.stylize("#cc2200")
        log.write(rich_text)

    def _write_markup(self, markup: str) -> None:
        log = self.query_one("#log", RichLog)
        log.write(Text.from_markup(markup))

    # ------------------------------------------------------------------
    # AI execution
    # ------------------------------------------------------------------

    def _render_plan(self) -> None:
        """Re-render the live plan panel from current state."""
        if not self._plan_items:
            return
        pending = [i for i in range(len(self._plan_items)) if i not in self._plan_done]
        current_idx = pending[0] if pending else -1
        lines = ["  [bold #ffd700]◆ Task Plan[/bold #ffd700]", ""]
        for i, item in enumerate(self._plan_items):
            if i in self._plan_done:
                lines.append(f"  [#d4a017]✓[/#d4a017]  [#7a6b4a]{item}[/#7a6b4a]")
            elif i == current_idx:
                lines.append(f"  [#ffd700]▶[/#ffd700]  [bold #f5ecd0]{item}[/bold #f5ecd0]")
            else:
                lines.append(f"  [#2a1f00]○[/#2a1f00]  [#7a6b4a]{item}[/#7a6b4a]")
        lines.append("")
        panel = self.query_one("#plan-panel", Static)
        panel.display = True
        panel.update(Text.from_markup("\n".join(lines)))

    def _run_ai(self, task: str, mode: str = "agent") -> None:
        log = self.query_one("#log", RichLog)

        # Warn if another AI worker is running
        if self._ai_worker is not None and self._ai_worker.is_running:
            log.write(Text("  ◈  AI is already running. Please wait.", style="#cc2200"))
            return

        # Track for /retry
        self._last_ai_task = task
        self._last_ai_mode = mode

        # Log to conversation history for /export
        self._conversation_log.append({"role": "user", "content": task, "mode": mode})

        # Auto-name session from first task (slug from first 5 words)
        if self._session_name is None:
            slug = "-".join(task.split()[:5]).lower()
            slug = "".join(c if c.isalnum() or c == "-" else "" for c in slug)[:40]
            self._session_name = slug or "session"

        self._stream_tokens = []
        self._think_tokens = []

        # Immediate visual feedback — user sees activity before first event arrives
        preview = self.query_one("#stream-preview", Static)
        preview.display = True
        preview.update(Text("  ◈  Thinking…", style="#7a6b4a"))

        self._ai_worker = self.run_worker(
            lambda: self._work_stream(task, mode),
            thread=True,
            exclusive=False,
            name="ai",
        )

    def _work_stream(self, task: str, mode: str) -> None:
        """Worker: iterate stream_agent_events and dispatch to UI thread."""
        for event in stream_agent_events(
            task,
            mode=mode,
            provider=self._provider,
            model=self._model,
            thread_id=self._session_id,
            session_name=self._session_name,
        ):
            self.app.call_from_thread(self._on_ai_event, event)

    def _on_ai_event(self, event) -> None:  # noqa: ANN001
        log = self.query_one("#log", RichLog)
        preview = self.query_one("#stream-preview", Static)

        if isinstance(event, StatusEvent):
            log.write(Rule(f"  {event.message}  ", style="#2a1f00"))
            # Also update preview so user sees current phase while log scrolls
            preview.display = True
            preview.update(Text(f"  ◈  {event.message}…", style="#7a6b4a"))

        elif isinstance(event, ThinkingEvent):
            self._think_tokens.append(event.text)
            # Show a simple indicator — thinking text is verbose and not useful live
            preview.display = True
            preview.update(Text("  ◈  Thinking…", style="#7a6b4a"))

        elif isinstance(event, TokenEvent):
            self._stream_tokens.append(event.text)
            full_text = "".join(self._stream_tokens)
            # Sliding window: show last 15 lines so the preview stays bounded
            lines = full_text.split("\n")
            visible = "\n".join(lines[-15:]) if len(lines) > 15 else full_text
            preview.display = True
            preview.update(Text(visible, style="#f5ecd0"))

        elif isinstance(event, ToolCallEvent):
            danger = " [#cc2200](!)[/#cc2200]" if event.is_dangerous else ""
            log.write(
                Text.from_markup(
                    f"  [#c8a800]⚙[/#c8a800]  [bold]{event.name}[/bold]{danger}"
                    f"  [#7a6b4a]{event.args_preview}[/#7a6b4a]"
                )
            )

        elif isinstance(event, ToolOutputEvent):
            snippet = event.content[:200].replace("\n", "  ")
            log.write(
                Text.from_markup(
                    f"     [#7a6b4a]↳  {snippet}[/#7a6b4a]"
                    + (f"  [dim]({event.line_count} lines)[/dim]"
                       if event.line_count > 3 else "")
                )
            )

        elif isinstance(event, PlanCreatedEvent):
            self._plan_items = list(event.items)
            self._plan_done = set()
            self._render_plan()

        elif isinstance(event, PlanItemDoneEvent):
            self._plan_done.add(event.index)
            self._render_plan()

        elif isinstance(event, ErrorEvent):
            preview.display = False
            log.write(Panel(
                Text(event.message, style="#cc2200"),
                border_style="#cc2200",
                title="Error",
            ))

        elif isinstance(event, DoneEvent):
            preview.display = False

            thinking = "".join(self._think_tokens).strip()
            if thinking:
                log.write(Panel(
                    Markdown(thinking),
                    border_style="#2a1f00",
                    title="◈ Thinking",
                    title_align="left",
                ))

            answer = event.final_answer.strip()
            if answer:
                log.write(Panel(
                    Markdown(answer),
                    border_style="#ffd700",
                    title="◆ Commandor",
                    title_align="left",
                ))
                # Log AI response for /export
                self._conversation_log.append({"role": "ai", "content": answer})

            # Extract context token count for status bar
            m = event.metrics
            if m.get("approx_tokens"):
                self._ctx_tokens = m["approx_tokens"]
            if m.get("model"):
                self._ctx_model = m["model"]
            self._update_status_bar()

            # Dump final plan to log if one was active, then hide panel
            if self._plan_items:
                plan_lines = ["  [bold #ffd700]◆ Task Plan — completed[/bold #ffd700]", ""]
                for i, item in enumerate(self._plan_items):
                    if i in self._plan_done:
                        plan_lines.append(f"  [#d4a017]✓[/#d4a017]  [#7a6b4a]{item}[/#7a6b4a]")
                    else:
                        plan_lines.append(f"  [#cc2200]✗[/#cc2200]  [#7a6b4a]{item} (incomplete)[/#7a6b4a]")
                log.write(Text.from_markup("\n".join(plan_lines)))
                self._plan_items = []
                self._plan_done = set()
                self.query_one("#plan-panel", Static).display = False

            # Metrics footer — compact format to fit Rule width
            m = event.metrics
            parts = []
            if m.get("model"):
                import re as _re
                model_display = m["model"]
                if "/" in model_display:                         # strip openrouter prefix
                    model_display = model_display.split("/")[-1]
                model_display = _re.sub(r"-\d{8}$", "", model_display)  # strip date suffix
                if len(model_display) > 22:
                    model_display = model_display[:19] + "…"
                parts.append(model_display)
            if m.get("input_tokens"):
                parts.append(f"in:{m['input_tokens']}")
            if m.get("output_tokens"):
                parts.append(f"out:{m['output_tokens']}")
            if m.get("approx_tokens"):
                # Compact ctx — full bar lives in status bar, keep metrics line short
                t = m["approx_tokens"]
                tok_str = f"{t / 1_000_000:.1f}M" if t >= 1_000_000 else f"{t / 1_000:.1f}k" if t >= 1_000 else str(t)
                parts.append(f"ctx:{tok_str}")
            if m.get("condensations"):
                parts.append(f"condensed:{m['condensations']}x")
            metrics_str = "  ·  ".join(parts)
            log.write(Rule(
                f"  [#d4a017]✓ done[/#d4a017]  [#7a6b4a]{metrics_str}[/#7a6b4a]  ",
                style="#2a1f00",
            ))

            # Update session last_used
            if self._session_name:
                try:
                    self._session_mgr.update_last_used(self._session_name)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # /provider, /model, /providers
    # ------------------------------------------------------------------

    def _cmd_providers(self, log: RichLog) -> None:
        cfg = get_config()
        log.write(Text("  Available providers:", style="bold #f5ecd0"))
        for name in _PROVIDERS:
            pcfg = cfg.get_provider_config(name)
            if pcfg is None:
                log.write(Text(f"    {name}  [not configured]", style="#7a6b4a"))
                continue
            has_key = bool(pcfg.api_key)
            is_default = (name == cfg.config.default_provider)
            status = "[#d4a017]✓[/#d4a017]" if has_key else "[#cc2200]✗[/#cc2200]"
            default_mark = "  [#ffd700]← default[/#ffd700]" if is_default else ""
            log.write(Text.from_markup(
                f"    {status}  [bold]{name}[/bold]"
                f"  [#7a6b4a]{pcfg.default_model}[/#7a6b4a]{default_mark}"
            ))

    def _cmd_provider(self, arg: str, log: RichLog) -> None:
        if not arg:
            log.write(Text(f"  Current provider: {self._provider or get_config().config.default_provider}", style="#f5ecd0"))
            log.write(Text("  Usage: /provider <name>", style="#7a6b4a"))
            return
        name = arg.strip().lower()
        if name not in _PROVIDERS:
            log.write(Text(f"  Unknown provider: {name}. Choose from: {', '.join(_PROVIDERS)}", style="#cc2200"))
            return
        self._provider = name
        log.write(Text(f"  ✓ Provider set to: {name}", style="#d4a017"))

    def _cmd_model(self, arg: str, log: RichLog) -> None:
        if not arg:
            cfg = get_config()
            provider = self._provider or cfg.config.default_provider
            pcfg = cfg.get_provider_config(provider)
            current = self._model or (pcfg.default_model if pcfg else "—")
            log.write(Text(f"  Current model: {current}", style="#f5ecd0"))
            log.write(Text("  Usage: /model <model-id>", style="#7a6b4a"))
            return
        self._model = arg.strip()
        log.write(Text(f"  ✓ Model set to: {self._model}", style="#d4a017"))

    # ------------------------------------------------------------------
    # /sessions
    # ------------------------------------------------------------------

    def _cmd_sessions(self, arg: str, log: RichLog) -> None:
        parts = arg.split() if arg else []
        sub = parts[0].lower() if parts else ""

        if not sub:
            # List sessions
            sessions = self._session_mgr._sessions
            if not sessions:
                log.write(Text("  No saved sessions. Use /sessions save <name>", style="#7a6b4a"))
                return
            log.write(Text("  Saved sessions:", style="bold #f5ecd0"))
            sorted_s = sorted(sessions.items(), key=lambda kv: kv[1].get("last_used", ""), reverse=True)
            for name, info in sorted_s:
                active = " ← active" if info.get("id") == self._session_id else ""
                last = info.get("last_used", "—")[:16].replace("T", " ")
                log.write(Text.from_markup(
                    f"    [bold]{name}[/bold]  [#7a6b4a]{last}{active}[/#7a6b4a]"
                ))
            log.write(Text("  /sessions save|new|resume|rename|delete <name>", style="#7a6b4a"))

        elif sub == "save" and len(parts) >= 2:
            name = parts[1]
            self._session_name = name
            self._session_mgr.save_session(name, self._session_id)
            log.write(Text(f"  ✓ Session saved as: {name}", style="#d4a017"))

        elif sub == "new" and len(parts) >= 2:
            name = parts[1]
            new_id = self._session_mgr.new_session(name)
            if new_id:
                self._session_id = new_id
                self._session_name = name
                log.write(Text(f"  ✓ New session started: {name}", style="#d4a017"))

        elif sub == "resume" and len(parts) >= 2:
            name = parts[1]
            sid = self._session_mgr.resume_session(name)
            if sid:
                self._session_id = sid
                self._session_name = name
                log.write(Text(f"  ✓ Resumed session: {name}", style="#d4a017"))

        elif sub == "rename" and len(parts) >= 3:
            old, new = parts[1], parts[2]
            self._session_mgr.rename_session(old, new)
            if self._session_name == old:
                self._session_name = new
            log.write(Text(f"  ✓ Renamed {old} → {new}", style="#d4a017"))

        elif sub == "delete" and len(parts) >= 2:
            name = parts[1]
            self._session_mgr.delete_session(name, current_id=self._session_id)
            log.write(Text(f"  ✓ Session deleted: {name}", style="#d4a017"))

        else:
            log.write(Text("  Usage: /sessions [save|new|resume|rename|delete] [<name>]", style="#7a6b4a"))

    # ------------------------------------------------------------------
    # /retry, /reset, /export
    # ------------------------------------------------------------------

    def _cmd_retry(self, log: RichLog) -> None:
        if not self._last_ai_task:
            log.write(Text("  No previous AI task to retry.", style="#7a6b4a"))
            return
        self._run_ai(self._last_ai_task, mode=self._last_ai_mode)

    def _cmd_reset(self, log: RichLog) -> None:
        self._session_id = str(uuid.uuid4())
        self._session_name = None
        self._ctx_tokens = 0
        self._ctx_model = ""
        self._last_ai_task = None
        self._conversation_log = []
        self._plan_items = []
        self._plan_done = set()
        try:
            self.query_one("#plan-panel", Static).display = False
        except Exception:
            pass
        self._update_status_bar()
        log.write(Text("  ✓ Conversation reset. New session started.", style="#d4a017"))

    def _cmd_export(self, arg: str, log: RichLog) -> None:
        from datetime import datetime
        if not self._conversation_log:
            log.write(Text("  No conversation to export.", style="#7a6b4a"))
            return
        filename = arg.strip() if arg else f"commandor-{datetime.now():%Y%m%d-%H%M%S}.md"
        if not filename.endswith(".md"):
            filename += ".md"
        path = Path(self._cwd) / filename
        lines = ["# Commandor Session Export\n\n"]
        if self._session_name:
            lines.append(f"**Session:** {self._session_name}\n\n")
        lines.append(f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
        for entry in self._conversation_log:
            if entry["role"] == "user":
                lines.append(f"## ▸ {entry.get('mode', 'agent').upper()}\n\n{entry['content']}\n\n")
            elif entry["role"] == "ai":
                lines.append(f"## ◆ Commandor\n\n{entry['content']}\n\n---\n\n")
        path.write_text("".join(lines))
        log.write(Text(f"  ✓ Exported to: {path}", style="#d4a017"))

    def _cmd_pipe(self, arg: str, log: RichLog) -> None:
        if not arg:
            log.write(Text("  Usage: /pipe <shell-cmd> | <ai-prompt>", style="#7a6b4a"))
            log.write(Text("  Example: /pipe git diff HEAD~1 | review this for bugs", style="#7a6b4a"))
            return
        if "|" in arg:
            shell_part, _, ai_part = arg.partition("|")
            shell_part = shell_part.strip()
            ai_part = ai_part.strip()
        else:
            shell_part = arg.strip()
            ai_part = "Analyze this output"
        if not shell_part:
            log.write(Text("  Usage: /pipe <shell-cmd> | <ai-prompt>", style="#7a6b4a"))
            return
        log.write(Text.from_markup(
            f"  [#c8a800]⚙[/#c8a800]  Piping: [bold]{shell_part}[/bold]"
        ))
        self.run_worker(
            lambda: self._work_pipe(shell_part, ai_part),
            thread=True,
            exclusive=False,
            name="pipe",
        )

    def _work_pipe(self, shell_cmd: str, ai_prompt: str) -> None:
        shell = os.environ.get("SHELL", "/bin/bash")
        try:
            result = subprocess.run(
                shell_cmd,
                shell=True,
                executable=shell,
                cwd=self._cwd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = (result.stdout + result.stderr).strip()
            if not output:
                self.app.call_from_thread(
                    lambda: self.query_one("#log", RichLog).write(
                        Text("  /pipe: command produced no output", style="#7a6b4a")
                    )
                )
                return
            lines = output.split("\n")
            if len(lines) > 200:
                output = "\n".join(lines[:200]) + f"\n… ({len(lines) - 200} more lines truncated)"
            task = f"{ai_prompt}\n\n```\n$ {shell_cmd}\n{output}\n```"
            self.app.call_from_thread(self._run_ai, task, "agent")
        except subprocess.TimeoutExpired:
            self.app.call_from_thread(
                lambda: self.query_one("#log", RichLog).write(
                    Text("  /pipe: command timed out (60s)", style="#cc2200")
                )
            )
        except Exception as exc:
            self.app.call_from_thread(
                lambda: self.query_one("#log", RichLog).write(
                    Text(f"  /pipe error: {exc}", style="#cc2200")
                )
            )

    # ------------------------------------------------------------------
    # /setup wizard (state machine)
    # ------------------------------------------------------------------

    def _start_setup(self, arg: str = "") -> None:
        log = self.query_one("#log", RichLog)
        inp = self.query_one("#cmd-input", Input)

        provider_arg = arg.strip().lower()
        if provider_arg and provider_arg in _PROVIDERS:
            # Skip straight to key entry for the given provider
            self._setup_state = {"step": "key_entry", "provider": provider_arg}
            cfg = get_config()
            pcfg = cfg.get_provider_config(provider_arg)
            model = pcfg.default_model if pcfg else ""
            log.write(Text(f"  ⚙  Setup: {provider_arg}  (model: {model})", style="#ffd700"))
            log.write(Text("  Enter your API key (or press Enter to skip):", style="#f5ecd0"))
            inp.placeholder = f"{provider_arg.upper()}_API_KEY"
        else:
            self._setup_state = {"step": "provider_choice"}
            log.write(Text("  ⚙  Commandor Setup Wizard", style="bold #ffd700"))
            log.write(Text("  Available providers:", style="#f5ecd0"))
            for p in _PROVIDERS:
                log.write(Text(f"    • {p}", style="#c8a800"))
            log.write(Text("  Which provider do you want to configure?", style="#f5ecd0"))
            inp.placeholder = "gemini / anthropic / openai / openrouter"

    def _handle_setup_input(self, value: str) -> None:
        log = self.query_one("#log", RichLog)
        inp = self.query_one("#cmd-input", Input)
        state = self._setup_state
        step = state["step"]

        # Echo what was typed (masked for key entry)
        if step == "key_entry":
            display = ("*" * min(len(value), 8) + "…") if value else "(skipped)"
            log.write(Text(f"  ▸  {display}", style="#7a6b4a"))
        else:
            log.write(Text(f"  ▸  {value}", style="#7a6b4a"))

        if step == "provider_choice":
            name = value.strip().lower()
            if name not in _PROVIDERS:
                log.write(Text(
                    f"  Invalid provider. Choose from: {', '.join(_PROVIDERS)}",
                    style="#cc2200",
                ))
                log.write(Text("  Which provider?", style="#f5ecd0"))
                return
            state["provider"] = name
            state["step"] = "key_entry"
            cfg = get_config()
            pcfg = cfg.get_provider_config(name)
            existing = pcfg.api_key if pcfg else None
            if existing:
                log.write(Text(f"  Key already set for {name}. Enter new key to replace, or press Enter to keep.", style="#7a6b4a"))
            else:
                log.write(Text(f"  Enter API key for {name} (press Enter to skip):", style="#f5ecd0"))
            inp.placeholder = f"{name.upper()}_API_KEY"

        elif step == "key_entry":
            provider = state["provider"]
            if value:
                cfg = get_config()
                cfg.set_provider_key(provider, value)
                log.write(Text(f"  ✓ API key saved for {provider}", style="#d4a017"))
                state["step"] = "default_choice"
                log.write(Text(f"  Set {provider} as the default provider? (y/n)", style="#f5ecd0"))
                inp.placeholder = "y / n"
            else:
                log.write(Text(f"  Skipped API key for {state['provider']}", style="#7a6b4a"))
                state["step"] = "another_choice"
                log.write(Text("  Configure another provider? (y/n)", style="#f5ecd0"))
                inp.placeholder = "y / n"

        elif step == "default_choice":
            provider = state["provider"]
            if value.strip().lower() in ("y", "yes"):
                cfg = get_config()
                cfg.set_default_provider(provider)
                self._provider = provider
                log.write(Text(f"  ✓ Default provider set to: {provider}", style="#d4a017"))
            state["step"] = "another_choice"
            log.write(Text("  Configure another provider? (y/n)", style="#f5ecd0"))
            inp.placeholder = "y / n"

        elif step == "another_choice":
            if value.strip().lower() in ("y", "yes"):
                self._setup_state = {"step": "provider_choice"}
                log.write(Text("  Which provider do you want to configure?", style="#f5ecd0"))
                inp.placeholder = "gemini / anthropic / openai / openrouter"
            else:
                self._setup_state = None
                inp.placeholder = ""
                log.write(Text("  ✓ Setup complete. Type /providers to see status.", style="#d4a017"))

    # ------------------------------------------------------------------
    # Command history actions
    # ------------------------------------------------------------------

    def _load_history(self) -> None:
        try:
            if _HISTORY_FILE.exists():
                lines = _HISTORY_FILE.read_text(errors="replace").splitlines()
                self._history = [l for l in lines if l.strip()][-_HISTORY_MAX:]
        except OSError:
            pass

    def _save_history_entry(self, cmd: str) -> None:
        try:
            _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            last = ""
            if _HISTORY_FILE.exists():
                try:
                    raw = _HISTORY_FILE.read_text()
                    stripped = raw.rstrip("\n")
                    last = stripped.rsplit("\n", 1)[-1] if "\n" in stripped else stripped
                except Exception:
                    pass
            if cmd != last:
                with _HISTORY_FILE.open("a") as f:
                    f.write(cmd + "\n")
        except OSError:
            pass

    def action_history_prev(self) -> None:
        if not self._history:
            return
        inp = self.query_one("#cmd-input", Input)
        if self._history_pos == -1:
            self._history_draft = inp.value
            self._history_pos = len(self._history) - 1
        elif self._history_pos > 0:
            self._history_pos -= 1
        inp.value = self._history[self._history_pos]
        inp.cursor_position = len(inp.value)

    def action_history_next(self) -> None:
        if self._history_pos == -1:
            return
        inp = self.query_one("#cmd-input", Input)
        if self._history_pos < len(self._history) - 1:
            self._history_pos += 1
            inp.value = self._history[self._history_pos]
        else:
            self._history_pos = -1
            inp.value = self._history_draft
        inp.cursor_position = len(inp.value)

    def action_tab_complete(self) -> None:
        """Tab-complete slash commands."""
        inp = self.query_one("#cmd-input", Input)
        val = inp.value
        # Only complete if input starts with / and has no space (no args yet)
        if not val.startswith("/") or " " in val:
            return
        matches = [c for c in _ALL_SLASH_CMDS if c.startswith(val)]
        if len(matches) == 1:
            inp.value = matches[0] + " "
            inp.cursor_position = len(inp.value)
        elif len(matches) > 1:
            log = self.query_one("#log", RichLog)
            log.write(Text("  " + "   ".join(matches), style="#7a6b4a"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _expand_files(text: str, cwd: str = "") -> tuple[str, list[str]]:
    """Expand @filename and @glob references to file contents inline.

    Paths are resolved relative to *cwd* (defaults to os.getcwd()).

    Returns:
        (expanded_text, list_of_loaded_paths)
    """
    import re
    import glob as _glob
    import os as _os

    base = cwd or _os.getcwd()
    loaded: list[str] = []

    def _replace(m: re.Match) -> str:
        pattern = m.group(1)
        # Resolve relative to the terminal's current working directory
        abs_pattern = pattern if _os.path.isabs(pattern) else _os.path.join(base, pattern)
        # Try glob expansion first (handles wildcards like src/**/*.py)
        matches = sorted(_glob.glob(abs_pattern, recursive=True))
        if matches:
            parts = []
            for p in matches:
                try:
                    content = Path(p).read_text(errors="replace")
                    rel = _os.path.relpath(p, base)
                    parts.append(f"\n```\n# {rel}\n{content}\n```\n")
                    loaded.append(rel)
                except OSError:
                    pass
            return "".join(parts) if parts else m.group(0)
        # Fallback: treat as a single literal path
        try:
            abs_path = Path(abs_pattern)
            content = abs_path.read_text(errors="replace")
            rel = _os.path.relpath(str(abs_path), base)
            loaded.append(rel)
            return f"\n```\n# {rel}\n{content}\n```\n"
        except OSError:
            return m.group(0)  # leave unchanged if not found

    result = re.sub(r"@([\w./\-*?\[\]]+)", _replace, text)
    return result, loaded
