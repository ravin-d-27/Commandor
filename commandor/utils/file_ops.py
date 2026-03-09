import os
import shutil
from pathlib import Path
from typing import Optional, List
import subprocess


def read_file(path: str, limit: Optional[int] = None) -> str:
    """Read file contents
    
    Args:
        path: File path to read
        limit: Optional line limit
    
    Returns:
        File contents as string
    """
    p = Path(path)
    
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    if not p.is_file():
        raise ValueError(f"Not a file: {path}")
    
    try:
        with open(p, 'r', encoding='utf-8') as f:
            if limit:
                lines = []
                for i, line in enumerate(f):
                    if i >= limit:
                        lines.append(f"\n... (truncated, showing first {limit} lines)")
                        break
                    lines.append(line)
                return ''.join(lines)
            return f.read()
    except UnicodeDecodeError:
        with open(p, 'rb') as f:
            return f"<Binary file: {path}>"


def write_file(path: str, content: str, create_dirs: bool = True) -> str:
    """Write content to file
    
    Args:
        path: File path to write
        content: Content to write
        create_dirs: Create parent directories if needed
    
    Returns:
        Success message
    """
    p = Path(path)
    
    if create_dirs:
        p.parent.mkdir(parents=True, exist_ok=True)
    
    with open(p, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return f"Successfully wrote to {path}"


def edit_file(path: str, old: str, new: str) -> str:
    """Edit a file by replacing old text with new
    
    Args:
        path: File path to edit
        old: Text to find
        new: Text to replace with
    
    Returns:
        Success message
    """
    p = Path(path)
    
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    with open(p, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if old not in content:
        raise ValueError(f"Text not found in file: {old[:50]}...")
    
    new_content = content.replace(old, new)
    
    with open(p, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    return f"Successfully edited {path}"


def create_directory(path: str) -> str:
    """Create a directory
    
    Args:
        path: Directory path to create
    
    Returns:
        Success message
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return f"Created directory: {path}"


def delete_file(path: str) -> str:
    """Delete a file
    
    Args:
        path: File path to delete
    
    Returns:
        Success message
    """
    p = Path(path)
    
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    
    return f"Deleted: {path}"


def list_directory(path: str = ".") -> str:
    """List directory contents
    
    Args:
        path: Directory path to list
    
    Returns:
        Directory listing
    """
    p = Path(path)
    
    if not p.exists():
        raise FileNotFoundError(f"Directory not found: {path}")
    
    if not p.is_dir():
        raise ValueError(f"Not a directory: {path}")
    
    items = []
    for item in sorted(p.iterdir()):
        icon = "📁" if item.is_dir() else "📄"
        items.append(f"{icon} {item.name}")
    
    if not items:
        return "(empty directory)"
    
    return "\n".join(items)


def glob_files(pattern: str, path: str = ".") -> str:
    """Find files matching a glob pattern
    
    Args:
        pattern: Glob pattern (e.g., "*.py")
        path: Directory to search in
    
    Returns:
        List of matching files
    """
    p = Path(path)
    
    if not p.exists():
        raise FileNotFoundError(f"Directory not found: {path}")
    
    files = list(p.glob(pattern))
    
    if not files:
        return f"No files matching {pattern}"
    
    result = [f"Found {len(files)} file(s):"]
    for f in sorted(files)[:50]:
        rel = f.relative_to(p) if f.is_relative_to(p) else f
        result.append(f"  {rel}")
    
    if len(files) > 50:
        result.append(f"  ... and {len(files) - 50} more")
    
    return "\n".join(result)


def search_in_files(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    """Search for pattern in files
    
    Args:
        pattern: Text pattern to search for
        path: Directory to search in
        file_pattern: File glob pattern (e.g., "*.py")
    
    Returns:
        Search results
    """
    import re
    
    p = Path(path)
    
    if not p.exists():
        raise FileNotFoundError(f"Directory not found: {path}")
    
    try:
        regex = re.compile(pattern)
    except re.error:
        regex = re.compile(re.escape(pattern))
    
    matches = []
    for f in p.rglob(file_pattern):
        if f.is_file():
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    for i, line in enumerate(file, 1):
                        if regex.search(line):
                            matches.append(f"{f}:{i}: {line.rstrip()}")
                            if len(matches) >= 100:
                                break
            except:
                pass
        
        if len(matches) >= 100:
            break
    
    if not matches:
        return f"No matches for '{pattern}'"
    
    result = [f"Found {len(matches)} match(es):"]
    result.extend(matches[:50])
    
    if len(matches) > 50:
        result.append(f"... and {len(matches) - 50} more")
    
    return "\n".join(result)


def get_file_info(path: str) -> str:
    """Get file information
    
    Args:
        path: File path
    
    Returns:
        File information
    """
    p = Path(path)
    
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    stat = p.stat()
    
    info = [
        f"Path: {p.absolute()}",
        f"Type: {'Directory' if p.is_dir() else 'File'}",
        f"Size: {stat.st_size} bytes",
    ]
    
    if p.is_file():
        with open(p, 'r', encoding='utf-8', errors='ignore') as f:
            lines = sum(1 for _ in f)
        info.append(f"Lines: {lines}")
    
    return "\n".join(info)
