"""
Utility Module
Contains common utility functions and constants used across the application.
"""

import os
import sys


class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_system_info():
    """Get basic system information."""
    info = {
        'os': os.name,
        'platform': sys.platform,
        'python_version': sys.version,
        'current_dir': os.getcwd(),
        'username': os.getenv('USERNAME', os.getenv('USER', 'unknown'))
    }
    return info


def format_file_size(size_bytes):
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024.0 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"


def validate_path(path):
    """Validate if a path exists and is accessible."""
    try:
        return os.path.exists(path) and os.access(path, os.R_OK)
    except:
        return False


def safe_input(prompt, default=""):
    """Safe input function with default value."""
    try:
        result = input(prompt).strip()
        return result if result else default
    except (KeyboardInterrupt, EOFError):
        return default


def print_banner(text, color=Colors.CYAN):
    """Print a banner with the given text."""
    border = "=" * len(text)
    print(f"\n{color}{border}{Colors.RESET}")
    print(f"{color}{text}{Colors.RESET}")
    print(f"{color}{border}{Colors.RESET}\n")


def log_error(error_msg, filename="error.log"):
    """Log error messages to a file."""
    try:
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {error_msg}\n")
    except:
        pass  # Fail silently if logging fails


def truncate_text(text, max_length=100):
    """Truncate text to specified length."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."