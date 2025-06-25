"""
Command Processor Module
Handles command validation, safety checks, and preprocessing.
"""

from utils import Colors


class CommandProcessor:
    """Handles command processing and safety validation."""
    
    def __init__(self):
        # Define dangerous command patterns
        self.dangerous_patterns = [
            'format', 'rmdir /s', 'del /s', 'rd /s',
            'shutdown', 'restart', 'reg delete',
            'diskpart', 'fdisk', 'attrib -r -s -h'
        ]
    
    def is_safe_command(self, command):
        """Basic safety check for potentially dangerous commands."""
        command_lower = command.lower()
        for pattern in self.dangerous_patterns:
            if pattern in command_lower:
                return False, f"Potentially dangerous command detected: {pattern}"
        return True, ""
    
    def validate_command(self, command):
        """Validate command syntax and structure."""
        if not command or not command.strip():
            return False, "Empty command"
        
        # Check for basic command structure
        if len(command.strip()) > 1000:
            return False, "Command too long (safety limit)"
        
        return True, ""
    
    def preprocess_command(self, command):
        """Preprocess command before execution."""
        # Remove any potentially harmful prefixes or suffixes
        command = command.strip()
        
        # Handle multi-line commands
        commands = [c.strip() for c in command.splitlines() if c.strip()]
        
        return commands
    
    def suggest_safer_alternative(self, dangerous_command):
        """Suggest safer alternatives for dangerous commands."""
        alternatives = {
            'format': 'Use "chkdsk" to check disk health instead',
            'rmdir /s': 'Use "dir" first to see what will be deleted',
            'del /s': 'Use "dir" first to see what will be deleted',
            'shutdown': 'Consider using "shutdown /t 60" to give time to cancel',
            'reg delete': 'Use "reg query" first to see what will be deleted'
        }
        
        command_lower = dangerous_command.lower()
        for pattern, alternative in alternatives.items():
            if pattern in command_lower:
                return alternative
        
        return "Please double-check this command before running"