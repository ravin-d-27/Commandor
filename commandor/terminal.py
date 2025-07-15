import os
import subprocess
import platform
import shutil
from pathlib import Path
from typing import Optional, Tuple
import google.generativeai as genai

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
        # Initialize colors first - this is critical!
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
        
        # Initialize other attributes
        self.api_key = None
        self.current_dir = Path.cwd()
        self.command_history = []
        self.max_history = 100
        self.system_info = self._get_system_info()
        self.config_dir = Path.home() / '.commandor'
        self.env_file = self.config_dir / '.env'
        self.model = None  # Initialize model as None
        
        # Ensure config directory exists
        try:
            self.config_dir.mkdir(exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create config directory: {e}")
        
        # Setup API key
        self._setup_api_key()
        
        # Configure Gemini only if we have an API key
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel("gemini-2.0-flash")
            except Exception as e:
                print(f"Warning: Could not initialize Gemini model: {e}")
                self.model = None
        
        # Setup readline if available
        self._setup_readline()

    def _setup_api_key(self):
        """Setup Gemini API key with interactive prompt if needed."""
        # Try to load from .env file first
        if self.env_file.exists():
            try:
                with open(self.env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('GEMINI='):
                            self.api_key = line.split('=', 1)[1].strip().strip('"\'')
                            break
            except Exception as e:
                print(f"Warning: Could not read .env file: {e}")
        
        # If no API key found, prompt user
        if not self.api_key:
            self._prompt_for_api_key()

    def _prompt_for_api_key(self):
        """Prompt user for Gemini API key and save it."""
        print(self._colorize('🔑 Gemini API Key Setup Required', 'bright_yellow'))
        print(self._colorize('=' * 45, 'bright_blue'))
        print("To use Commandor, you need a Gemini API key.")
        print("You can get one free at: https://makersuite.google.com/app/apikey")
        print()
        
        while True:
            try:
                api_key = input(self._colorize("Please enter your Gemini API key: ", 'bright_cyan')).strip()
                
                if not api_key:
                    print(self._colorize("❌ API key cannot be empty. Please try again.", 'red'))
                    continue
                
                # Test the API key
                print(self._colorize("🔍 Validating API key...", 'yellow'))
                
                try:
                    genai.configure(api_key=api_key)
                    test_model = genai.GenerativeModel("gemini-2.0-flash")
                    test_response = test_model.generate_content("Hello")
                    
                    if test_response:
                        self.api_key = api_key
                        self._save_api_key()
                        print(self._colorize("✅ API key validated and saved successfully!", 'bright_green'))
                        self.model = test_model
                        break
                    else:
                        print(self._colorize("❌ Invalid API key. Please check and try again.", 'red'))
                        
                except Exception as e:
                    print(self._colorize(f"❌ API key validation failed: {str(e)}", 'red'))
                    print(self._colorize("Please check your API key and try again.", 'yellow'))
                    
            except KeyboardInterrupt:
                print(f"\n{self._colorize('❌ Setup cancelled. Commandor requires an API key to function.', 'red')}")
                exit(1)

    def _save_api_key(self):
        """Save API key to .env file."""
        try:
            with open(self.env_file, 'w') as f:
                f.write(f'GEMINI={self.api_key}\n')
            
            # Set file permissions to be readable only by owner
            if os.name != 'nt':  # Not Windows
                os.chmod(self.env_file, 0o600)
                
        except Exception as e:
            print(f"Warning: Could not save API key: {e}")

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
        history_file = self.config_dir / 'history'
        
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
            atexit.register(lambda: self._save_history(history_file))
            
        except Exception as e:
            print(f"Warning: Could not setup readline: {e}")

    def _save_history(self, history_file):
        """Save command history to file."""
        try:
            readline.write_history_file(str(history_file))
        except Exception as e:
            print(f"Warning: Could not save history: {e}")

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text."""
        try:
            if hasattr(self, 'colors') and self.colors:
                return f"{self.colors.get(color, '')}{text}{self.colors['reset']}"
            else:
                return text
        except Exception:
            return text

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
        
        recent = self.command_history[-3:]
        return "Recent commands:\n" + "\n".join([f"  {cmd}" for cmd in recent]) + "\n"

    def get_ai_command(self, instruction: str) -> str:
        """Convert natural language instruction to shell command using AI."""
        if not self.api_key or not self.model:
            return "# Error: No API key configured or model not initialized"
        
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
            
            if command.startswith('```'):
                lines = command.split('\n')
                command = '\n'.join(lines[1:-1]) if len(lines) > 2 else lines[1]
            
            return command.strip()
        except Exception as e:
            return f"# Error getting AI response: {e}"

    def ask_ai(self, question: str) -> str:
        """Ask AI a general question (not command-related)."""
        if not self.api_key or not self.model:
            return "Error: No API key configured or model not initialized"
        
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
            if command.strip().startswith('cd '):
                return self._handle_cd_command(command)
            
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.current_dir),
                capture_output=True,
                text=True,
                timeout=30
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
            target = Path.home()
        else:
            path = parts[1].strip('\'"')
            target = Path(path)
            
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
        
        # Create a shortened path similar to the screenshot
        if len(str(self.current_dir)) > 30:
            # Show pattern like [.../projects/Commandor]
            parts = self.current_dir.parts
            if len(parts) > 2:
                dir_display = f"[.../{'/'.join(parts[-2:])}]"
            else:
                dir_display = f"[{dir_name}]"
        else:
            dir_display = f"[{self.current_dir}]"
        
        return f"{self._colorize('Commandor', 'bright_cyan')} {self._colorize(dir_display, 'blue')} {self._colorize('# ', 'bright_yellow')}"

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
        {self._colorize('/config', 'yellow')}           - Show configuration info
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

    def show_config(self):
        """Display configuration information."""
        config_text = f"""
        {self._colorize('⚙️  Configuration', 'bold')}
        {self._colorize('=' * 25, 'bright_blue')}
        {self._colorize('Config Directory:', 'bright_cyan')} {self.config_dir}
        {self._colorize('API Key Status:', 'bright_cyan')} {'✅ Configured' if self.api_key else '❌ Not configured'}
        {self._colorize('Model Status:', 'bright_cyan')} {'✅ Initialized' if self.model else '❌ Not initialized'}
        {self._colorize('Readline Support:', 'bright_cyan')} {'✅ Available' if READLINE_AVAILABLE else '❌ Not available'}
        """
        print(config_text)

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
        if command and command not in ['exit', '/help', '/info', '/history', '/clear', '/config']:
            self.command_history.append(command)
            if len(self.command_history) > self.max_history:
                self.command_history.pop(0)
            
            if READLINE_AVAILABLE:
                readline.add_history(command)

    def get_input(self, prompt: str) -> str:
        """Get user input with proper readline support."""
        try:
            return input(prompt).strip()
        except EOFError:
            raise KeyboardInterrupt

    def run(self):
        """Main terminal loop."""
        if not self.api_key or not self.model:
            print(self._colorize("❌ Cannot start Commandor without API key or model initialization.", 'red'))
            return
        
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
                
                if user_input == 'exit':
                    break
                elif user_input == '/help':
                    self.show_help()
                    continue
                elif user_input == '/info':
                    self.show_info()
                    continue
                elif user_input == '/config':
                    self.show_config()
                    continue
                elif user_input == '/history':
                    self.show_history()
                    continue
                elif user_input == '/clear':
                    os.system('clear' if os.name != 'nt' else 'cls')
                    continue
                
                elif user_input.startswith('/ask '):
                    question = user_input[5:].strip()
                    if not question:
                        print(self._colorize("❓ Please provide a question after /ask", 'yellow'))
                        continue
                    
                    print(self._colorize("🤔 Thinking...", 'yellow'), flush=True)
                    ai_response = self.ask_ai(question)
                    print(f"\n{self._colorize('🤖 AI Response:', 'bright_green')}")
                    print(f"{self._colorize('─' * 50, 'blue')}")
                    print(ai_response)
                    print(f"{self._colorize('─' * 50, 'blue')}\n")
                    self.add_to_history(f"/ask {question}")
                    continue
                
                elif user_input.startswith('/ai '):
                    instruction = user_input[4:].strip()
                    if not instruction:
                        print(self._colorize("💡 Please provide an instruction after /ai", 'yellow'))
                        continue
                    
                    print(self._colorize("🧠 Generating command...", 'yellow'), flush=True)
                    ai_command = self.get_ai_command(instruction)
                    print(f"{self._colorize('🤖 AI →', 'bright_green')} {self._colorize(ai_command, 'bright_blue')}")
                    
                    dangerous_patterns = ['rm -rf', 'sudo rm', 'format', 'mkfs', '> /dev/', 'dd if=']
                    if any(pattern in ai_command.lower() for pattern in dangerous_patterns):
                        confirm = self.get_input(self._colorize("⚠️  This command looks dangerous. Execute? (y/N): ", 'bright_yellow'))
                        if confirm.lower() != 'y':
                            print(self._colorize("❌ Command cancelled", 'yellow'))
                            continue
                    
                    success, stdout, stderr = self.execute_command(ai_command)
                    self.display_output(success, stdout, stderr)
                    self.add_to_history(f"/ai {instruction} → {ai_command}")
                
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
                print(f"💥 Unexpected error: {e}")
                # Add some debugging info
                import traceback
                print(f"Error details: {traceback.format_exc()}")

def main():
    """Entry point for the commandor package."""
    try:
        terminal = AITerminal()
        terminal.run()
    except Exception as e:
        print(f"❌ Error starting Commandor: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()