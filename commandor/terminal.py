import os
import platform
import re
import shutil
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path
from typing import Optional, Tuple

from google import genai
from google.genai import types

# For Markdown Response Rendering
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

# Import new agent system
from . import config
from .agent import list_modes, run_agent, test_providers
from .api_manager import APIManager
from .session_manager import SessionManager
from .tui import CommandorPrompt


class AITerminal:
    """An intelligent terminal that uses AI to convert natural language to shell commands."""

    def __init__(self):
        # Initialize colors first - this is critical!
        self.colors = {
            "red": "\033[91m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "magenta": "\033[95m",
            "cyan": "\033[96m",
            "white": "\033[97m",
            "reset": "\033[0m",
            "bold": "\033[1m",
            "bright_red": "\033[91m\033[1m",
            "bright_green": "\033[92m\033[1m",
            "bright_yellow": "\033[93m\033[1m",
            "bright_blue": "\033[94m\033[1m",
            "bright_magenta": "\033[95m\033[1m",
            "bright_cyan": "\033[96m\033[1m",
        }

        # Initialize other attributes
        self.api_key = None
        self.session_id = str(uuid.uuid4())
        self.current_dir = Path.cwd()
        self.command_history = []
        self.ask_history = []  # Dedicated history for /ask prompts
        self.max_history = 100
        self.max_ask_history = 50  # Separate limit for ask history
        self.system_info = self._get_system_info()
        self.config_dir = Path.home() / ".commandor"
        self.env_file = self.config_dir / ".env"
        self.ask_history_file = self.config_dir / "ask_history.txt"
        self.model = None  # Initialize model as None

        # Initializing the Rich console
        self.console = Console()

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
                self.gemini_client = genai.Client(api_key=self.api_key)
                self.model = "gemini-2.5-flash"
            except Exception as e:
                print(f"Warning: Could not initialize Gemini model: {e}")
                self.model = None

        # Setup readline if available
        self._setup_readline()

        # Load ask history
        self._load_ask_history()

        # API manager (for /api commands)
        self._api_manager = APIManager()

        # Session manager (for /sessions commands)
        self._session_manager = SessionManager()
        self._session_name: Optional[str] = None  # name of current session, if saved
        self._autosave_declined: bool = False       # don't re-ask if user skipped once

        # prompt_toolkit interactive prompt
        self._prompt = CommandorPrompt(self.config_dir)
        self._prompt.update_session(None, self.session_id)

    def _display_ai_response(self, response: str, title: str = "AI Response"):
        """Display AI response using rich library for better formatting."""

        # Create markdown object
        markdown = Markdown(response)

        # Resolve current provider name for subtitle
        try:
            cfg = config.get_config()
            provider_name = cfg.config.default_provider if cfg.config else "gemini"
        except Exception:
            provider_name = "gemini"
        subtitle = f"Powered by {provider_name.capitalize()}"

        # Create a panel with the markdown content
        panel = Panel(
            markdown,
            title=f"🤖 {title}",
            subtitle=subtitle,
            border_style="cyan",
            padding=(1, 2),
            expand=False,
        )

        self.console.print(panel)

    def reset_api_key(self):
        """Reset and reconfigure the API key."""
        print(self._colorize("🔄 Resetting API key...", "yellow"))
        self.api_key = None
        self.model = None
        self._prompt_for_api_key()

    def test_api_key(self) -> bool:
        """Test if the current API key is valid."""
        if not self.api_key:
            print(self._colorize("❌ No API key configured", "red"))
            return False

        try:
            print(self._colorize("🔍 Testing API key...", "yellow"))
            client = genai.Client(api_key=self.api_key)
            test_response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=["Hello"],
                config=types.GenerateContentConfig(max_output_tokens=10),
            )
            return test_response is not None
        except Exception as e:
            print(self._colorize(f"❌ API key test failed: {str(e)}", "red"))
            return False

    def handle_api_error(self, error_message: str) -> bool:
        """Handle API errors and offer to reset API key."""
        print(self._colorize(f"❌ API Error: {error_message}", "red"))

        # Check if it's likely an API key issue
        api_error_keywords = [
            "api key",
            "authentication",
            "unauthorized",
            "forbidden",
            "invalid",
            "quota",
            "exceeded",
        ]
        if any(keyword in error_message.lower() for keyword in api_error_keywords):
            print(self._colorize("🔍 This looks like an API key issue.", "yellow"))

            response = self.get_input(
                self._colorize(
                    "Would you like to reset your API key? (y/N): ", "bright_cyan"
                )
            )
            if response.lower() == "y":
                self.reset_api_key()
                return True

        return False

    def ask_ai(self, question: str) -> str:
        """Ask AI a general question (not command-related) - Enhanced for rich markdown."""

        if not self.api_key or not self.model:
            return "Error: No API key configured or model not initialized"

        context = self._get_directory_context()

        prompt = textwrap.dedent(f"""You are a helpful AI assistant. Answer the user's question with rich markdown formatting.

        Use these markdown features extensively:
        - # Main headings and ## Subheadings
        - **Bold text** for key concepts
        - *Italic text* for emphasis
        - `inline code` for technical terms
        - ```language
          code blocks with syntax highlighting
          ```
        - > Blockquotes for important information
        - - Bullet points for lists
        - 1. Numbered lists for steps
        - [Links](https://example.com) when relevant
        - Tables when appropriate

        SYSTEM CONTEXT (for reference only):
        - OS: {self.system_info["os"]}
        - Current Directory: {self.current_dir}

        QUESTION: "{question}"

        Provide a comprehensive, well-structured answer with excellent markdown formatting.""")

        try:
            response = self.gemini_client.models.generate_content(
                model=self.model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    system_instruction="You are a helpful AI assistant."
                ),
            )
            return response.text.strip() if response.text else ""
        except Exception as e:
            error_msg = str(e)
            if self.handle_api_error(error_msg):
                return self.ask_ai(question)
            return f"Sorry, I couldn't process your question: {error_msg}"

    def _setup_api_key(self):
        """Setup Gemini API key with interactive prompt if needed."""
        # Try to load from .env file first
        if self.env_file.exists():
            try:
                with open(self.env_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI="):
                            self.api_key = line.split("=", 1)[1].strip().strip("\"'")
                            break
            except Exception as e:
                print(f"Warning: Could not read .env file: {e}")

        # If no API key found, prompt user
        if not self.api_key:
            self._prompt_for_api_key()

    def _prompt_for_api_key(self):
        """Prompt user for Gemini API key and save it."""
        print(self._colorize("🔑 Gemini API Key Setup Required", "bright_yellow"))
        print(self._colorize("=" * 45, "bright_blue"))
        print("To use Commandor, you need a Gemini API key.")
        print("You can get one free at: https://makersuite.google.com/app/apikey")
        print()

        while True:
            try:
                api_key = input(
                    self._colorize("Please enter your Gemini API key: ", "bright_cyan")
                ).strip()

                if not api_key:
                    print(
                        self._colorize(
                            "❌ API key cannot be empty. Please try again.", "red"
                        )
                    )
                    continue

                # Test the API key
                print(self._colorize("🔍 Validating API key...", "yellow"))

                try:
                    client = genai.Client(api_key=api_key)
                    test_response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=["Hello"],
                        config=types.GenerateContentConfig(max_output_tokens=10),
                    )

                    if test_response:
                        self.api_key = api_key
                        self._save_api_key()
                        print(
                            self._colorize(
                                "✅ API key validated and saved successfully!",
                                "bright_green",
                            )
                        )
                        self.gemini_client = client
                        self.model = "gemini-2.5-flash"
                        break
                    else:
                        print(
                            self._colorize(
                                "❌ Invalid API key. Please check and try again.", "red"
                            )
                        )

                except Exception as e:
                    print(
                        self._colorize(f"❌ API key validation failed: {str(e)}", "red")
                    )
                    print(
                        self._colorize(
                            "Please check your API key and try again.", "yellow"
                        )
                    )

            except KeyboardInterrupt:
                print(
                    f"\n{self._colorize('❌ Setup cancelled. Commandor requires an API key to function.', 'red')}"
                )
                exit(1)

    def _save_api_key(self):
        """Save API key to .env file."""
        try:
            with open(self.env_file, "w") as f:
                f.write(f"GEMINI={self.api_key}\n")

            # Set file permissions to be readable only by owner
            if os.name != "nt":  # Not Windows
                os.chmod(self.env_file, 0o600)

        except Exception as e:
            print(f"Warning: Could not save API key: {e}")

    def _get_system_info(self) -> dict:
        """Gather system information for better context."""
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "shell": os.environ.get("SHELL", "unknown"),
            "user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
        }

    def _setup_readline(self):
        """No-op: readline replaced by prompt_toolkit (CommandorPrompt)."""

    def _save_history(self, history_file):
        """No-op: history is managed by prompt_toolkit FileHistory."""

    def _load_ask_history(self):
        """Load ask prompt history from file."""
        try:
            if self.ask_history_file.exists():
                with open(self.ask_history_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self.ask_history.append(line)
        except Exception as e:
            print(f"Warning: Could not load ask history: {e}")

    def _save_ask_history(self):
        """Save ask prompt history to file."""
        try:
            with open(self.ask_history_file, "w", encoding="utf-8") as f:
                for prompt in self.ask_history:
                    f.write(f"{prompt}\n")
        except Exception as e:
            print(f"Warning: Could not save ask history: {e}")

    def show_ask_history(self):
        """Display ask prompt history."""
        if not self.ask_history:
            print(self._colorize("🤔 No ask history available", "yellow"))
            return

        print(
            self._colorize(f"📝 Ask History ({len(self.ask_history)} total):", "bold")
        )
        print(self._colorize("-" * 40, "bright_magenta"))
        for i, prompt in enumerate(self.ask_history[-15:], 1):
            # Truncate long prompts for display
            display_prompt = prompt if len(prompt) <= 60 else prompt[:57] + "..."
            print(f"{self._colorize(f'{i:2d}.', 'bright_cyan')} {display_prompt}")

        if len(self.ask_history) > 15:
            print(
                f"{self._colorize(f'... and {len(self.ask_history) - 15} more', 'yellow')}"
            )

        print(
            f"\n{self._colorize('💡 Tip:', 'bright_yellow')} Use '/ask-search <term>' to search your ask history"
        )

    def search_ask_history(self, search_term: str):
        """Search ask history for a specific term."""
        if not self.ask_history:
            print(self._colorize("🤔 No ask history to search", "yellow"))
            return

        search_term_lower = search_term.lower()
        matches = []

        for i, prompt in enumerate(self.ask_history):
            if search_term_lower in prompt.lower():
                matches.append((i + 1, prompt))

        if not matches:
            print(self._colorize(f"🔍 No matches found for '{search_term}'", "yellow"))
            return

        print(
            self._colorize(
                f"🔍 Found {len(matches)} match(es) for '{search_term}':", "bold"
            )
        )
        print(self._colorize("-" * 50, "bright_green"))
        for index, prompt in matches:
            # Highlight the search term in the result
            highlighted_prompt = prompt.replace(
                search_term, self._colorize(search_term, "bright_yellow")
            )
            print(
                f"{self._colorize(f'{index:2d}.', 'bright_cyan')} {highlighted_prompt}"
            )

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text."""
        try:
            if hasattr(self, "colors") and self.colors:
                return f"{self.colors.get(color, '')}{text}{self.colors['reset']}"
            else:
                return text
        except Exception:
            return text

    def _display_colorful_logo(self):
        """Display clean startup banner."""
        try:
            cfg = config.get_config()
            provider_name = cfg.config.default_provider if cfg.config else "gemini"
        except Exception:
            provider_name = "gemini"

        self.console.print()
        self.console.print(
            f"  [bold purple]◆[/bold purple]  [bold]Commandor[/bold]  [dim]— AI-powered terminal[/dim]"
        )
        self.console.print()
        self.console.print(
            f"  [dim]provider:[/dim] [cyan]{provider_name}[/cyan]"
            f"  [dim]·  type [bold]/help[/bold] for commands  ·  Ctrl+C to exit[/dim]"
        )
        self.console.print()

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
        - OS: {self.system_info["os"]} {self.system_info["os_version"]}
        - Architecture: {self.system_info["architecture"]}
        - Shell: {self.system_info["shell"]}
        - User: {self.system_info["user"]}

        CURRENT CONTEXT:
        {context}

        {recent_commands}

        INSTRUCTION: "{instruction}"

        RULES:
        1. Reply with ONLY the shell command, no explanations
        2. Use commands appropriate for {self.system_info["os"]}
        3. Consider the current directory context
        4. Use safe commands (avoid destructive operations without explicit confirmation)
        5. For file operations, use relative paths when possible
        6. If the instruction is ambiguous, choose the most common interpretation

        Command:"""

        try:
            response = self.gemini_client.models.generate_content(
                model=self.model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    system_instruction="You are an expert system administrator helping convert natural language to shell commands."
                ),
            )
            command = response.text.strip() if response.text else ""

            if command.startswith("```"):
                lines = command.split("\n")
                command = "\n".join(lines[1:-1]) if len(lines) > 2 else lines[1]

            return command.strip()
        except Exception as e:
            error_msg = str(e)
            if self.handle_api_error(error_msg):
                # API key was reset, try again
                return self.get_ai_command(instruction)
            return f"# Error getting AI response: {error_msg}"

    def execute_command(self, command: str) -> Tuple[bool, str, str]:
        """Execute a shell command and return success status and output."""
        try:
            if command.strip().startswith("cd "):
                return self._handle_cd_command(command)

            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.current_dir),
                capture_output=True,
                text=True,
                timeout=30,
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
            path = parts[1].strip("'\"")
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
            print(stdout, end="")

        if stderr:
            print(self._colorize(stderr, "red"), end="")

        if not success and not stderr:
            print(self._colorize("Command failed", "red"))

        # Always add newline after any command output to ensure prompt appears on new line
        # This prevents text overlapping issues when the next prompt is displayed
        print()

    def _expand_at_references(self, text: str) -> str:
        """Replace ``@filepath`` tokens with inlined file-content blocks.

        For example, ``/agent review @src/main.py`` becomes:

            /agent review
            <file path="src/main.py" lines="42">
            ...file contents...
            </file>

        Paths are resolved relative to the current working directory.
        Supports ``~`` expansion and absolute paths.
        """
        import re

        def _replace(match: re.Match) -> str:  # type: ignore[type-arg]
            raw = match.group(1)
            p = Path(raw).expanduser()
            if not p.is_absolute():
                p = self.current_dir / p
            try:
                content = p.read_text(encoding="utf-8")
                line_count = content.count("\n") + (0 if content.endswith("\n") else 1)
                return (
                    f'\n<file path="{raw}" lines="{line_count}">\n'
                    f"{content}\n</file>"
                )
            except Exception as exc:
                return f"@{raw}  [could not read: {exc}]"

        # Match @word, @path/to/file.py, @./relative, @~/home-rel, @/absolute
        # Don't match inside email-style tokens (preceded by alnum)
        return re.sub(r"(?<![A-Za-z0-9])@([\w./~-]+)", _replace, text)

    def get_prompt(self) -> str:
        """Generate the terminal prompt: dim path + bold purple ❯"""
        try:
            home = str(Path.home())
            cwd = str(self.current_dir)
            if cwd.startswith(home):
                cwd = "~" + cwd[len(home):]
        except Exception:
            cwd = str(self.current_dir)

        # ANSI: dim (2m) for path, reset, bold purple (1;35m) for ❯, reset
        DIM    = "\033[2m"
        RESET  = "\033[0m"
        BOLD_PURPLE = "\033[1;35m"

        return f"  {DIM}{cwd}{RESET} {BOLD_PURPLE}❯{RESET} "

    def show_help(self):
        """Display help information using Rich tables."""
        console = Console()

        def _section(title: str, rows: list[tuple[str, str]]) -> Table:
            t = Table(show_header=False, box=None, padding=(0, 2), expand=False)
            t.add_column("command", style="cyan", no_wrap=True)
            t.add_column("description", style="white")
            for cmd, desc in rows:
                t.add_row(cmd, desc)
            return t

        console.print()
        console.print(Panel(
            "[bold cyan]Commandor[/bold cyan]  —  AI-powered terminal",
            border_style="cyan",
            padding=(0, 2),
            expand=False,
        ))

        console.print("\n[bold green]Agent Commands[/bold green]")
        console.print(_section("agent", [
            ("/agent <task>",   "Run fully autonomous agent"),
            ("/assist <task>",  "Run with per-tool confirmations"),
            ("/plan <task>",    "Generate plan, review, then execute"),
            ("/chat <question>","Conversational AI (no tools)"),
        ]))

        console.print("\n[bold green]Traditional Commands[/bold green]")
        console.print(_section("traditional", [
            ("/ai <instruction>",  "Convert natural language to shell command"),
            ("/ask <question>",    "Ask AI a general question"),
            ("/help",              "Show this help"),
            ("/info",              "Show system information"),
            ("/history",           "Show recent command history"),
            ("/ask-history",       "Show question history"),
            ("/ask-search <term>", "Search question history"),
            ("/clear",             "Clear the screen"),
            ("/config",            "Show configuration info"),
            ("/reset-api",         "Reset and reconfigure API key"),
            ("/test-api",          "Test current API key"),
        ]))

        console.print("\n[bold green]Provider Commands[/bold green]")
        console.print(_section("providers", [
            ("/provider <name>",  "Switch AI provider"),
            ("/providers",        "List available providers"),
            ("/modes",            "Show agent modes"),
        ]))

        console.print("\n[bold green]API Management[/bold green]")
        console.print(_section("api", [
            ("/api",                         "Show API key status table"),
            ("/api set <provider> <key>",     "Set API key for a provider"),
            ("/api model <provider> <model>", "Set default model for a provider"),
            ("/api test [provider]",          "Test one or all providers"),
            ("/api remove <provider>",        "Remove a provider's API key"),
            ("/api default <provider>",       "Set default provider"),
            ("/test-providers",               "Quick test of all providers"),
        ]))

        console.print("\n[bold green]Session Management[/bold green]")
        console.print(_section("sessions", [
            ("/sessions",                      "List saved sessions"),
            ("/sessions save <name>",          "Name the current session"),
            ("/sessions new <name>",           "Start a fresh named session"),
            ("/sessions resume <name>",        "Switch to a saved session"),
            ("/sessions rename <old> <new>",   "Rename a session"),
            ("/sessions delete <name>",        "Delete a session"),
        ]))

        console.print(
            "\n[dim]exit[/dim] or [dim]Ctrl+C[/dim] to quit  ·  "
            "[dim]Regular shell commands work too[/dim]\n"
        )

    def _maybe_autosave_session(self, task: str) -> None:
        """Before the first run of an unsaved session, offer to save with an AI-generated name.

        - Makes a quick LLM call to produce a 2–4 word kebab-case slug.
        - Prompts: Save session as "<slug>"? [Enter=yes / type to rename / n=skip]:
        - On confirm/rename: saves + updates toolbar.
        - On 'n': sets self._autosave_declined so we don't ask again this session.
        """
        if self._session_name is not None or self._autosave_declined:
            return

        # Generate a slug via a quick LLM call
        try:
            from .agent.executor import _resolve_provider_model  # noqa: PLC0415
            from .agent.lc_models import build_model              # noqa: PLC0415
            from langchain_core.messages import HumanMessage      # noqa: PLC0415

            _, api_key, resolved_model = _resolve_provider_model(None, None)
            cfg_obj = config.get_config()
            provider_name = cfg_obj.config.default_provider if cfg_obj.config else "gemini"
            llm = build_model(provider_name, api_key, resolved_model)
            prompt = (
                "Generate a 2-4 word kebab-case session name for this task. "
                "Reply with ONLY the slug, no explanation, no punctuation.\n\n"
                f"Task: {task[:200]}"
            )
            resp = llm.invoke([HumanMessage(content=prompt)])
            raw_content = resp.content if hasattr(resp, "content") else str(resp)
            if isinstance(raw_content, list):
                raw_content = " ".join(
                    b.get("text", "") if isinstance(b, dict) else str(b)
                    for b in raw_content
                )
            raw = str(raw_content)
            # Sanitize: keep only alphanumeric + hyphens, collapse multiple hyphens
            slug = re.sub(r"[^a-z0-9-]", "-", raw.strip().lower())
            slug = re.sub(r"-+", "-", slug).strip("-")[:40]
            if not slug:
                return
        except Exception:
            return  # If LLM fails, silently skip autosave

        try:
            answer = input(
                f'  Save session as "{slug}"? [Enter=yes / type to rename / n=skip]: '
            ).strip()
        except (KeyboardInterrupt, EOFError):
            self._autosave_declined = True
            return

        if answer.lower() == "n":
            self._autosave_declined = True
            return

        # Use provided rename if non-empty, otherwise use slug
        final_name = answer if answer and answer.lower() != "n" else slug
        # Sanitize custom name too
        final_name = re.sub(r"[^a-z0-9_-]", "-", final_name.lower()).strip("-")[:40]
        if not final_name:
            final_name = slug

        self._session_manager.save_session(final_name, self.session_id)
        self._session_name = final_name
        self._prompt.update_session(final_name, session_id=self.session_id)

    def show_info(self):
        """Display system information."""
        info_text = f"""
        {self._colorize("🖥️  System Information", "bold")}
        {self._colorize("=" * 35, "bright_blue")}
        {self._colorize("OS:", "bright_cyan")} {self.system_info["os"]} {self.system_info["os_version"]}
        {self._colorize("Architecture:", "bright_cyan")} {self.system_info["architecture"]}
        {self._colorize("Python:", "bright_cyan")} {self.system_info["python_version"]}
        {self._colorize("Shell:", "bright_cyan")} {self.system_info["shell"]}
        {self._colorize("User:", "bright_cyan")} {self.system_info["user"]}
        {self._colorize("Current Directory:", "bright_cyan")} {self.current_dir}
        """
        print(info_text)

    def show_config(self):
        """Display configuration information."""
        config_text = f"""
        {self._colorize("⚙️  Configuration", "bold")}
        {self._colorize("=" * 25, "bright_blue")}
        {self._colorize("Config Directory:", "bright_cyan")} {self.config_dir}
        {self._colorize("API Key Status:", "bright_cyan")} {"✅ Configured" if self.api_key else "❌ Not configured"}
        {self._colorize("Model Status:", "bright_cyan")} {"✅ Initialized" if self.model else "❌ Not initialized"}
        {self._colorize("Input Mode:", "bright_cyan")} ✅ prompt_toolkit
        {self._colorize("API Key File:", "bright_cyan")} {self.env_file}
        {self._colorize("Ask History File:", "bright_cyan")} {self.ask_history_file}
        """
        print(config_text)

    def show_history(self):
        """Display recent command history."""
        if not self.command_history:
            print(self._colorize("📝 No command history available", "yellow"))
            return

        print(self._colorize("📚 Recent Commands:", "bold"))
        print(self._colorize("-" * 25, "bright_blue"))
        for i, cmd in enumerate(self.command_history[-10:], 1):
            print(f"{self._colorize(f'{i:2d}.', 'bright_cyan')} {cmd}")

    def add_to_history(self, command: str):
        """Add command to history."""
        if command and command not in [
            "exit",
            "/help",
            "/info",
            "/history",
            "/clear",
            "/config",
            "/ask-history",
            "/reset-api",
            "/test-api",
        ]:
            self.command_history.append(command)
            if len(self.command_history) > self.max_history:
                self.command_history.pop(0)

    def add_to_ask_history(self, prompt: str):
        """Add ask prompt to ask history."""
        if prompt and prompt.strip():
            # Avoid duplicates if the same question was asked recently
            if not self.ask_history or self.ask_history[-1] != prompt:
                self.ask_history.append(prompt)
                if len(self.ask_history) > self.max_ask_history:
                    self.ask_history.pop(0)
                # Save to file immediately for persistence
                self._save_ask_history()

    def get_input(self, prompt: str) -> str:
        """Get user input with proper readline support and line wrapping prevention."""
        try:
            # Get input normally - the real fix is ensuring clean line termination elsewhere
            user_input = input(prompt).strip()
            return user_input
        except EOFError:
            raise KeyboardInterrupt

    def run(self):
        """Main terminal loop."""
        if not self.api_key or not self.model:
            print(
                self._colorize(
                    "❌ Cannot start Commandor without API key or model initialization.",
                    "red",
                )
            )
            return

        self._display_colorful_logo()

        while True:
            try:
                user_input = self._prompt.get_input(self.get_prompt())

                if not user_input:
                    continue

                if user_input == "exit":
                    break
                elif user_input == "/help":
                    self.show_help()
                    continue
                elif user_input == "/info":
                    self.show_info()
                    continue
                elif user_input == "/config":
                    self.show_config()
                    continue
                elif user_input == "/history":
                    self.show_history()
                    continue
                elif user_input == "/ask-history":
                    self.show_ask_history()
                    continue
                elif user_input.startswith("/ask-search "):
                    search_term = user_input[12:].strip()
                    if not search_term:
                        print(
                            self._colorize(
                                "🔍 Please provide a search term after /ask-search",
                                "yellow",
                            )
                        )
                        continue
                    self.search_ask_history(search_term)
                    continue
                elif user_input == "/clear":
                    os.system("clear" if os.name != "nt" else "cls")
                    continue
                elif user_input == "/reset-api":
                    self.reset_api_key()
                    continue
                elif user_input == "/test-api":
                    if self.test_api_key():
                        print(
                            self._colorize(
                                "✅ API key is working correctly!", "bright_green"
                            )
                        )
                    else:
                        print(self._colorize("❌ API key test failed", "red"))
                    continue

                elif user_input.startswith("/ask "):
                    question = user_input[5:].strip()
                    if not question:
                        print(
                            self._colorize(
                                "❓ Please provide a question after /ask", "yellow"
                            )
                        )
                        continue

                    # Check if API key and model are still valid
                    if not self.api_key or not self.model:
                        print(
                            self._colorize(
                                "❌ API key or model not available. Use /reset-api to reconfigure.",
                                "red",
                            )
                        )
                        continue

                    # Add question to ask history before processing
                    self.add_to_ask_history(question)

                    print(self._colorize("🤔 Thinking...", "yellow"), flush=True)
                    ai_response = self.ask_ai(question)

                    # Check if there was an API error that couldn't be resolved
                    if ai_response.startswith("Error:") or ai_response.startswith(
                        "Sorry,"
                    ):
                        print(self._colorize(ai_response, "red"))
                    else:
                        # Use the enhanced display instead of simple print
                        self._display_ai_response(ai_response, "AI Response")

                    self.add_to_history(f"/ask {question}")
                    continue

                elif user_input.startswith("/ai "):
                    instruction = user_input[4:].strip()
                    if not instruction:
                        print(
                            self._colorize(
                                "💡 Please provide an instruction after /ai", "yellow"
                            )
                        )
                        continue

                    # Check if API key and model are still valid
                    if not self.api_key or not self.model:
                        print(
                            self._colorize(
                                "❌ API key or model not available. Use /reset-api to reconfigure.",
                                "red",
                            )
                        )
                        continue

                    print(
                        self._colorize("🧠 Generating command...", "yellow"), flush=True
                    )
                    ai_command = self.get_ai_command(instruction)

                    # Check if there was an API error
                    if ai_command.startswith("# Error"):
                        print(self._colorize(ai_command, "red"))
                        continue

                    print(
                        f"{self._colorize('🤖 AI →', 'bright_green')} {self._colorize(ai_command, 'bright_blue')}"
                    )

                    # Safety check for dangerous commands
                    dangerous_patterns = [
                        "rm -rf",
                        "sudo rm",
                        "format",
                        "mkfs",
                        "> /dev/",
                        "dd if=",
                    ]
                    if any(
                        pattern in ai_command.lower() for pattern in dangerous_patterns
                    ):
                        confirm = self.get_input(
                            self._colorize(
                                "⚠️  This command looks dangerous. Execute? (y/N): ",
                                "bright_yellow",
                            )
                        )
                        if confirm.lower() != "y":
                            print(self._colorize("❌ Command cancelled", "yellow"))
                            continue

                    success, stdout, stderr = self.execute_command(ai_command)
                    self.display_output(success, stdout, stderr)
                    self.add_to_history(f"/ai {instruction} → {ai_command}")

                elif user_input.startswith("/agent "):
                    task = user_input[7:].strip()
                    if not task:
                        print(
                            self._colorize(
                                "❓ Please provide a task after /agent", "yellow"
                            )
                        )
                        continue

                    self._maybe_autosave_session(task)
                    result = run_agent(
                        self._expand_at_references(task), mode="agent",
                        thread_id=self.session_id,
                        session_name=self._session_name,
                    )

                    if not result.success:
                        print(self._colorize(f"❌ {result.final_answer}", "red"))

                    if result.metrics:
                        self._prompt.update_metrics(**result.metrics)
                    self.add_to_history(f"/agent {task}")
                    if self._session_name:
                        self._session_manager.update_last_used(self._session_name)
                    continue

                elif user_input.startswith("/assist "):
                    task = user_input[8:].strip()
                    if not task:
                        print(
                            self._colorize(
                                "❓ Please provide a task after /assist", "yellow"
                            )
                        )
                        continue

                    self._maybe_autosave_session(task)
                    result = run_agent(
                        self._expand_at_references(task), mode="assist",
                        thread_id=self.session_id,
                        session_name=self._session_name,
                    )

                    if not result.success:
                        print(self._colorize(f"❌ {result.final_answer}", "red"))

                    if result.metrics:
                        self._prompt.update_metrics(**result.metrics)
                    self.add_to_history(f"/assist {task}")
                    if self._session_name:
                        self._session_manager.update_last_used(self._session_name)
                    continue

                elif user_input.startswith("/plan "):
                    task = user_input[6:].strip()
                    if not task:
                        print(
                            self._colorize(
                                "❓ Please provide a task after /plan", "yellow"
                            )
                        )
                        continue

                    self._maybe_autosave_session(task)
                    result = run_agent(
                        self._expand_at_references(task), mode="plan",
                        thread_id=self.session_id,
                        session_name=self._session_name,
                    )

                    if not result.success:
                        print(self._colorize(f"❌ {result.final_answer}", "red"))

                    if result.metrics:
                        self._prompt.update_metrics(**result.metrics)
                    self.add_to_history(f"/plan {task}")
                    if self._session_name:
                        self._session_manager.update_last_used(self._session_name)
                    continue

                elif user_input.startswith("/chat "):
                    question = user_input[6:].strip()
                    if not question:
                        print(
                            self._colorize(
                                "❓ Please provide a question after /chat", "yellow"
                            )
                        )
                        continue

                    self._maybe_autosave_session(question)
                    result = run_agent(
                        self._expand_at_references(question), mode="chat",
                        thread_id=self.session_id,
                        session_name=self._session_name,
                    )

                    if not result.success:
                        print(self._colorize(f"❌ {result.final_answer}", "red"))

                    if result.metrics:
                        self._prompt.update_metrics(**result.metrics)
                    self.add_to_history(f"/chat {question}")
                    if self._session_name:
                        self._session_manager.update_last_used(self._session_name)
                    continue

                elif user_input == "/providers":
                    print(self._colorize("\n📋 Available Providers:", "bold"))
                    cfg = config.get_config()
                    for name in cfg.get_enabled_providers():
                        pconfig = cfg.get_provider_config(name)
                        status = "✅" if pconfig and pconfig.api_key else "❌"
                        model = pconfig.default_model if pconfig else ""
                        print(f"  {status} {name}: {model}")
                    continue

                elif user_input == "/modes":
                    print(self._colorize("\n📋 Agent Modes:", "bold"))
                    modes = list_modes()
                    for name, desc in modes.items():
                        print(f"  • {name}: {desc}")
                    continue

                elif user_input.startswith("/provider "):
                    provider_name = user_input[10:].strip()
                    if not provider_name:
                        print(self._colorize("❓ Please specify a provider", "yellow"))
                        continue

                    cfg = config.get_config()
                    cfg.set_default_provider(provider_name)
                    print(
                        self._colorize(
                            f"✅ Default provider set to: {provider_name}",
                            "bright_green",
                        )
                    )
                    continue

                elif user_input == "/setup":
                    config.setup_interactive()
                    continue

                elif user_input.startswith("/test-providers"):
                    print(self._colorize("\n🔍 Testing providers...", "bright_yellow"))
                    results = test_providers()
                    for name, result in results.items():
                        if result["status"] == "ok":
                            print(
                                self._colorize(f"  ✅ {name}: Working", "bright_green")
                            )
                        elif result["status"] == "no_api_key":
                            print(self._colorize(f"  ⚠️  {name}: No API key", "yellow"))
                        elif result["status"] == "invalid_key":
                            print(
                                self._colorize(f"  ❌ {name}: Invalid API key", "red")
                            )
                        else:
                            print(
                                self._colorize(
                                    f"  ❌ {name}: {result.get('error', 'Unknown error')}",
                                    "red",
                                )
                            )
                    continue

                elif user_input == "/api":
                    self._api_manager.show_status()
                    continue

                elif user_input.startswith("/api set "):
                    parts = user_input[9:].strip().split(maxsplit=1)
                    if len(parts) < 2:
                        print(
                            self._colorize(
                                "Usage: /api set <provider> <key>", "yellow"
                            )
                        )
                        continue
                    self._api_manager.set_key(parts[0], parts[1])
                    continue

                elif user_input.startswith("/api model "):
                    parts = user_input[11:].strip().split(maxsplit=1)
                    if len(parts) < 2:
                        print(
                            self._colorize(
                                "Usage: /api model <provider> <model>", "yellow"
                            )
                        )
                        continue
                    self._api_manager.set_model(parts[0], parts[1])
                    continue

                elif user_input.startswith("/api test"):
                    arg = user_input[9:].strip()
                    if arg:
                        self._api_manager.test_provider(arg)
                    else:
                        self._api_manager.test_all()
                    continue

                elif user_input.startswith("/api remove "):
                    provider = user_input[12:].strip()
                    self._api_manager.remove_key(provider)
                    continue

                elif user_input.startswith("/api default "):
                    provider = user_input[13:].strip()
                    self._api_manager.set_default(provider)
                    continue

                elif user_input == "/sessions":
                    self._session_manager.show_sessions(current_id=self.session_id)
                    continue

                elif user_input.startswith("/sessions save "):
                    name = user_input[15:].strip()
                    if not name:
                        print(self._colorize("Usage: /sessions save <name>", "yellow"))
                        continue
                    self._session_manager.save_session(name, self.session_id)
                    self._session_name = name
                    self._prompt.update_session(name, session_id=self.session_id)
                    continue

                elif user_input.startswith("/sessions new "):
                    name = user_input[14:].strip()
                    if not name:
                        print(self._colorize("Usage: /sessions new <name>", "yellow"))
                        continue
                    new_id = self._session_manager.new_session(name)
                    if new_id:
                        self.session_id = new_id
                        self._session_name = name
                        self._prompt.update_session(name, session_id=self.session_id)
                    continue

                elif user_input.startswith("/sessions resume "):
                    name = user_input[17:].strip()
                    if not name:
                        print(
                            self._colorize("Usage: /sessions resume <name>", "yellow")
                        )
                        continue
                    resumed_id = self._session_manager.resume_session(name)
                    if resumed_id:
                        self.session_id = resumed_id
                        self._session_name = name
                        self._prompt.update_session(name, session_id=self.session_id)
                    continue

                elif user_input.startswith("/sessions rename "):
                    parts = user_input[17:].strip().split(maxsplit=1)
                    if len(parts) < 2:
                        print(
                            self._colorize(
                                "Usage: /sessions rename <old> <new>", "yellow"
                            )
                        )
                        continue
                    self._session_manager.rename_session(parts[0], parts[1])
                    if self._session_name == parts[0]:
                        self._session_name = parts[1]
                        self._prompt.update_session(parts[1], session_id=self.session_id)
                    continue

                elif user_input.startswith("/sessions delete "):
                    name = user_input[17:].strip()
                    if not name:
                        print(
                            self._colorize(
                                "Usage: /sessions delete <name>", "yellow"
                            )
                        )
                        continue
                    self._session_manager.delete_session(
                        name, current_id=self.session_id
                    )
                    continue

                else:
                    # Regular shell command
                    success, stdout, stderr = self.execute_command(user_input)
                    self.display_output(success, stdout, stderr)
                    self.add_to_history(user_input)

            except KeyboardInterrupt:
                print(
                    f"\n{self._colorize('👋 Goodbye! Thanks for using Commandor!', 'bright_green')}"
                )
                break
            except EOFError:
                print(
                    f"\n{self._colorize('👋 Goodbye! Thanks for using Commandor!', 'bright_green')}"
                )
                break
            except Exception as e:
                print(f"💥 Unexpected error: {e}")
                # Add some debugging info
                import traceback

                print(f"Error details: {traceback.format_exc()}")
                # Offer to reset API if it might be an API-related error
                if "api" in str(e).lower() or "model" in str(e).lower():
                    response = self.get_input(
                        self._colorize(
                            "This might be an API issue. Reset API key? (y/N): ",
                            "bright_cyan",
                        )
                    )
                    if response.lower() == "y":
                        self.reset_api_key()
