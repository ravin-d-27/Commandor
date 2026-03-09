"""Session management for Commandor.

Provides a SessionManager class that maintains a persistent registry of
named sessions (stored at ~/.commandor/sessions.json).  Each session maps a
human-readable name to a UUID that corresponds to the LangGraph thread_id
scope used by the checkpointer.

Because the checkpointer is now a SqliteSaver (see agent/lc_graph.py),
conversation history is preserved across restarts and can be resumed by
name via /sessions resume <name>.

Commands exposed via terminal.py:
  /sessions                        – list saved sessions (Rich table)
  /sessions save <name>            – name the current session
  /sessions new  <name>            – start a fresh named session
  /sessions resume <name>          – switch to a saved session
  /sessions rename <old> <new>     – rename a session
  /sessions delete <name>          – delete a session + its checkpoints
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from .agent.lc_graph import get_checkpointer

# Modes whose threads we clean up on delete
_MODES = ("agent", "chat", "assist")

_SESSIONS_FILE = Path.home() / ".commandor" / "sessions.json"


class SessionManager:
    """Manage named Commandor sessions backed by a JSON registry."""

    def __init__(self) -> None:
        self._console = Console()
        self._sessions_file = _SESSIONS_FILE
        self._sessions: dict = self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        if self._sessions_file.exists():
            try:
                return json.loads(self._sessions_file.read_text())
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save(self) -> None:
        self._sessions_file.parent.mkdir(exist_ok=True)
        self._sessions_file.write_text(json.dumps(self._sessions, indent=2))

    def _touch(self, name: str) -> None:
        """Update the last_used timestamp for *name*."""
        if name in self._sessions:
            self._sessions[name]["last_used"] = datetime.now().isoformat(
                timespec="seconds"
            )
            self._save()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_sessions(self, current_id: Optional[str] = None) -> None:
        """Display all saved sessions in a Rich table."""
        if not self._sessions:
            self._console.print(
                "[dim]No saved sessions yet. "
                "Use [bold]/sessions save <name>[/bold] to name the current session.[/dim]"
            )
            return

        table = Table(
            title="Commandor Sessions",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Name", style="bold white")
        table.add_column("ID (prefix)", style="dim")
        table.add_column("Created", style="green")
        table.add_column("Last Used", style="yellow")
        table.add_column("", style="bold yellow")  # active marker

        sorted_sessions = sorted(
            self._sessions.items(),
            key=lambda kv: kv[1].get("last_used", ""),
            reverse=True,
        )
        for name, info in sorted_sessions:
            active = "★ active" if info.get("id") == current_id else ""
            created = info.get("created_at", "—")[:10]
            last_used = info.get("last_used", "—")[:16].replace("T", " ")
            table.add_row(
                name,
                info.get("id", "")[:8] + "…",
                created,
                last_used,
                active,
            )

        self._console.print(table)
        self._console.print(
            "[dim]Commands: "
            "/sessions save <name>  •  "
            "/sessions new <name>  •  "
            "/sessions resume <name>  •  "
            "/sessions rename <old> <new>  •  "
            "/sessions delete <name>[/dim]"
        )

    def save_session(self, name: str, session_id: str) -> None:
        """Associate *name* with the current *session_id*.

        If the session_id is already registered under a different name,
        that entry is renamed to *name* instead of creating a duplicate.
        """
        now = datetime.now().isoformat(timespec="seconds")

        # Check for an existing entry with the same UUID (rename scenario)
        existing_name = next(
            (n for n, info in self._sessions.items() if info.get("id") == session_id),
            None,
        )
        if existing_name and existing_name != name:
            self._sessions[name] = self._sessions.pop(existing_name)
            self._sessions[name]["last_used"] = now
            self._save()
            self._console.print(
                f"[green]✓ Session renamed from [bold]{existing_name}[/bold] "
                f"to [bold]{name}[/bold].[/green]"
            )
            return

        # Guard against clobbering a different session
        if name in self._sessions and self._sessions[name].get("id") != session_id:
            self._console.print(
                f"[yellow]⚠ Name '[bold]{name}[/bold]' is already used by a "
                "different session. Use a different name or delete it first.[/yellow]"
            )
            return

        self._sessions[name] = {
            "id": session_id,
            "created_at": self._sessions.get(name, {}).get("created_at", now),
            "last_used": now,
        }
        self._save()
        self._console.print(
            f"[green]✓ Session saved as [bold]{name}[/bold] "
            f"(id: {session_id[:8]}…)[/green]"
        )

    def new_session(self, name: str) -> Optional[str]:
        """Create a fresh named session and return its UUID.

        Returns None (and prints an error) if the name is already taken.
        """
        if name in self._sessions:
            self._console.print(
                f"[yellow]⚠ Session '[bold]{name}[/bold]' already exists. "
                f"Use [bold]/sessions resume {name}[/bold] to switch to it.[/yellow]"
            )
            return None

        new_id = str(uuid.uuid4())
        now = datetime.now().isoformat(timespec="seconds")
        self._sessions[name] = {
            "id": new_id,
            "created_at": now,
            "last_used": now,
        }
        self._save()
        self._console.print(
            f"[green]✓ New session created: [bold]{name}[/bold] "
            f"(id: {new_id[:8]}…)[/green]"
        )
        return new_id

    def resume_session(self, name: str) -> Optional[str]:
        """Return the UUID of *name* so the terminal can switch session_id.

        Returns None if the session is not found.
        """
        if name not in self._sessions:
            self._console.print(
                f"[red]✗ No session named '[bold]{name}[/bold]'. "
                "Use [bold]/sessions[/bold] to list available sessions.[/red]"
            )
            return None

        info = self._sessions[name]
        self._touch(name)
        self._console.print(
            f"[green]✓ Resumed session: [bold]{name}[/bold] "
            f"(id: {info['id'][:8]}…)[/green]"
        )
        return info["id"]

    def rename_session(self, old: str, new: str) -> None:
        """Rename session *old* to *new*."""
        if old not in self._sessions:
            self._console.print(
                f"[red]✗ No session named '[bold]{old}[/bold]'.[/red]"
            )
            return
        if new in self._sessions:
            self._console.print(
                f"[red]✗ Name '[bold]{new}[/bold]' is already taken.[/red]"
            )
            return

        self._sessions[new] = self._sessions.pop(old)
        self._save()
        self._console.print(
            f"[green]✓ Session '[bold]{old}[/bold]' renamed to '[bold]{new}[/bold]'.[/green]"
        )

    def delete_session(self, name: str, current_id: Optional[str] = None) -> None:
        """Remove *name* from the registry and wipe its checkpointer threads."""
        if name not in self._sessions:
            self._console.print(
                f"[red]✗ No session named '[bold]{name}[/bold]'.[/red]"
            )
            return

        if self._sessions[name].get("id") == current_id:
            self._console.print(
                f"[yellow]⚠ Cannot delete the active session. "
                "Switch to another session first.[/yellow]"
            )
            return

        session_id = self._sessions.pop(name)["id"]
        self._save()

        cp = get_checkpointer()
        deleted = 0
        for mode in _MODES:
            try:
                cp.delete_thread(f"{mode}_{session_id}")
                deleted += 1
            except Exception:
                pass

        self._console.print(
            f"[green]✓ Session '[bold]{name}[/bold]' deleted "
            f"(removed {deleted} checkpoint thread(s)).[/green]"
        )

    def update_last_used(self, name: str) -> None:
        """Refresh the last_used timestamp for *name* (call after any agent run)."""
        self._touch(name)
