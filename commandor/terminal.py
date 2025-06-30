import os
import subprocess
import platform
import shutil
from pathlib import Path
from typing import Optional, Tuple
import google.generativeai as genai
from decouple import config

# Import readline for better terminal input handling
try:
    import readline
    READLINE_AVAILABLE = True
except ImportError:
    try:
        import pyreadline3 as readline
        READLINE_AVAILABLE = True
    except ImportError:
        print("⚠️  For better terminal experience, install: pip install pyreadline3")
        READLINE_AVAILABLE = False

class AITerminal:
    """An intelligent terminal that uses AI to convert natural language to shell commands."""
    
    def __init__(self):
        self.api_key = config("GEMINI")
        self.current_dir = Path.cwd()
        self.command_history = []
        self.max_history = 100
        self.system_info = self._get_system_info()
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash")
        
        # Colors for output
        self.colors = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'reset': '\033[0m',
            'bold': '\033[1m',
            'bright_red': '\033[91m\033[1m',
            'bright_green': '\033[92m\033[1m',
            'bright_yellow': '\033[93m\033[1m',
            'bright_blue': '\033[94m\033[1m',
            'bright_magenta': '\033[95m\033[1m',
            'bright_cyan': '\033[96m\033[1m'
        }
        
        # Setup readline if available
        self._setup_readline()

    def _get_system_info(self) -> dict:
        """Gather system information for better context."""
        return {
            'os': platform.system(),
            'os_version': platform.version(),
            'architecture': platform.machine(),
            'python_version': platform.python_version(),
            'shell': os.environ.get('SHELL', 'unknown'),
            'user': os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))
        }

    def _setup_readline(self):
        """Setup readline for better terminal input experience."""
        if not READLINE_AVAILABLE:
            return
        
        # Set up history file
        history_file = Path.home() / '.ai_terminal_history'
        
        try:
            # Load existing history
            if history_file.exists():
                readline.read_history_file(str(history_file))
            
            # Set history length
            readline.set_history_length(1000)
            
            # Enable tab completion for file paths
            readline.set_completer_delims(' \t\n`!@#$%^&*()=+[{]}\\|;:\'",<>?')
            readline.parse_and_bind("tab: complete")
            
            # Enable vi or emacs mode (emacs is default)
            readline.parse_and_bind("set editing-mode emacs")
            
            # Custom key bindings
            readline.parse_and_bind("\\C-p: previous-history")  # Ctrl+P for previous
            readline.parse_and_bind("\\C-n: next-history")     # Ctrl+N for next
            
            # Save history on exit
            import atexit
            atexit.register(lambda: readline.write_history_file(str(history_file)))
            
        except Exception as e:
            print(f"Warning: Could not setup readline: {e}")

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text."""
        return f"{self.colors.get(color, '')}{text}{self.colors['reset']}"

    def _display_colorful_logo(self):
        """Display colorful Commandor logo."""
        logo = f"""
{self._colorize('╔═══════════════════════════════════════════════════════════════╗', 'bright_cyan')}
{self._colorize('║', 'bright_cyan')}  {self._colorize('█▀▀ █▀█ █▀▄▀█ █▀▄▀█ █▀█ █▄░█ █▀▄ █▀█ █▀█', 'bright_magenta')}  {self._colorize('║', 'bright_cyan')}
{self._colorize('║', 'bright_cyan')}  {self._colorize('█▄▄ █▄█ █░▀░█ █░▀░█ █▄█ █░▀█ █▄▀ █▄█ █▀▄', 'bright_blue')}  {self._colorize('║', 'bright_cyan')}
{self._colorize('║', 'bright_cyan')}                                                             {self._colorize('║', 'bright_cyan')}
{self._colorize('║', 'bright_cyan')}    {self._colorize('🤖 Your AI-Powered Terminal Assistant 🤖', 'bright_yellow')}        {self._colorize('║', 'bright_cyan')}
{self._colorize('║', 'bright_cyan')}           {self._colorize('Speak naturally, execute powerfully!', 'bright_green')}       {self._colorize('║', 'bright_cyan')}
{self._colorize('╚═══════════════════════════════════════════════════════════════╝', 'bright_cyan')}
        """
        print(logo)

    def _get_directory_context(self) -> str:
        """Get context about the current directory."""
        try:
            files = []
            dirs = []
            
            # Get first 10 items for context
            for item in sorted(self.current_dir.iterdir())[:10]:
                if item.is_file():
                    files.append(item.name)
                elif item.is_dir():
                    dirs.append(item.name)
            
            context = f"Current directory: {self.current_dir}\n"
            if dirs:
                context += f"Directories: {', '.join(dirs[:5])}\n"
            if files:
                context += f"Files: {', '.join(files[:5])}\n"
                
            return context
        except PermissionError:
            return f"Current directory: {self.current_dir} (limited access)\n"

    def _get_recent_commands(self) -> str:
        """Get recent command history for context."""
        if not self.command_history:
            return ""
        
        recent = self.command_history[-3:]  # Last 3 commands
        return "Recent commands:\n" + "\n".join([f"  {cmd}" for cmd in recent]) + "\n"

    def get_ai_command(self, instruction: str) -> str:
        """Convert natural language instruction to shell command using AI."""
        context = self._get_directory_context()
        recent_commands = self._get_recent_commands()
        
        prompt = f"""You are an expert system administrator helping convert natural language to shell commands.

        SYSTEM INFORMATION:
        - OS: {self.system_info['os']} {self.system_info['os_version']}
        - Architecture: {self.system_info['architecture']}
        - Shell: {self.system_info['shell']}
        - User: {self.system_info['user']}

        CURRENT CONTEXT:
        {context}

        {recent_commands}

        INSTRUCTION: "{instruction}"

        RULES:
        1. Reply with ONLY the shell command, no explanations
        2. Use commands appropriate for {self.system_info['os']}
        3. Consider the current directory context
        4. Use safe commands (avoid destructive operations without explicit confirmation)
        5. For file operations, use relative paths when possible
        6. If the instruction is ambiguous, choose the most common interpretation

        Command:"""

        try:
            response = self.model.generate_content(prompt)
            command = response.text.strip()
            
            # Remove code block markers if present
            if command.startswith('```'):
                lines = command.split('\n')
                command = '\n'.join(lines[1:-1]) if len(lines) > 2 else lines[1]
            
            return command.strip()
        except Exception as e:
            return f"# Error getting AI response: {e}"

    def ask_ai(self, question: str) -> str:
        """Ask AI a general question (not command-related)."""
        context = self._get_directory_context()
        
        prompt = f"""You are a helpful AI assistant. Answer the user's question clearly and concisely.

        SYSTEM CONTEXT (for reference only):
        - OS: {self.system_info['os']}
        - Current Directory: {self.current_dir}
        
        QUESTION: "{question}"

        Please provide a helpful and informative answer. If the question is about system administration, programming, or technical topics, provide practical advice. Keep responses concise but comprehensive."""

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"Sorry, I couldn't process your question: {e}"

    def execute_command(self, command: str) -> Tuple[bool, str, str]:
        """Execute a shell command and return success status and output."""
        try:
            # Handle cd commands specially to maintain directory state
            if command.strip().startswith('cd '):
                return self._handle_cd_command(command)
            
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.current_dir),
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            success = result.returncode == 0
            return success, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out after 30 seconds"
        except Exception as e:
            return False, "", str(e)

    def _handle_cd_command(self, command: str) -> Tuple[bool, str, str]:
        """Handle cd commands to update current directory."""
        parts = command.strip().split(maxsplit=1)
        
        if len(parts) == 1:
            # cd with no arguments goes to home
            target = Path.home()
        else:
            path = parts[1].strip('\'"')  # Remove quotes
            target = Path(path)
            
            # Handle relative paths
            if not target.is_absolute():
                target = self.current_dir / target
        
        try:
            resolved_target = target.resolve()
            if resolved_target.exists() and resolved_target.is_dir():
                os.chdir(resolved_target)
                self.current_dir = resolved_target
                return True, f"Changed directory to {resolved_target}", ""
            else:
                return False, "", f"Directory not found: {target}"
        except (OSError, PermissionError) as e:
            return False, "", f"Cannot access directory: {e}"

    def display_output(self, success: bool, stdout: str, stderr: str):
        """Display command output with appropriate formatting."""
        if stdout:
            print(stdout, end='')
        
        if stderr:
            print(self._colorize(stderr, 'red'), end='')
        
        if not success and not stderr:
            print(self._colorize("Command failed", 'red'))

    def get_prompt(self) -> str:
        """Generate the terminal prompt."""
        dir_name = self.current_dir.name if self.current_dir.name else str(self.current_dir)
        
        # Shorten long directory names
        if len(dir_name) > 20:
            dir_name = "..." + dir_name[-17:]
        
        return f"{self._colorize('Commandor', 'bright_cyan')} {self._colorize('$', 'bright_yellow')} "

    def show_help(self):
        """Display help information."""
        help_text = f"""
        {self._colorize('🚀 Commandor Help Guide 🚀', 'bold')}
        {self._colorize('=' * 60, 'bright_blue')}

        {self._colorize('Special Commands:', 'bright_green')}
        {self._colorize('/ai <instruction>', 'bright_cyan')}  - Convert natural language to shell command
        {self._colorize('/ask <question>', 'bright_magenta')}   - Ask AI any question directly
        {self._colorize('/help', 'yellow')}             - Show this help message
        {self._colorize('/info', 'yellow')}             - Show system information
        {self._colorize('/history', 'yellow')}          - Show recent command history
        {self._colorize('/clear', 'yellow')}            - Clear the screen
        {self._colorize('exit', 'red')} or {self._colorize('Ctrl+C', 'red')}       - Exit the terminal

        {self._colorize('AI Command Examples:', 'bright_yellow')}
        {self._colorize('/ai', 'bright_cyan')} list all python files
        {self._colorize('/ai', 'bright_cyan')} create a new directory called projects
        {self._colorize('/ai', 'bright_cyan')} find files larger than 100MB
        {self._colorize('/ai', 'bright_cyan')} show disk usage
        {self._colorize('/ai', 'bright_cyan')} install package using pip

        {self._colorize('Ask AI Examples:', 'bright_yellow')}
        {self._colorize('/ask', 'bright_magenta')} What is the difference between Python and JavaScript?
        {self._colorize('/ask', 'bright_magenta')} How do I optimize my code for better performance?
        {self._colorize('/ask', 'bright_magenta')} Explain machine learning concepts
        {self._colorize('/ask', 'bright_magenta')} What are best practices for Git workflow?

        {self._colorize('💡 Regular shell commands work too!', 'bright_green')}
        """
        print(help_text)

    def show_info(self):
        """Display system information."""
        info_text = f"""
        {self._colorize('🖥️  System Information', 'bold')}
        {self._colorize('=' * 35, 'bright_blue')}
        {self._colorize('OS:', 'bright_cyan')} {self.system_info['os']} {self.system_info['os_version']}
        {self._colorize('Architecture:', 'bright_cyan')} {self.system_info['architecture']}
        {self._colorize('Python:', 'bright_cyan')} {self.system_info['python_version']}
        {self._colorize('Shell:', 'bright_cyan')} {self.system_info['shell']}
        {self._colorize('User:', 'bright_cyan')} {self.system_info['user']}
        {self._colorize('Current Directory:', 'bright_cyan')} {self.current_dir}
        """
        print(info_text)

    def show_history(self):
        """Display recent command history."""
        if not self.command_history:
            print(self._colorize("📝 No command history available", 'yellow'))
            return
        
        print(self._colorize("📚 Recent Commands:", 'bold'))
        print(self._colorize('-' * 25, 'bright_blue'))
        for i, cmd in enumerate(self.command_history[-10:], 1):
            print(f"{self._colorize(f'{i:2d}.', 'bright_cyan')} {cmd}")

    def add_to_history(self, command: str):
        """Add command to history."""
        if command and command not in ['exit', '/help', '/info', '/history', '/clear']:
            self.command_history.append(command)
            if len(self.command_history) > self.max_history:
                self.command_history.pop(0)
            
            # Add to readline history if available
            if READLINE_AVAILABLE:
                readline.add_history(command)

    def get_input(self, prompt: str) -> str:
        """Get user input with proper readline support."""
        try:
            return input(prompt).strip()
        except EOFError:
            raise KeyboardInterrupt  # Treat EOF as exit signal

    def run(self):
        """Main terminal loop."""
        self._display_colorful_logo()
        
        if READLINE_AVAILABLE:
            print(f"✨ {self._colorize('Enhanced input mode active!', 'bright_green')}")
        else:
            print("⚠️  Basic input mode (install 'readline' or 'pyreadline3' for better experience)")
        
        print(f"Type {self._colorize('/help', 'bright_cyan')} for commands or {self._colorize('Ctrl+C', 'bright_yellow')} to exit.")
        print(f"Use {self._colorize('/ai', 'bright_cyan')} for commands or {self._colorize('/ask', 'bright_magenta')} for questions!")
        print()

        while True:
            try:
                user_input = self.get_input(self.get_prompt())
                
                if not user_input:
                    continue
                
                # Handle special commands
                if user_input == 'exit':
                    break
                elif user_input == '/help':
                    self.show_help()
                    continue
                elif user_input == '/info':
                    self.show_info()
                    continue
                elif user_input == '/history':
                    self.show_history()
                    continue
                elif user_input == '/clear':
                    os.system('clear' if os.name != 'nt' else 'cls')
                    continue
                
                # Handle AI questions
                elif user_input.startswith('/ask '):
                    question = user_input[5:].strip()
                    if not question:
                        print(self._colorize("❓ Please provide a question after /ask", 'yellow'))
                        continue
                    
                    print(self._colorize("🤔 Thinking...", 'yellow'))
                    ai_response = self.ask_ai(question)
                    print(f"\n{self._colorize('🤖 AI Response:', 'bright_green')}")
                    print(f"{self._colorize('─' * 50, 'blue')}")
                    print(ai_response)
                    print(f"{self._colorize('─' * 50, 'blue')}\n")
                    self.add_to_history(f"/ask {question}")
                    continue
                
                # Handle AI commands
                elif user_input.startswith('/ai '):
                    instruction = user_input[4:].strip()
                    if not instruction:
                        print(self._colorize("💡 Please provide an instruction after /ai", 'yellow'))
                        continue
                    
                    print(self._colorize("🧠 Generating command...", 'yellow'))
                    ai_command = self.get_ai_command(instruction)
                    print(f"{self._colorize('🤖 AI →', 'bright_green')} {self._colorize(ai_command, 'bright_blue')}")
                    
                    # Ask for confirmation for potentially dangerous commands
                    dangerous_patterns = ['rm -rf', 'sudo rm', 'format', 'mkfs', '> /dev/', 'dd if=']
                    if any(pattern in ai_command.lower() for pattern in dangerous_patterns):
                        confirm = self.get_input(self._colorize("⚠️  This command looks dangerous. Execute? (y/N): ", 'bright_yellow'))
                        if confirm.lower() != 'y':
                            print(self._colorize("❌ Command cancelled", 'yellow'))
                            continue
                    
                    success, stdout, stderr = self.execute_command(ai_command)
                    self.display_output(success, stdout, stderr)
                    self.add_to_history(f"/ai {instruction} → {ai_command}")
                
                # Handle regular shell commands
                else:
                    success, stdout, stderr = self.execute_command(user_input)
                    self.display_output(success, stdout, stderr)
                    self.add_to_history(user_input)
                    
            except KeyboardInterrupt:
                print(f"\n{self._colorize('👋 Goodbye! Thanks for using Commandor!', 'bright_green')}")
                break
            except EOFError:
                print(f"\n{self._colorize('👋 Goodbye! Thanks for using Commandor!', 'bright_green')}")
                break
            except Exception as e:
                print(self._colorize(f"💥 Unexpected error: {e}", 'red'))

if __name__ == "__main__":
    terminal = AITerminal()
    terminal.run()