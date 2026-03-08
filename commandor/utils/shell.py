import subprocess
import os
import platform
from pathlib import Path
from typing import Optional, Tuple, List
import json


def run_command(
    command: str,
    timeout: int = 60,
    cwd: Optional[str] = None
) -> str:
    """Run a shell command
    
    Args:
        command: Command to execute
        timeout: Timeout in seconds
        cwd: Working directory
    
    Returns:
        Command output
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd or str(Path.cwd()),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        output = []
        
        if result.stdout:
            output.append(result.stdout)
        
        if result.stderr:
            output.append(f"[stderr] {result.stderr}")
        
        if result.returncode != 0:
            output.append(f"[exit code: {result.returncode}]")
        
        if not output:
            output.append("(no output)")
        
        return "\n".join(output)
    
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error: {str(e)}"


def get_working_directory() -> str:
    """Get current working directory"""
    return str(Path.cwd())


def change_directory(path: str) -> str:
    """Change working directory
    
    Args:
        path: Directory path
    
    Returns:
        Success/failure message
    """
    try:
        target = Path(path)
        
        if not target.is_absolute():
            target = Path.cwd() / target
        
        target = target.resolve()
        
        if not target.exists():
            return f"Error: Directory not found: {path}"
        
        if not target.is_dir():
            return f"Error: Not a directory: {path}"
        
        os.chdir(target)
        return f"Changed directory to: {target}"
    
    except Exception as e:
        return f"Error: {str(e)}"


def get_environment_info() -> str:
    """Get system environment information
    
    Returns:
        Environment info as string
    """
    info = {
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "shell": os.environ.get("SHELL", "unknown"),
        "cwd": str(Path.cwd()),
        "user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
    }
    
    return json.dumps(info, indent=2)


def get_git_info() -> str:
    """Get git repository information
    
    Returns:
        Git info as string
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        
        if result.returncode != 0:
            return "Not a git repository"
        
        status = result.stdout.strip()
        
        # Get branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        branch = branch_result.stdout.strip() or "unknown"
        
        # Get recent commits
        commits_result = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        commits = commits_result.stdout.strip()
        
        info = f"""Branch: {branch}
Status: {"clean" if not status else "dirty"}
Recent commits:
{commits}"""
        
        return info
    
    except Exception as e:
        return f"Not a git repository: {str(e)}"


def get_project_files(extensions: Optional[List[str]] = None) -> str:
    """Get list of project files
    
    Args:
        extensions: File extensions to include (e.g., ['.py', '.js'])
    
    Returns:
        List of project files
    """
    from .file_ops import list_directory
    
    if extensions is None:
        extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.h']
    
    files = []
    cwd = Path.cwd()
    
    # Common directories to ignore
    ignore_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'dist', 'build', '.next', 'target'}
    
    for ext in extensions:
        for f in cwd.rglob(f'*{ext}'):
            # Check if any parent should be ignored
            if not any(part in ignore_dirs for part in f.parts):
                rel = f.relative_to(cwd)
                files.append(str(rel))
    
    if not files:
        return "No project files found"
    
    files.sort()
    
    result = [f"Found {len(files)} file(s):"]
    result.extend(files[:50])
    
    if len(files) > 50:
        result.append(f"... and {len(files) - 50} more")
    
    return "\n".join(result)


DANGEROUS_PATTERNS = [
    'rm -rf',
    'sudo rm',
    'dd if=',
    'mkfs',
    '> /dev/sd',
    'curl | sh',
    'wget | sh',
    ':(){:|:&};:',
]


def is_dangerous(command: str) -> bool:
    """Check if a command is potentially dangerous
    
    Args:
        command: Command to check
    
    Returns:
        True if dangerous
    """
    cmd_lower = command.lower()
    
    for pattern in DANGEROUS_PATTERNS:
        if pattern in cmd_lower:
            return True
    
    return False
