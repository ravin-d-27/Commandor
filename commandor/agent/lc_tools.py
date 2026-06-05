"""LangChain @tool-decorated wrappers around file_ops and shell utilities."""

import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import List, Optional

from langchain_core.tools import tool

from ..utils import file_ops, shell, web_ops
from ..utils.diff_display import display_diff
from ..utils.git_ops import git_commit, git_log, get_git_status, is_git_repo
from ..utils.ignore import IgnoreMatcher


# ---------------------------------------------------------------------------
# Thread-local queue for plan events.
# agent_bridge sets _plan_tls.queue = [] before each agent run and clears it
# after. The tools push (event_type, payload) tuples; _iter_graph drains them.
# ---------------------------------------------------------------------------

_plan_tls = threading.local()

# Module-level ignore matcher.  Initialized lazily on first use; the agent's
# system prompt is updated to reflect the active source.
_ignore_matcher: Optional[IgnoreMatcher] = None


def _get_ignore_matcher() -> IgnoreMatcher:
    """Return the process-wide IgnoreMatcher (created on first use)."""
    global _ignore_matcher
    if _ignore_matcher is None:
        _ignore_matcher = IgnoreMatcher()
    return _ignore_matcher


def _deny_if_ignored(path: str, op: str) -> Optional[str]:
    """If *path* is matched by .commandorignore, return an error message.

    Returns None when the path is allowed.
    """
    matcher = _get_ignore_matcher()
    if matcher.pattern_count == 0:
        return None
    if matcher.is_ignored(path):
        return (
            f"Refused to {op} '{path}': path is matched by .commandorignore "
            f"(rules: {matcher.summary()}).  Ask the user to remove the rule "
            f"or pass an unignored path before retrying."
        )
    return None


# ---------------------------------------------------------------------------
# Read-only tools
# ---------------------------------------------------------------------------

@tool
def read_file_tool(path: str, onset: int = 0, offset: Optional[int] = None) -> str:
    """Read the contents of a file, with optional line range selection.

    Lines are 0-indexed.  To read the **first 10 lines** pass onset=0, offset=9.
    To read lines 20–29 pass onset=20, offset=29.
    To read from line 50 to the end of file pass onset=50 (omit offset).

    Args:
        path:   Absolute or relative path to the file.
        onset:  First line to read, 0-indexed (default 0 = start of file).
        offset: Last line to read, 0-indexed **inclusive** (default = end of file).
    """
    try:
        denied = _deny_if_ignored(path, "read")
        if denied:
            return denied

        p = Path(path)
        if not p.exists():
            return f"Error: File not found: {path}"
        if not p.is_file():
            return f"Error: Not a file: {path}"

        try:
            with open(p, "r", encoding="utf-8") as fh:
                all_lines = fh.readlines()
        except UnicodeDecodeError:
            return f"<Binary file: {path}>"

        total = len(all_lines)
        start = max(0, onset)
        end   = (min(offset + 1, total) if offset is not None else total)
        selected = all_lines[start:end]

        header = ""
        if start > 0 or end < total:
            header = f"[Lines {start}–{end - 1} of {total} total]\n"

        return header + "".join(selected)
    except (FileNotFoundError, ValueError, OSError) as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# File-mutation tools (trigger diff display)
# ---------------------------------------------------------------------------

@tool
def write_file_tool(path: str, content: str) -> str:
    """Write content to a file, creating parent directories as needed.

    Overwrites the file if it already exists. Use edit_file_tool for surgical
    changes to existing files (preserves unchanged lines).

    Always use a path relative to the current working directory OR an absolute
    path. Do NOT accidentally write to the wrong directory — use cd_tool first
    to navigate to the project root if unsure.

    Args:
        path: Absolute or relative path to the file to write.
        content: Full content to write to the file. Must be the complete file
                 content (not a diff or partial update).
    """
    denied = _deny_if_ignored(path, "write")
    if denied:
        return denied

    # Capture old content before overwriting
    try:
        old_content = Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        old_content = ""

    try:
        result = file_ops.write_file(path, content, create_dirs=True)
    except OSError as e:
        return f"Error writing file: {e}"
    display_diff(path, old_content, content)
    return result


@tool
def edit_file_tool(path: str, old: str, new: str) -> str:
    """Edit a file by replacing an exact string with a new string.

    The first occurrence of `old` in the file will be replaced with `new`.
    Preferred over write_file_tool for targeted changes — it's safer and
    shows a precise diff.

    Tips for reliable use:
    - Include enough surrounding context lines in `old` to make it unique
    - Match whitespace and indentation exactly as it appears in the file
    - Read the file first with read_file_tool if unsure of exact content

    Args:
        path: Path to the file to edit.
        old: The exact text to find and replace (must exist verbatim in the file).
        new: The replacement text.
    """
    denied = _deny_if_ignored(path, "edit")
    if denied:
        return denied

    # Capture old content before editing
    try:
        old_content = Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        old_content = ""

    try:
        result = file_ops.edit_file(path, old, new)
    except (FileNotFoundError, ValueError, OSError) as e:
        return f"Error: {e}"

    # Reread to get the actual new content (edit_file may normalise line endings etc.)
    try:
        new_content = Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        new_content = old_content.replace(old, new, 1)

    display_diff(path, old_content, new_content)
    return result


@tool
def patch_file_tool(path: str, diff: str) -> str:
    """Apply a unified diff string to a file.

    The diff must be in standard unified-diff format (as produced by
    `diff -u` or `git diff`).  The system `patch` command is tried first;
    if it is not installed a pure-Python fallback is used automatically.

    Args:
        path: Path to the file to patch.
        diff: Unified diff string to apply.
    """
    # Capture old content before patching
    try:
        old_content = Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        old_content = ""

    # --- Try system `patch` first ---
    if shutil.which("patch"):
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".patch", delete=False, encoding="utf-8"
            ) as tf:
                tf.write(diff)
                patch_file = tf.name

            proc = subprocess.run(
                ["patch", "-p1", path, patch_file],
                capture_output=True,
                text=True,
                timeout=30,
            )
            os.unlink(patch_file)

            if proc.returncode != 0:
                return f"patch command failed:\n{proc.stderr.strip()}"

        except subprocess.TimeoutExpired:
            return "patch command timed out."
        except Exception as exc:  # noqa: BLE001
            return f"patch command error: {exc}"

    else:
        # --- Pure-Python fallback ---
        try:
            new_content = _apply_unified_diff(old_content, diff)
        except Exception as exc:  # noqa: BLE001
            return f"Failed to apply patch: {exc}"

        try:
            Path(path).write_text(new_content, encoding="utf-8")
        except OSError as exc:
            return f"Failed to write patched file: {exc}"

    # Reread the result for the diff display
    try:
        new_content = Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        new_content = old_content

    display_diff(path, old_content, new_content)
    return f"Patch applied successfully to {path}."


# ---------------------------------------------------------------------------
# Remaining read-only / shell tools
# ---------------------------------------------------------------------------

@tool
def glob_tool(pattern: str, path: str = ".") -> str:
    """Find files matching a glob pattern.

    Use this to discover the structure of a project before reading files.
    Common patterns:
    - '**/*.py'   — all Python files recursively
    - '*.ts'      — TypeScript files in the current directory only
    - 'src/**/*'  — everything under src/

    Files matched by .commandorignore are filtered out automatically.

    Args:
        pattern: Glob pattern such as '**/*.py' or '*.ts'.
        path: Directory to search in (defaults to current working directory).
    """
    try:
        result = file_ops.glob_files(pattern, path)
        return _filter_ignored_from_text_list(result, path, pattern)
    except (FileNotFoundError, ValueError, OSError) as e:
        return f"Error: {e}"


@tool
def grep_tool(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    """Search for a regex pattern inside file contents.

    Use this to find where a function, class, variable, or string is defined
    or referenced across a project.  Files matched by .commandorignore
    are skipped automatically.

    Args:
        pattern: Regular expression to search for (e.g. 'def my_func', 'TODO', 'import os').
        path: Directory to search in (defaults to current working directory).
        file_pattern: Glob pattern to filter files (e.g. '*.py', '*.ts', '*.json').
    """
    try:
        result = file_ops.search_in_files(pattern, path, file_pattern)
        return _filter_ignored_from_text_list(result, path, "*")
    except (FileNotFoundError, ValueError, OSError) as e:
        return f"Error: {e}"


def _filter_ignored_from_text_list(text: str, base: str, _pattern: str) -> str:
    """Drop lines from a glob/grep result that reference ignored files.

    The existing helpers return a list of paths or path:line entries.  We
    keep the heading line ("Found N file(s):") and filter the body.
    """
    matcher = _get_ignore_matcher()
    if matcher.pattern_count == 0:
        return text

    lines = text.splitlines()
    if not lines:
        return text

    # The first line is a header like "Found 12 file(s):" or "Found 5 match(es):"
    header = lines[0]
    body = lines[1:]

    base_path = Path(base).resolve() if base and base != "." else Path.cwd()

    kept: list[str] = []
    for line in body:
        # Extract the first whitespace-delimited token (the path)
        candidate = line.lstrip(" ").lstrip("\t").split(":", 1)[0].split()[0:1]
        if not candidate:
            kept.append(line)
            continue
        first = candidate[0]
        try:
            abs_p = (base_path / first).resolve() if not Path(first).is_absolute() else Path(first)
        except OSError:
            abs_p = Path(first)
        if not matcher.is_ignored(str(abs_p)):
            kept.append(line)

    # Update the header count to reflect filtering
    if "match(es):" in header or "file(s):" in header:
        new_count = len(kept)
        header = header.split(":")[0] + f":  ({new_count} shown, some ignored)"

    if not kept:
        return header + "\n  (all results matched by .commandorignore)"
    return "\n".join([header, *kept])


@tool
def list_directory_tool(path: str = ".") -> str:
    """List the contents of a directory (files and subdirectories).

    Use this to explore the project structure before reading files.
    Useful as a first step when starting work in an unfamiliar directory.

    Args:
        path: Directory path to list (defaults to current working directory).
    """
    try:
        return file_ops.list_directory(path)
    except (FileNotFoundError, ValueError, OSError) as e:
        return f"Error: {e}"


@tool
def run_command_tool(command: str, timeout: int = 60) -> str:
    """Run a shell command and return its combined stdout+stderr output.

    Use for: running tests, builds, git commands, package managers (pip/npm/cargo),
    creating directories (mkdir -p), checking installed tools, etc.

    Tips:
    - Create a new directory before writing files into it: run_command_tool('mkdir -p /path/to/dir')
    - Use absolute paths or ensure you've cd_tool'd to the right directory first
    - Avoid commands needing interactive input (e.g. passwd, vim, less)
    - For long-running processes (servers, watchers), use a short timeout and note the PID

    Safety: A handful of obviously destructive command patterns (rm -rf /, sudo rm,
    curl | sh, mkfs, dd of=/dev/sd*, etc.) are intercepted before execution and
    require explicit confirmation.  The agent will be told to ask the user to run
    the command manually instead.

    Args:
        command: Shell command to execute (runs in the current working directory).
        timeout: Maximum seconds to wait before giving up (default 60).
    """
    if shell.is_dangerous(command):
        return (
            "⚠ BLOCKED: this command matches a destructive pattern "
            "(rm -rf, sudo rm, dd, mkfs, curl|sh, fork bomb, etc.).  "
            "Ask the user to confirm and run it manually instead of via this tool."
        )
    return shell.run_command(command, timeout=timeout)


@tool
def get_directory_tool() -> str:
    """Get the current working directory path."""
    return shell.get_working_directory()


@tool
def cd_tool(path: str) -> str:
    """Change the current working directory.

    Use this BEFORE starting any work in a project to navigate to the correct
    folder. All subsequent file reads, writes, and shell commands will operate
    relative to the new directory.

    After changing directory, confirm the new CWD by calling get_directory_tool().

    IMPORTANT: Do NOT create project files in the Commandor tool's own directory.
    Always cd into a dedicated project folder first (create it with run_command_tool
    if it doesn't exist), then do your work there.

    Args:
        path: Directory to navigate to. Supports absolute paths (/home/user/project),
              relative paths (my_project, ../sibling), and ~ for home directory.
              Examples: '/tmp/my_app', '~/projects/website', '..', 'src'
    """
    return shell.change_directory(path)


@tool
def get_project_files_tool(extensions: Optional[List[str]] = None) -> str:
    """List all source files in the project, filtered by extension.

    Files matched by .commandorignore are excluded automatically.

    Args:
        extensions: Optional list of file extensions to include,
                    e.g. ['.py', '.ts']. Defaults to common source file types.
    """
    return shell.get_project_files(extensions)


@tool
def get_git_info_tool() -> str:
    """Get git repository status, current branch, and recent commits."""
    return shell.get_git_info()


@tool
def get_environment_tool() -> str:
    """Get system environment information: OS, Python version, shell, user, cwd."""
    return shell.get_environment_info()


# ---------------------------------------------------------------------------
# Network tools
# ---------------------------------------------------------------------------

@tool
def fetch_url_tool(url: str, timeout: int = 30, max_chars: int = 50000) -> str:
    """Fetch a web page and return its text content (HTML tags stripped).

    Use this to read documentation, blog posts, Stack Overflow answers,
    GitHub READMEs, API references, or any other public web page.  Returns
    plain text only — no images, scripts, or styling.

    Only http:// and https:// URLs are allowed.  Local file://, gopher://,
    and similar schemes are rejected for safety.

    For POST / PUT / DELETE / generic HTTP, use http_request_tool.

    Args:
        url:       Full http(s) URL to fetch.
        timeout:   Seconds to wait before giving up (default 30).
        max_chars: Maximum number of characters to return (default 50000).
    """
    return web_ops.fetch_url(url, timeout=timeout, max_chars=max_chars)


@tool
def http_request_tool(
    method: str,
    url: str,
    headers: Optional[dict] = None,
    body: str = "",
    timeout: int = 30,
    max_chars: int = 50000,
) -> str:
    """Send a generic HTTP request (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS).

    Use this to interact with REST APIs, webhooks, or any HTTP service.
    JSON request bodies are detected and sent with Content-Type:
    application/json automatically.  Only http:// and https:// URLs
    are allowed.

    The response is returned as a formatted block: status line, content
    type, and the body (HTML stripped, JSON pretty-printed).

    Args:
        method:    HTTP verb — GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS.
        url:       Target URL.
        headers:   Optional dict of extra request headers (e.g. Authorization).
        body:      Optional request body as a string.  If it parses as JSON,
                   it is sent as application/json.
        timeout:   Seconds before giving up (default 30).
        max_chars: Maximum response characters (default 50000).
    """
    return web_ops.http_request(
        method=method,
        url=url,
        headers=headers,
        body=body,
        timeout=timeout,
        max_chars=max_chars,
    )


# ---------------------------------------------------------------------------
# Git tools
# ---------------------------------------------------------------------------

@tool
def git_status_tool() -> str:
    """Return a short git status report (current branch, staged/unstaged files).

    Returns 'Not a git repository' if the working directory is not inside one.
    """
    if not is_git_repo():
        return "Not a git repository."
    return get_git_status()


@tool
def git_diff_tool(path: str = "", staged: bool = False) -> str:
    """Show the git diff (working tree by default; pass staged=True for staged).

    Args:
        path:   Optional file path filter (e.g. 'src/foo.py').  Empty = whole tree.
        staged: If True, show staged-but-not-committed changes.
    """
    if not is_git_repo():
        return "Not a git repository."
    return get_git_diff(path=path or None, staged=staged)


@tool
def git_commit_tool(message: str, add_all: bool = False, amend: bool = False) -> str:
    """Create a git commit with the given message.

    Refuses to commit with an empty message.  Set add_all=True to first
    stage every modified/deleted/untracked file.  Set amend=True to
    amend the previous commit (rewrites history — use with care).

    Args:
        message: Commit message.  Should be a one-line summary; multi-line
                 messages are allowed but the first line is the subject.
        add_all: If True, run 'git add -A' before committing.
        amend:   If True, amend the previous commit instead of creating a new one.
    """
    if not message or not message.strip():
        return "Refused to commit with an empty message."
    return git_commit(message=message, add_all=add_all, amend=amend)


@tool
def git_log_tool(n: int = 10) -> str:
    """Show the last *n* commits (default 10).

    Args:
        n: Number of commits to show.
    """
    return git_log(n=n)


# ---------------------------------------------------------------------------
# Task-tracking tools (signal the TUI to render / update the plan panel)
# ---------------------------------------------------------------------------

@tool
def create_task_plan(tasks: list) -> str:
    """Show the user a live numbered task plan in the terminal UI.

    WHEN TO USE: Call this at the very start of any complex multi-step task
    — implementing a feature, debugging, refactoring, project setup, etc. —
    that requires 3 or more distinct steps.  This lets the user track your
    progress in real time.

    HOW TO USE:
    1. Call create_task_plan(tasks=[...]) FIRST, before using any other tools.
    2. List 3-12 concise, action-oriented task descriptions.
    3. Execute the tasks in order.
    4. Call complete_task(index=N) immediately after finishing each step.

    DO NOT call this for simple one-step lookups, single-file reads, or
    direct conversational questions.

    Args:
        tasks: List of short task descriptions in execution order.
               Example: ["Read src/auth.py to understand login flow",
                         "Edit validate_token() to handle expiry",
                         "Run pytest auth/ to verify",
                         "Summarise changes"]
    """
    q = getattr(_plan_tls, "queue", None)
    if q is not None:
        q.append(("plan_created", list(tasks)))
    return json.dumps({
        "status": "plan_registered",
        "count": len(tasks),
        "message": (
            f"Plan with {len(tasks)} tasks displayed to user. "
            "Execute each task and call complete_task(index) after finishing each one."
        ),
    })


@tool
def complete_task(index: int) -> str:
    """Mark a plan task as done — checks it off live for the user.

    Call this immediately after completing each task listed in the most
    recent create_task_plan() call.  Use the 0-based position of the task.

    IMPORTANT: Call this DURING execution right after each step — not all
    at the end.  The user watches each item tick off in real time.

    Args:
        index: 0-based task index (first task = 0, second = 1, etc.).
    """
    q = getattr(_plan_tls, "queue", None)
    if q is not None:
        q.append(("task_done", index))
    return json.dumps({"status": "task_completed", "index": index})


# ---------------------------------------------------------------------------
# Tool registries
# ---------------------------------------------------------------------------

# All tools available to agent mode
ALL_TOOLS = [
    read_file_tool,
    write_file_tool,
    edit_file_tool,
    patch_file_tool,
    glob_tool,
    grep_tool,
    list_directory_tool,
    run_command_tool,
    get_directory_tool,
    cd_tool,
    get_project_files_tool,
    get_git_info_tool,
    get_environment_tool,
    fetch_url_tool,
    http_request_tool,
    git_status_tool,
    git_diff_tool,
    git_commit_tool,
    git_log_tool,
    create_task_plan,
    complete_task,
]

# Tool names that modify the filesystem or execute commands — used by assist mode
# to flag which actions need user confirmation.
DANGEROUS_TOOL_NAMES = {
    "run_command_tool",
    "write_file_tool",
    "edit_file_tool",
    "patch_file_tool",
}


# ---------------------------------------------------------------------------
# Pure-Python unified-diff applier (fallback when `patch` is not installed)
# ---------------------------------------------------------------------------

def _apply_unified_diff(original: str, diff_text: str) -> str:
    """Apply a unified diff to *original* text and return the patched text.

    Handles standard unified-diff format (--- / +++ / @@ headers, +/- lines).
    Raises ValueError on malformed or non-applicable hunks.
    """
    orig_lines = original.splitlines(keepends=True)
    result_lines: list[str] = list(orig_lines)
    offset = 0  # cumulative line-count shift from previously applied hunks

    lines = diff_text.splitlines(keepends=True)
    i = 0

    # Skip file header lines (--- / +++)
    while i < len(lines) and (lines[i].startswith("---") or lines[i].startswith("+++")):
        i += 1

    while i < len(lines):
        line = lines[i]
        if not line.startswith("@@"):
            i += 1
            continue

        # Parse @@ -start,count +start,count @@
        try:
            parts = line.split("@@")[1].strip().split()
            old_info = parts[0]  # e.g. "-10,6"
            old_start = int(old_info.split(",")[0].lstrip("-")) - 1  # 0-indexed
        except (IndexError, ValueError) as exc:
            raise ValueError(f"Malformed hunk header: {line!r}") from exc

        i += 1
        hunk_removes: list[str] = []
        hunk_adds: list[str] = []
        hunk_lines: list[tuple[str, str]] = []  # (type, text): ' ', '+', '-'

        while i < len(lines) and not lines[i].startswith("@@"):
            hl = lines[i]
            if hl.startswith("+") and not hl.startswith("+++"):
                hunk_lines.append(("+", hl[1:]))
                hunk_adds.append(hl[1:])
            elif hl.startswith("-") and not hl.startswith("---"):
                hunk_lines.append(("-", hl[1:]))
                hunk_removes.append(hl[1:])
            elif hl.startswith(" "):
                hunk_lines.append((" ", hl[1:]))
            elif hl.strip() == r"\ No newline at end of file":
                pass  # ignore
            i += 1

        # Apply the hunk: find the removal block in result_lines at adjusted position
        apply_pos = old_start + offset

        # Verify context / removals match
        check_pos = apply_pos
        for typ, text in hunk_lines:
            if typ in (" ", "-"):
                if check_pos >= len(result_lines):
                    raise ValueError(
                        f"Hunk extends beyond end of file at line {check_pos + 1}"
                    )
                if result_lines[check_pos].rstrip("\n\r") != text.rstrip("\n\r"):
                    raise ValueError(
                        f"Hunk mismatch at line {check_pos + 1}: "
                        f"expected {text!r}, got {result_lines[check_pos]!r}"
                    )
                check_pos += 1

        # Replace: collect new block
        new_block: list[str] = []
        src_pos = apply_pos
        for typ, text in hunk_lines:
            if typ == " ":
                new_block.append(result_lines[src_pos])
                src_pos += 1
            elif typ == "-":
                src_pos += 1  # skip removed line
            elif typ == "+":
                new_block.append(text)

        result_lines[apply_pos:src_pos] = new_block
        offset += len(new_block) - (src_pos - apply_pos)

    return "".join(result_lines)
