"""
AI Terminal - Main Terminal Interface
Handles the primary terminal interface and user interaction.
"""

import os
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.completion import WordCompleter

from command_processor import CommandProcessor
from ai_assistant import AIAssistant
from command_executor import CommandExecutor
from utils import Colors, clear_screen


class AITerminal:
    """Main terminal interface class."""
    
    def __init__(self):
        # Initialize components
        self.command_processor = CommandProcessor()
        self.ai_assistant = AIAssistant()
        self.command_executor = CommandExecutor()
        
        # Initialize the shell prompt session with command completion
        common_commands = ['/ai', '/ask', 'exit', 'help', 'clear', 'dir', 'cd', 'mkdir', 'rmdir', 'copy', 'del']
        completer = WordCompleter(common_commands, ignore_case=True)
        self.session = PromptSession(
            history=FileHistory(".ai_terminal_history"),
            completer=completer
        )
    
    def show_welcome(self):
        """Display welcome message."""
        print(f"{Colors.CYAN}🤖 Welcome to AI Terminal!{Colors.RESET}")
        print(f"{Colors.GREEN}Type '/ai <your request>' for natural language commands{Colors.RESET}")
        print(f"{Colors.GREEN}Type '/ask <question>' for general AI conversation{Colors.RESET}")
        print(f"{Colors.YELLOW}Type 'help' for assistance, 'exit' to quit{Colors.RESET}")
    
    def show_help(self):
        """Display help information."""
        help_text = f"""
{Colors.CYAN}AI Terminal Help:{Colors.RESET}
{Colors.CYAN}================{Colors.RESET}
{Colors.GREEN}/ai <instruction>{Colors.RESET}  - Convert natural language to command
{Colors.GREEN}/ask <question>{Colors.RESET}    - Ask AI anything (general conversation)
{Colors.GREEN}/ai help{Colors.RESET}          - Show AI command examples
{Colors.GREEN}/ask help{Colors.RESET}         - Show conversation examples
{Colors.GREEN}help{Colors.RESET}              - Show this help
{Colors.GREEN}clear{Colors.RESET}             - Clear the screen
{Colors.GREEN}exit{Colors.RESET}              - Exit the terminal

{Colors.YELLOW}Command Examples:{Colors.RESET}
/ai list all files in current directory
/ai create a new folder called projects
/ai show system information
/ai find all text files containing "python"

{Colors.YELLOW}Conversation Examples:{Colors.RESET}
/ask what is the difference between TCP and UDP?
/ask how do I optimize my Python code?
/ask explain what docker containers are
/ask why is my computer running slowly?
        """
        print(help_text)
    
    def handle_ai_command(self, natural_prompt):
        """Handle /ai commands for natural language to shell command conversion."""
        if natural_prompt.lower() == "help":
            self.ai_assistant.show_ai_help()
            return
        
        if not natural_prompt:
            print(f"{Colors.RED}Please provide an instruction after /ai{Colors.RESET}")
            return
        
        print(f"\n{Colors.BLUE}🔄 Processing: {natural_prompt}{Colors.RESET}")
        shell_cmd = self.ai_assistant.natural_to_command(natural_prompt)
        
        if shell_cmd.startswith("Error"):
            print(f"{Colors.RED}❌ {shell_cmd}{Colors.RESET}")
            return
        
        print(f"{Colors.CYAN}🤖 AI → {shell_cmd}{Colors.RESET}")
        
        # Safety check
        is_safe, warning = self.command_processor.is_safe_command(shell_cmd)
        if not is_safe:
            print(f"{Colors.YELLOW}⚠️  Warning: {warning}{Colors.RESET}")
            if not (input("Do you want to proceed anyway? [y/N]: ").strip().lower() in ['y', 'yes']):
                print(f"{Colors.YELLOW}Command cancelled for safety.{Colors.RESET}")
                return
        
        # Confirm execution
        confirm_response = input("Run this command? [Y/n]: ").strip().lower()
        if confirm_response in ['y', 'yes', '']:
            out, err = self.command_executor.run_command(shell_cmd)
            if out:
                print(f"\n{Colors.GREEN}✅ Output:{Colors.RESET}\n{out}")
            if err:
                print(f"\n{Colors.RED}❌ Error:{Colors.RESET}\n{err}")
        else:
            print(f"{Colors.YELLOW}Command skipped.{Colors.RESET}")
    
    def handle_ask_command(self, question):
        """Handle /ask commands for AI conversation."""
        if question.lower() == "help":
            self.ai_assistant.show_ask_help()
            return
        
        if not question:
            print(f"{Colors.RED}Please ask a question after /ask{Colors.RESET}")
            return
        
        print(f"\n{Colors.BLUE}💭 Thinking about: {question}{Colors.RESET}")
        answer = self.ai_assistant.ask_ai(question)
        
        if answer.startswith("Error"):
            print(f"{Colors.RED}❌ {answer}{Colors.RESET}")
        else:
            print(f"\n{Colors.CYAN}🤖 AI: {answer}{Colors.RESET}")
            print()  # Extra line for readability
    
    def handle_direct_command(self, user_input):
        """Handle direct command execution."""
        out, err = self.command_executor.run_command(user_input)
        if out:
            print(f"\n{out}")
        if err:
            print(f"\n{Colors.RED}Error:{Colors.RESET}\n{err}")
    
    def run(self):
        """Main terminal loop."""
        self.show_welcome()
        
        try:
            with patch_stdout():
                while True:
                    try:
                        user_input = self.session.prompt(
                            ANSI(f"\x1b[1;32mAI-Terminal> \x1b[0m")
                        )
                        
                        if not user_input.strip():
                            continue
                        
                        # Handle built-in commands
                        if user_input.strip().lower() == "exit":
                            break
                        elif user_input.strip().lower() == "help":
                            self.show_help()
                            continue
                        elif user_input.strip().lower() == "clear":
                            clear_screen()
                            continue
                        
                        # Handle AI commands
                        if user_input.startswith("/ai"):
                            natural_prompt = user_input[3:].strip()
                            self.handle_ai_command(natural_prompt)
                        elif user_input.startswith("/ask"):
                            question = user_input[4:].strip()
                            self.handle_ask_command(question)
                        else:
                            # Direct command execution
                            self.handle_direct_command(user_input)

                    except (KeyboardInterrupt, EOFError):
                        break
                    except Exception as e:
                        print(f"{Colors.RED}Unexpected error: {e}{Colors.RESET}")

        finally:
            self.ai_assistant.save_command_history()
            print(f"\n{Colors.CYAN}👋 Goodbye!{Colors.RESET}")