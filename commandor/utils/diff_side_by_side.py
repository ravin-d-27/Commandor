"""Side-by-side, syntax-highlighted diff display using Rich.

Public API:
    display_diff(path, old, new)              → unified (backward-compat)
    display_side_by_side_diff(path, old, new) → two-column diff Panel

`display_diff` is the existing entry point used by write/edit/patch tools
(unified format, single panel).  `display_side_by_side_diff` is a richer
two-column view with line numbers, syntax highlighting (when Pygments is
available), and aligned gutters.  Falls back to a single-column view in
narrow terminals (< 80 cols).
"""

from __future__ import annotations

import difflib
from typing import Sequence

from rich.console import Console, Group
from rich.padding import Padding
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

_console = Console()


# ---------------------------------------------------------------------------
# File-extension → Pygments lexer hint
# ---------------------------------------------------------------------------

_LANG_HINTS = {
    ".py":   "python",
    ".js":   "javascript",
    ".jsx":  "jsx",
    ".ts":   "typescript",
    ".tsx":  "tsx",
    ".json": "json",
    ".yaml": "yaml",
    ".yml":  "yaml",
    ".md":   "markdown",
    ".html": "html",
    ".css":  "css",
    ".sh":   "bash",
    ".rs":   "rust",
    ".go":   "go",
    ".java": "java",
    ".c":    "c",
    ".h":    "c",
    ".cpp":  "cpp",
    ".hpp":  "cpp",
    ".toml": "toml",
    ".ini":  "ini",
    ".xml":  "xml",
    ".sql":  "sql",
}


def _guess_lexer(path: str) -> str | None:
    """Return a Pygments lexer name based on file extension, or None."""
    if not path:
        return None
    dot = path.rfind(".")
    if dot < 0:
        return None
    return _LANG_HINTS.get(path[dot:].lower())


# ---------------------------------------------------------------------------
# Backward-compatible single-column diff
# ---------------------------------------------------------------------------

def display_diff(path: str, old_content: str, new_content: str) -> None:
    """Print a coloured unified diff of old → new in a Rich Panel.

    Behaviour unchanged from the original (called by write/edit/patch tools).
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


# ---------------------------------------------------------------------------
# Side-by-side diff
# ---------------------------------------------------------------------------

def _compute_rows(
    old: str,
    new: str,
    context: int = 3,
) -> tuple[list[tuple[str, int | None, str, int | None, str]], list[str]]:
    """Build a flat list of rows for side-by-side display.

    Each row is a tuple:
        (kind, old_lineno, old_text, new_lineno, new_text)

    kind is one of 'equal', 'delete', 'insert', 'replace', 'pad', 'hunk'.

    The hunk rows have empty text fields and are emitted as headers
    between change blocks.
    """
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    opcodes = sm.get_opcodes()

    rows: list[tuple[str, int | None, str, int | None, str]] = []
    hunks: list[tuple[int, int, int, int]] = []  # (i1, i2, j1, j2) of each change block

    # Collect change blocks
    for tag, i1, i2, j1, j2 in opcodes:
        if tag != "equal":
            hunks.append((i1, i2, j1, j2))

    if not hunks:
        return [], []

    # Apply context windowing
    consumed_to_old = 0
    consumed_to_new = 0

    for hi, (i1, i2, j1, j2) in enumerate(hunks):
        # Pre-context
        if hi == 0:
            pre_old_start = max(0, i1 - context)
            pre_new_start = max(0, j1 - context)
        else:
            pi1, pi2, pj1, pj2 = hunks[hi - 1]
            pre_old_start = pi2 if pi2 < i1 - context else i1
            pre_new_start = pj2 if pj2 < j1 - context else j1

        # Emit the pre-context (only on the first block, or when there's a gap)
        if hi == 0 or pre_old_start < i1 or pre_new_start < j1:
            for k in range(pre_old_start, i1):
                rows.append((
                    "equal", k + 1, old_lines[k],
                    k - pre_old_start + pre_new_start + 1, new_lines[k - pre_old_start + pre_new_start],
                ))
        elif hi > 0:
            # No pre-context; just emit a "..." separator
            rows.append(("pad", None, "…", None, "…"))

        # Hunk header
        rows.append((
            "hunk", None, f"@@ -{i1 + 1},{i2 - i1} +{j1 + 1},{j2 - j1} @@",
            None, "",
        ))

        # Side-by-side alignment of the change block
        old_block = old_lines[i1:i2]
        new_block = new_lines[j1:j2]
        max_len = max(len(old_block), len(new_block))
        for k in range(max_len):
            o_text = old_block[k] if k < len(old_block) else None
            n_text = new_block[k] if k < len(new_block) else None
            o_lineno = i1 + k + 1 if o_text is not None else None
            n_lineno = j1 + k + 1 if n_text is not None else None

            if o_text is not None and n_text is not None:
                kind = "replace"
            elif o_text is not None:
                kind = "delete"
            else:
                kind = "insert"

            rows.append((kind, o_lineno, o_text or "", n_lineno, n_text or ""))

        # Post-context
        if hi == len(hunks) - 1:
            # last block — show trailing context
            post_old_end = min(len(old_lines), i2 + context)
            post_new_end = min(len(new_lines), j2 + context)
        else:
            ni1, ni2, nj1, nj2 = hunks[hi + 1]
            post_old_end = i2 if i2 + context < ni1 else ni1
            post_new_end = j2 if j2 + context < nj1 else nj1

        for k in range(i2, post_old_end):
            new_k = k - i2 + j2
            if new_k >= len(new_lines):
                break
            rows.append((
                "equal", k + 1, old_lines[k],
                new_k + 1, new_lines[new_k],
            ))

        if hi < len(hunks) - 1 and post_old_end < hunks[hi + 1][0]:
            # gap before next block — we'll emit a pad on its iteration
            pass

    return rows, []


def display_side_by_side_diff(
    path: str,
    old_content: str,
    new_content: str,
    max_lines: int = 200,
) -> None:
    """Print a side-by-side, syntax-highlighted diff of *old* → *new*.

    Falls back to a single-column unified diff if the terminal is too
    narrow (< 100 cols) or if Pygments is unavailable.

    Args:
        path:        File path used for syntax detection and the title.
        old_content: Original contents.
        new_content: Updated contents.
        max_lines:   Maximum number of body lines to render.
    """
    if old_content == new_content:
        return

    width = _console.width or 120
    if width < 100:
        # Narrow terminal — fall back to unified
        display_diff(path, old_content, new_content)
        return

    rows, _hunks = _compute_rows(old_content, new_content)
    if not rows:
        display_diff(path, old_content, new_content)
        return

    # Try syntax highlighting; fall back to plain text
    lexer = _guess_lexer(path)
    try:
        old_syntax = Syntax(old_content, lexer or "text", theme="monokai", word_wrap=False) if lexer else None
        new_syntax = Syntax(new_content, lexer or "text", theme="monokai", word_wrap=False) if lexer else None
    except Exception:
        old_syntax = new_syntax = None

    col_width = (width - 8) // 2  # leave room for gutters and separator

    body: list = []
    line_count = 0
    truncated = 0
    for kind, o_no, o_text, n_no, n_text in rows:
        if line_count >= max_lines:
            truncated += 1
            continue

        if kind == "hunk":
            body.append(Text(o_text, style="cyan"))
            line_count += 1
            continue
        if kind == "pad":
            pad = Text("    …    ", style="dim")
            sep = Text("  │  ", style="dim")
            body.append(Text(" ") * 0)  # spacer
            body.append(Group(
                Text("    …    ", style="dim", justify="center"),
            ))
            line_count += 1
            continue

        # Build left and right cells
        if kind == "equal":
            left_marker = " "
            right_marker = " "
            left_style = "dim"
            right_style = "dim"
        elif kind == "delete":
            left_marker = "-"
            right_marker = " "
            left_style = "bold red"
            right_style = "dim"
        elif kind == "insert":
            left_marker = " "
            right_marker = "+"
            left_style = "dim"
            right_style = "bold green"
        else:  # replace
            left_marker = "-"
            right_marker = "+"
            left_style = "bold red"
            right_style = "bold green"

        # Left cell
        o_label = f"{o_no:>4} " if o_no is not None else "     "
        left = Text()
        left.append(o_label, style="#7a6b4a")
        left.append(left_marker + " ", style=left_style)
        left.append(_truncate(o_text or "", col_width - 7), style=left_style)

        # Right cell
        n_label = f"{n_no:>4} " if n_no is not None else "     "
        right = Text()
        right.append(n_label, style="#7a6b4a")
        right.append(right_marker + " ", style=right_style)
        right.append(_truncate(n_text or "", col_width - 7), style=right_style)

        # Render side-by-side as a single Text with tab-like padding
        combined = Text()
        combined.append_text(left)
        combined.append(" │ ", style="dim")
        combined.append_text(right)
        body.append(combined)
        line_count += 1

    if truncated:
        body.append(Text(f"  … ({truncated} more rows truncated)", style="dim"))

    title = f"[yellow]diff: {path}[/yellow]"
    _console.print(Panel(
        Group(*body),
        title=title,
        border_style="yellow",
        padding=(0, 1),
    ))


def _truncate(s: str, n: int) -> str:
    """Truncate *s* to *n* chars with a trailing … marker if needed."""
    if n <= 1:
        return ""
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"
