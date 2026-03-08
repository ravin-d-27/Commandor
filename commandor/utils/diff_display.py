"""Rich-powered unified diff display.

Public API:
    display_diff(path, old_content, new_content) -> None
        Prints a colour-coded before/after diff panel to the terminal.
        No-op if contents are identical.
"""

from __future__ import annotations

import difflib

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

_console = Console()


def display_diff(path: str, old_content: str, new_content: str) -> None:
    """Print a coloured unified diff of old_content → new_content in a Rich Panel.

    Colours:
        bold green  — added lines (+)
        bold red    — removed lines (-)
        cyan        — hunk headers (@@)
        dim         — context lines / file headers (--- / +++)

    Args:
        path:        File path shown in the panel title.
        old_content: Original file contents (empty string for new files).
        new_content: Updated file contents.
    """
    if old_content == new_content:
        return

    lines = list(
        difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )

    if not lines:
        return

    text = Text()
    for line in lines:
        if line.startswith("+++") or line.startswith("---"):
            text.append(line + "\n", style="dim")
        elif line.startswith("+"):
            text.append(line + "\n", style="bold green")
        elif line.startswith("-"):
            text.append(line + "\n", style="bold red")
        elif line.startswith("@@"):
            text.append(line + "\n", style="cyan")
        else:
            text.append(line + "\n", style="dim")

    _console.print(
        Panel(
            text,
            title=f"[yellow]diff: {path}[/yellow]",
            border_style="yellow",
            padding=(0, 1),
        )
    )
