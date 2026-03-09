"""LangChain @tool-decorated wrappers around file_ops and shell utilities."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from langchain_core.tools import tool

from ..utils import file_ops, shell
from ..utils.diff_display import display_diff


# ---------------------------------------------------------------------------
# Read-only tools
# ---------------------------------------------------------------------------

@tool
def read_file_tool(path: str, limit: Optional[int] = None) -> str:
    """Read the contents of a file.

    Args:
        path: Absolute or relative path to the file.
        limit: Optional maximum number of lines to return.
    """
    try:
        return file_ops.read_file(path, limit)
    except (FileNotFoundError, ValueError, OSError) as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# File-mutation tools (trigger diff display)
# ---------------------------------------------------------------------------

@tool
def write_file_tool(path: str, content: str) -> str:
    """Write content to a file, creating parent directories as needed.

    Args:
        path: Absolute or relative path to the file to write.
        content: Full content to write to the file.
    """
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
    Make sure `old` is unique enough to identify the correct location.

    Args:
        path: Path to the file to edit.
        old: The exact text to find and replace (must exist in the file).
        new: The replacement text.
    """
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

    Args:
        pattern: Glob pattern such as '**/*.py' or '*.ts'.
        path: Directory to search in (defaults to current directory).
    """
    try:
        return file_ops.glob_files(pattern, path)
    except (FileNotFoundError, ValueError, OSError) as e:
        return f"Error: {e}"


@tool
def grep_tool(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    """Search for a regex pattern inside files.

    Args:
        pattern: Regular expression to search for.
        path: Directory to search in (defaults to current directory).
        file_pattern: Glob pattern to filter which files are searched (e.g. '*.py').
    """
    try:
        return file_ops.search_in_files(pattern, path, file_pattern)
    except (FileNotFoundError, ValueError, OSError) as e:
        return f"Error: {e}"


@tool
def list_directory_tool(path: str = ".") -> str:
    """List the contents of a directory.

    Args:
        path: Directory path to list (defaults to current directory).
    """
    try:
        return file_ops.list_directory(path)
    except (FileNotFoundError, ValueError, OSError) as e:
        return f"Error: {e}"


@tool
def run_command_tool(command: str, timeout: int = 60) -> str:
    """Run a shell command and return its output.

    Use this to run tests, build tools, git commands, package managers, etc.
    Avoid commands that require interactive input.

    Args:
        command: Shell command to execute.
        timeout: Maximum seconds to wait before giving up (default 60).
    """
    return shell.run_command(command, timeout=timeout)


@tool
def get_directory_tool() -> str:
    """Get the current working directory path."""
    return shell.get_working_directory()


@tool
def get_project_files_tool(extensions: Optional[List[str]] = None) -> str:
    """List all source files in the project, filtered by extension.

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
# Tool registries
# ---------------------------------------------------------------------------

# All tools available to agent/assist modes
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
    get_project_files_tool,
    get_git_info_tool,
    get_environment_tool,
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
