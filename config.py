"""
Configuration Module
Contains application configuration settings and constants.
"""

import os
from pathlib import Path


class Config:
    """Application configuration settings."""
    
    # Application info
    APP_NAME = "AI Terminal"
    APP_VERSION = "1.0.0"
    
    # File paths
    HISTORY_FILE = ".ai_terminal_history"
    COMMAND_HISTORY_FILE = ".ai_command_history.json"
    CONFIG_FILE = ".ai_terminal_config.json"
    LOG_FILE = "ai_terminal.log"
    
    # AI Model settings
    DEFAULT_MODEL = "llama3.2:1b"
    MAX_CONVERSATION_HISTORY = 50
    MAX_COMMAND_HISTORY = 100
    
    # Execution settings
    DEFAULT_TIMEOUT = 30  # seconds
    MAX_COMMAND_LENGTH = 1000
    
    # Safety settings
    ENABLE_SAFETY_CHECKS = True
    REQUIRE_CONFIRMATION = True
    
    # Display settings
    ENABLE_COLORS = True
    PROMPT_FORMAT = "AI-Terminal> "
    
    # Paths
    HOME_DIR = Path.home()
    CONFIG_DIR = HOME_DIR / ".ai_terminal"
    
    @classmethod
    def init_config_dir(cls):
        """Initialize configuration directory if it doesn't exist."""
        cls.CONFIG_DIR.mkdir(exist_ok=True)
    
    @classmethod
    def get_full_path(cls, filename):
        """Get full path for configuration files."""
        return cls.CONFIG_DIR / filename
    
    @classmethod
    def load_user_config(cls):
        """Load user-specific configuration from file."""
        config_path = cls.get_full_path(cls.CONFIG_FILE)
        if config_path.exists():
            try:
                import json
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    # Update class attributes with user config
                    for key, value in user_config.items():
                        if hasattr(cls, key.upper()):
                            setattr(cls, key.upper(), value)
            except Exception as e:
                print(f"Warning: Could not load user config: {e}")
    
    @classmethod
    def save_user_config(cls):
        """Save current configuration to file."""
        config_path = cls.get_full_path(cls.CONFIG_FILE)
        try:
            import json
            config_data = {
                'default_model': cls.DEFAULT_MODEL,
                'default_timeout': cls.DEFAULT_TIMEOUT,
                'enable_safety_checks': cls.ENABLE_SAFETY_CHECKS,
                'enable_colors': cls.ENABLE_COLORS,
                'max_conversation_history': cls.MAX_CONVERSATION_HISTORY,
                'max_command_history': cls.MAX_COMMAND_HISTORY
            }
            
            cls.init_config_dir()
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save user config: {e}")


# Dangerous command patterns
DANGEROUS_PATTERNS = [
    'format', 'rmdir /s', 'del /s', 'rd /s',
    'shutdown', 'restart', 'reg delete',
    'diskpart', 'fdisk', 'attrib -r -s -h',
    'system32', 'boot.ini', 'registry',
    'sfc /scannow', 'dism', 'bcdedit',
    'powercfg', 'netsh wlan delete',
    'taskkill /f', 'wmic', 'cipher /w'
]

# Common command completions
COMMON_COMMANDS = [
    '/ai', '/ask', 'exit', 'help', 'clear',
    'dir', 'cd', 'mkdir', 'rmdir', 'copy', 'del',
    'type', 'find', 'findstr', 'tree', 'ping',
    'ipconfig', 'netstat', 'tasklist', 'systeminfo',
    'where', 'which', 'echo', 'set', 'path',
    'attrib', 'xcopy', 'robocopy', 'fc', 'comp'
]

# File extensions to handle specially
EXECUTABLE_EXTENSIONS = [
    '.exe', '.bat', '.cmd', '.com', '.scr',
    '.pif', '.application', '.gadget', '.msi',
    '.msp', '.cpl', '.scf', '.lnk', '.inf'
]

# Safe command categories
SAFE_COMMAND_CATEGORIES = {
    'navigation': ['cd', 'dir', 'tree', 'pushd', 'popd'],
    'file_info': ['type', 'more', 'find', 'findstr', 'fc', 'comp'],
    'system_info': ['systeminfo', 'tasklist', 'ipconfig', 'ping', 'tracert'],
    'directory_ops': ['mkdir', 'md'],
    'file_ops': ['copy', 'xcopy', 'move', 'ren', 'rename'],
    'display': ['echo', 'cls', 'title', 'color', 'prompt']
}

# AI System prompts
COMMAND_SYSTEM_PROMPT = """You are an expert Linux command-line assistant. Convert natural language instructions to Linux commands.

IMPORTANT SAFETY RULES:
- Never suggest commands that could harm the system (like deleting system files)
- Always use safe, reversible operations when possible
- For file operations, suggest checking first (e.g., 'dir' before 'del')
- Output ONLY the command(s), no explanations or code blocks
- Use multiple lines for complex operations
- Prefer built-in Linux commands over third-party tools
- When in doubt, choose the safer option

SYSTEM CONTEXT:
{context}

EXAMPLES:
User: "list files" → dir
User: "show hidden files" → dir /a
User: "create folder called test" → mkdir test
User: "copy all text files to backup" → xcopy *.txt backup\
User: "find files containing python" → findstr /s /i "python" *.*
"""

CONVERSATION_SYSTEM_PROMPT = """You are a helpful AI assistant integrated into a command-line terminal. 
You can help with general questions, programming concepts, troubleshooting, 
explanations, and casual conversation. Be concise but informative. 
If the user asks about terminal/command-line related topics, you can be more detailed.

Keep responses practical and actionable when possible. If discussing technical topics,
provide examples or analogies to make concepts clearer.
"""

# Error messages
ERROR_MESSAGES = {
    'model_not_found': "AI model '{model}' not found. Please check if Ollama is running and the model is installed.",
    'connection_failed': "Failed to connect to AI service. Please ensure Ollama is running.",
    'command_too_long': "Command exceeds maximum length of {max_length} characters.",
    'unsafe_command': "Command appears to be potentially dangerous: {reason}",
    'execution_timeout': "Command execution timed out after {timeout} seconds.",
    'invalid_input': "Invalid input provided. Please try again.",
    'file_not_found': "File or directory not found: {path}",
    'permission_denied': "Permission denied. You may need administrator privileges.",
    'unknown_error': "An unexpected error occurred: {error}"
}

# Success messages
SUCCESS_MESSAGES = {
    'command_executed': "Command executed successfully.",
    'config_saved': "Configuration saved successfully.",
    'history_cleared': "Command history cleared.",
    'directory_changed': "Directory changed to: {path}",
    'model_changed': "AI model changed to: {model}"
}

# Help text templates
HELP_TEMPLATES = {
    'main_help': """
{app_name} v{version} - AI-Powered Terminal Assistant

COMMANDS:
  /ai <instruction>    Convert natural language to command
  /ask <question>      Ask AI anything (general conversation)
  help                 Show this help message
  clear                Clear the screen
  exit                 Exit the terminal

EXAMPLES:
  /ai list all files in current directory
  /ai create a new folder called projects
  /ask what is the difference between TCP and UDP?
  /ask how do I optimize my Python code?

Type '/ai help' or '/ask help' for more specific examples.
""",
    
    'ai_help': """
AI COMMAND EXAMPLES:
  /ai list all files and folders
  /ai create a backup of my documents folder
  /ai find all python files in this directory
  /ai show disk space usage
  /ai display network configuration
  /ai compress this folder into a zip file
  /ai show running processes
  /ai check system information
  /ai find files modified today
  /ai copy all images to a backup folder
""",
    
    'ask_help': """
AI CONVERSATION EXAMPLES:
  /ask what is the difference between git merge and git rebase?
  /ask how do I debug a Python script?
  /ask explain REST APIs in simple terms
  /ask what are the best practices for password security?
  /ask how does machine learning work?
  /ask why is my code running slowly?
  /ask what is the difference between compiled and interpreted languages?
  /ask how do I improve my command line skills?

💡 Tip: I remember our conversation context, so you can ask follow-up questions!
"""
}

# Logging configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'ai_terminal.log',
    'max_size': 10 * 1024 * 1024,  # 10MB
    'backup_count': 3
}

# Performance settings
PERFORMANCE_CONFIG = {
    'max_output_lines': 1000,
    'max_history_size': 1000,
    'gc_threshold': 100,  # Garbage collection threshold
    'response_timeout': 30,
    'max_retries': 3
}

# Feature flags
FEATURES = {
    'auto_completion': True,
    'syntax_highlighting': False,  # Not implemented yet
    'command_suggestions': True,
    'conversation_memory': True,
    'command_history': True,
    'safety_warnings': True,
    'progress_indicators': True
}

def get_config_value(key, default=None):
    """Get configuration value with fallback to default."""
    return getattr(Config, key.upper(), default)

def set_config_value(key, value):
    """Set configuration value."""
    setattr(Config, key.upper(), value)

def validate_config():
    """Validate configuration settings."""
    errors = []
    
    if Config.DEFAULT_TIMEOUT <= 0:
        errors.append("DEFAULT_TIMEOUT must be positive")
    
    if Config.MAX_COMMAND_LENGTH <= 0:
        errors.append("MAX_COMMAND_LENGTH must be positive")
    
    if Config.MAX_CONVERSATION_HISTORY <= 0:
        errors.append("MAX_CONVERSATION_HISTORY must be positive")
    
    return errors

def reset_config():
    """Reset configuration to defaults."""
    Config.DEFAULT_MODEL = "llama3.2:1b"
    Config.DEFAULT_TIMEOUT = 30
    Config.MAX_COMMAND_LENGTH = 1000
    Config.ENABLE_SAFETY_CHECKS = True
    Config.REQUIRE_CONFIRMATION = True
    Config.ENABLE_COLORS = True
    Config.MAX_CONVERSATION_HISTORY = 50
    Config.MAX_COMMAND_HISTORY = 100