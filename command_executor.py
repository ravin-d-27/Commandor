"""
Command Executor Module
Handles the actual execution of shell commands with proper error handling.
"""

import subprocess
import os
from utils import Colors, clear_screen


class CommandExecutor:
    """Handles command execution with proper error handling and timeouts."""
    
    def __init__(self, timeout=30):
        self.timeout = timeout
    
    def run_command(self, cmd):
        """Execute command(s) with improved error handling."""
        try:
            commands = [c.strip() for c in cmd.strip().splitlines() if c.strip()]
            full_output = ""
            full_error = ""

            for command in commands:
                print(f"\n{Colors.BLUE}>> {command}{Colors.RESET}")
                
                # Handle built-in commands
                if command.lower() == 'clear':
                    clear_screen()
                    continue
                
                # Handle change directory commands specially
                if command.lower().startswith('cd '):
                    try:
                        path = command[3:].strip()
                        if path == '..':
                            os.chdir('..')
                        elif path == '.':
                            pass  # Stay in current directory
                        else:
                            os.chdir(path)
                        full_output += f"Changed directory to: {os.getcwd()}\n"
                        continue
                    except Exception as e:
                        full_error += f"Failed to change directory: {e}\n"
                        continue
                
                # Run the command
                result = subprocess.run(
                    command, 
                    shell=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self.timeout
                )
                
                if result.stdout:
                    full_output += result.stdout + "\n"
                if result.stderr:
                    full_error += result.stderr + "\n"
                
                # Break on first error for safety
                if result.returncode != 0:
                    break

            return full_output.strip(), full_error.strip()
            
        except subprocess.TimeoutExpired:
            return "", f"Command timed out after {self.timeout} seconds"
        except Exception as e:
            return "", f"Execution error: {e}"
    
    def run_command_async(self, cmd):
        """Run command asynchronously (for long-running processes)."""
        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return process
        except Exception as e:
            return None, f"Failed to start async process: {e}"
    
    def set_timeout(self, timeout):
        """Set the timeout for command execution."""
        self.timeout = timeout
    
    def get_current_directory(self):
        """Get the current working directory."""
        return os.getcwd()
    
    def change_directory(self, path):
        """Change the current working directory."""
        try:
            os.chdir(path)
            return True, f"Changed to: {os.getcwd()}"
        except Exception as e:
            return False, f"Failed to change directory: {e}"