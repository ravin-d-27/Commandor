"""Git operations used by /diff and the git_*_tool functions.

Public API:
    get_git_diff(path=None, staged=False) -> str
        Return the working-tree (or staged) diff as a Rich-markup string.
    get_git_status() -> str
        Return a short, Rich-formatted status report.
    git_commit(message, add_all=False, amend=False) -> str
        Stage (optional) and commit with the given message.
    git_log(n=10, oneline=True) -> str
        Return the last *n* commits.
    is_git_repo() -> bool
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

# Patterns used to colourise diff output for the Rich markup TUI.
# (Used by get_git_diff; agents get plain text via run_command_tool.)
_ADD_STYLE = "[bold #5faf5f]+{line}[/{style}]".format  # placeholder
_ADD_STYLE = ""
_DEL_STYLE = ""
_HUNK_STYLE = "[cyan]{line}[/cyan]"
_HDR_STYLE = "[dim]{line}[/dim]"


def _run_git(args: list[str], cwd: Optional[str] = None) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=cwd or str(Path.cwd()),
            timeout=30,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return 127, "", "git is not installed or not on PATH"
    except subprocess.TimeoutExpired:
        return 124, "", "git command timed out (30s)"
    except Exception as exc:  # noqa: BLE001
        return 1, "", str(exc)


def is_git_repo(cwd: Optional[str] = None) -> bool:
    """True if cwd (or Path.cwd()) is inside a git working tree."""
    code, _, _ = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=cwd)
    return code == 0


def get_git_diff(path: Optional[str] = None, staged: bool = False,
                 cwd: Optional[str] = None) -> str:
    """Return the working-tree (or staged) diff as a Rich-markup string.

    Args:
        path:   Optional path filter (e.g. 'src/foo.py' to limit to that file).
        staged: If True, show staged-but-not-committed changes (git diff --cached).
        cwd:    Working directory (defaults to Path.cwd()).

    Returns:
        A multi-line string with Rich markup suitable for log.write(Text.from_markup(...)).
    """
    args = ["diff", "--no-color"]
    if staged:
        args.append("--cached")
    if path:
        args.extend(["--", path])

    code, out, err = _run_git(args, cwd=cwd)
    if code != 0:
        return f"[red]git diff failed:[/red] {err.strip() or 'unknown error'}"

    if not out.strip():
        scope = "staged" if staged else "working tree"
        target = f" ({path})" if path else ""
        return f"[dim]  No {scope} changes{target}.[/dim]"

    lines = ["[bold #ffd700]◆ git diff[/bold #ffd700]  [dim]({0}{1})[/dim]".format(
        "staged" if staged else "working tree",
        f" — {path}" if path else "",
    ), ""]

    for raw in out.splitlines():
        if raw.startswith("+++") or raw.startswith("---"):
            lines.append(f"[dim]{raw}[/dim]")
        elif raw.startswith("+"):
            lines.append(f"[bold #5faf5f]{raw}[/bold #5faf5f]")
        elif raw.startswith("-"):
            lines.append(f"[bold #cc2200]{raw}[/bold #cc2200]")
        elif raw.startswith("@@"):
            lines.append(f"[cyan]{raw}[/cyan]")
        else:
            lines.append(f"[#7a6b4a]{raw}[/#7a6b4a]")

    # Truncate to keep the terminal responsive
    if len(lines) > 400:
        lines = lines[:400] + [
            f"[dim]… ({len(lines) - 400} more lines truncated)[/dim]"
        ]
    return "\n".join(lines)


def get_git_status(cwd: Optional[str] = None) -> str:
    """Return a short, Rich-formatted status report."""
    code, out, err = _run_git(["status", "--porcelain"], cwd=cwd)
    if code != 0:
        return f"[red]Not a git repository:[/red] {err.strip()}"

    if not out.strip():
        return "[dim]  Working tree clean.[/dim]"

    code2, branch_out, _ = _run_git(["branch", "--show-current"], cwd=cwd)
    branch = branch_out.strip() or "(detached HEAD)"

    lines = [
        f"[bold #ffd700]◆ git status[/bold #ffd700]  [dim]on {branch}[/dim]",
        "",
    ]
    for raw in out.splitlines():
        # XY format: X = index status, Y = worktree status
        if len(raw) < 3:
            continue
        x, y, path = raw[0], raw[1], raw[3:]
        if x != " " and y != " ":
            sym = "[yellow]→[/yellow]"
        elif x != " ":
            sym = "[bold #5faf5f]A[/bold #5faf5f]"  # staged
        elif y != " ":
            sym = "[bold #c8a800]M[/bold #c8a800]"  # modified
        else:
            sym = " "
        if y == "?":
            sym = "[dim]?[/dim]"
        lines.append(f"  {sym}  {path}")
    return "\n".join(lines)


def git_commit(
    message: str,
    add_all: bool = False,
    amend: bool = False,
    cwd: Optional[str] = None,
) -> str:
    """Stage (optional) and commit with the given message.

    Returns a Rich-formatted status line.  Refuses to commit with an
    empty message.
    """
    if not message or not message.strip():
        return "[red]Refused to commit with an empty message.[/red]"

    if not is_git_repo(cwd=cwd):
        return "[red]Not a git repository — nothing to commit.[/red]"

    if add_all:
        code, _, err = _run_git(["add", "-A"], cwd=cwd)
        if code != 0:
            return f"[red]git add failed:[/red] {err.strip()}"

    args = ["commit", "-m", message.strip()]
    if amend:
        args.append("--amend")

    code, out, err = _run_git(args, cwd=cwd)
    if code != 0:
        return (
            f"[red]git commit failed:[/red] {err.strip() or out.strip() or 'unknown error'}"
        )

    # Try to extract the commit hash for the response
    code2, hash_out, _ = _run_git(["rev-parse", "--short", "HEAD"], cwd=cwd)
    short = hash_out.strip() if code2 == 0 else "?"

    return (
        f"[bold #5faf5f]✓[/bold #5faf5f]  "
        f"[#5faf5f]Committed [bold]{short}[/bold][/#5faf5f]  "
        f"[dim]{message.strip()[:60]}{'…' if len(message.strip()) > 60 else ''}[/dim]"
    )


def git_log(n: int = 10, oneline: bool = True,
            cwd: Optional[str] = None) -> str:
    """Return the last *n* commits as a Rich-formatted string."""
    if not is_git_repo(cwd=cwd):
        return "[red]Not a git repository.[/red]"

    fmt = "--oneline" if oneline else "--pretty=format:%h %ad %s%n%b  (%an)"
    args = ["log", fmt, f"-n{n}"]
    code, out, err = _run_git(args, cwd=cwd)
    if code != 0:
        return f"[red]git log failed:[/red] {err.strip()}"

    if not out.strip():
        return "[dim]  No commits yet.[/dim]"

    lines = [f"[bold #ffd700]◆ git log -n {n}[/bold #ffd700]", ""]
    for raw in out.splitlines():
        if oneline:
            if " " in raw:
                sha, rest = raw.split(" ", 1)
                lines.append(f"  [#c8a800]{sha}[/#c8a800]  {rest}")
            else:
                lines.append(f"  {raw}")
        else:
            lines.append(f"  {raw}")
    return "\n".join(lines)
