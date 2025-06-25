import subprocess
import sys
import os
import json
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.completion import WordCompleter
import ollama

class AITerminal:
    def __init__(self):
        # Initialize the shell prompt session with command completion
        common_commands = ['/ai', '/ask', 'exit', 'help', 'clear', 'dir', 'cd', 'mkdir', 'rmdir', 'copy', 'del']
        completer = WordCompleter(common_commands, ignore_case=True)
        self.session = PromptSession(
            history=FileHistory(".ai_terminal_history"),
            completer=completer
        )
        
        # Command history for AI suggestions
        self.command_history = []
        self.load_command_history()
        
        # Conversation history for /ask feature
        self.conversation_history = []
    
    def save_command_history(self):
        """Save command history to file for learning patterns"""
        try:
            with open('.ai_command_history.json', 'w') as f:
                json.dump(self.command_history[-100:], f)  # Keep last 100 commands
        except Exception as e:
            print(f"Warning: Could not save command history: {e}")
    
    def load_command_history(self):
        """Load command history from file"""
        try:
            if os.path.exists('.ai_command_history.json'):
                with open('.ai_command_history.json', 'r') as f:
                    self.command_history = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load command history: {e}")
    
    def get_system_context(self):
        """Get current system context for better command generation"""
        try:
            current_dir = os.getcwd()
            username = os.getenv('USERNAME', 'user')
            return f"Current directory: {current_dir}\nUsername: {username}"
        except:
            return "System context unavailable"
    
    def natural_to_command(self, prompt):
        """Convert natural language to shell command using Ollama"""
        try:
            system_context = self.get_system_context()
            
            # Enhanced prompt with system context and safety guidelines
            full_prompt = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert Windows command-line assistant. Convert natural language instructions to Windows commands.\n"
                        "IMPORTANT SAFETY RULES:\n"
                        "- Never suggest commands that could harm the system (like deleting system files)\n"
                        "- Always use safe, reversible operations when possible\n"
                        "- For file operations, suggest checking first (e.g., 'dir' before 'del')\n"
                        "- Output ONLY the command(s), no explanations or code blocks\n"
                        "- Use multiple lines for complex operations\n"
                        f"SYSTEM CONTEXT:\n{system_context}"
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            response = ollama.chat(model="llama3.2:1b", messages=full_prompt)
            command = response["message"]["content"].strip()

            # Clean up the response
            command = self.clean_command_output(command)
            
            # Store the successful translation
            self.command_history.append({
                "natural": prompt,
                "command": command,
                "timestamp": str(os.times())
            })
            
            return command
        except Exception as e:
            return f"Error generating command: {e}"
    
    def ask_ai(self, question):
        """Have a normal conversation with AI"""
        try:
            # Build conversation context (keep last 10 exchanges)
            messages = []
            
            # Add system context for conversational AI
            messages.append({
                "role": "system",
                "content": (
                    "You are a helpful AI assistant integrated into a command-line terminal. "
                    "You can help with general questions, programming concepts, troubleshooting, "
                    "explanations, and casual conversation. Be concise but informative. "
                    "If the user asks about terminal/command-line related topics, you can be more detailed."
                )
            })
            
            # Add recent conversation history for context
            for exchange in self.conversation_history[-10:]:
                messages.append({"role": "user", "content": exchange["question"]})
                messages.append({"role": "assistant", "content": exchange["answer"]})
            
            # Add current question
            messages.append({"role": "user", "content": question})
            
            response = ollama.chat(model="llama3.2:1b", messages=messages)
            answer = response["message"]["content"].strip()
            
            # Store conversation for context
            self.conversation_history.append({
                "question": question,
                "answer": answer,
                "timestamp": str(os.times())
            })
            
            # Keep conversation history manageable
            if len(self.conversation_history) > 50:
                self.conversation_history = self.conversation_history[-25:]
            
            return answer
        except Exception as e:
            return f"Error in conversation: {e}"
    
    def clean_command_output(self, command):
        """Clean up command output from potential markdown or explanations"""
        lines = command.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip empty lines and markdown code blocks
            if not line or line.startswith('```') or line.startswith('#'):
                continue
            # Remove common prefixes that might be added
            if line.startswith('Command: '):
                line = line[9:]
            elif line.startswith('> '):
                line = line[2:]
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def is_safe_command(self, command):
        """Basic safety check for potentially dangerous commands"""
        dangerous_patterns = [
            'format', 'rmdir /s', 'del /s', 'rd /s',
            'shutdown', 'restart', 'reg delete',
            'diskpart', 'fdisk', 'attrib -r -s -h'
        ]
        
        command_lower = command.lower()
        for pattern in dangerous_patterns:
            if pattern in command_lower:
                return False, f"Potentially dangerous command detected: {pattern}"
        return True, ""
    
    def run_command(self, cmd):
        """Execute command(s) with improved error handling"""
        try:
            commands = [c.strip() for c in cmd.strip().splitlines() if c.strip()]
            full_output = ""
            full_error = ""

            for command in commands:
                print(f"\n>> {command}")
                
                # Handle built-in commands
                if command.lower() == 'clear':
                    os.system('cls')
                    continue
                
                # Run the command
                result = subprocess.run(
                    command, 
                    shell=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30  # 30 second timeout
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
            return "", "Command timed out after 30 seconds"
        except Exception as e:
            return "", f"Execution error: {e}"
    
    def show_help(self):
        """Display help information"""
        help_text = """
AI Terminal Help:
================
/ai <instruction>  - Convert natural language to command
/ask <question>    - Ask AI anything (general conversation)
/ai help          - Show AI command examples
/ask help         - Show conversation examples
help              - Show this help
clear             - Clear the screen
exit              - Exit the terminal

Command Examples:
/ai list all files in current directory
/ai create a new folder called projects
/ai show system information
/ai find all text files containing "python"

Conversation Examples:
/ask what is the difference between TCP and UDP?
/ask how do I optimize my Python code?
/ask explain what docker containers are
/ask why is my computer running slowly?
        """
        print(help_text)
    
    def show_ai_help(self):
        """Show AI-specific help and examples"""
        examples = [
            "list all files and folders",
            "create a backup of my documents folder",
            "find all python files in this directory",
            "show disk space usage",
            "display network configuration",
            "compress this folder into a zip file",
            "show running processes"
        ]
        
        print("\nAI Command Examples:")
        print("===================")
        for example in examples:
            print(f"/ai {example}")
        print()
    
    def show_ask_help(self):
        """Show conversation-specific help and examples"""
        examples = [
            "what is the difference between git merge and git rebase?",
            "how do I debug a Python script?",
            "explain REST APIs in simple terms",
            "what are the best practices for password security?",
            "how does machine learning work?",
            "why is my code running slowly?",
            "what is the difference between compiled and interpreted languages?"
        ]
        
        print("\nAI Conversation Examples:")
        print("========================")
        for example in examples:
            print(f"/ask {example}")
        print()
        print("💡 Tip: I remember our conversation context, so you can ask follow-up questions!")
        print()
    
    def run(self):
        """Main terminal loop"""
        print("🤖 Welcome to AI Terminal!")
        print("Type '/ai <your request>' for natural language commands")
        print("Type '/ask <question>' for general AI conversation")
        print("Type 'help' for assistance, 'exit' to quit")
        
        try:
            with patch_stdout():
                while True:
                    try:
                        user_input = self.session.prompt(
                            ANSI("\x1b[1;32mAI-Terminal> \x1b[0m")
                        )
                        
                        if not user_input.strip():
                            continue
                        
                        if user_input.strip().lower() == "exit":
                            break
                        elif user_input.strip().lower() == "help":
                            self.show_help()
                            continue
                        elif user_input.strip().lower() == "clear":
                            os.system('cls')
                            continue
                        
                        if user_input.startswith("/ai"):
                            natural_prompt = user_input[3:].strip()
                            
                            if natural_prompt.lower() == "help":
                                self.show_ai_help()
                                continue
                            
                            if not natural_prompt:
                                print("Please provide an instruction after /ai")
                                continue
                            
                            print(f"\n🔄 Processing: {natural_prompt}")
                            shell_cmd = self.natural_to_command(natural_prompt)
                            
                            if shell_cmd.startswith("Error"):
                                print(f"❌ {shell_cmd}")
                                continue
                            
                            print(f"🤖 AI → {shell_cmd}")
                            
                            # Safety check
                            is_safe, warning = self.is_safe_command(shell_cmd)
                            if not is_safe:
                                print(f"⚠️  Warning: {warning}")
                                if not (input("Do you want to proceed anyway? [y/N]: ").strip().lower() in ['y', 'yes']):
                                    print("Command cancelled for safety.")
                                    continue
                            
                            # Confirm execution
                            confirm_response = input("Run this command? [Y/n]: ").strip().lower()
                            if confirm_response in ['y', 'yes', '']:
                                out, err = self.run_command(shell_cmd)
                                if out:
                                    print(f"\n✅ Output:\n{out}")
                                if err:
                                    print(f"\n❌ Error:\n{err}")
                            else:
                                print("Command skipped.")
                        
                        elif user_input.startswith("/ask"):
                            question = user_input[4:].strip()
                            
                            if question.lower() == "help":
                                self.show_ask_help()
                                continue
                            
                            if not question:
                                print("Please ask a question after /ask")
                                continue
                            
                            print(f"\n💭 Thinking about: {question}")
                            answer = self.ask_ai(question)
                            
                            if answer.startswith("Error"):
                                print(f"❌ {answer}")
                            else:
                                print(f"\n🤖 AI: {answer}")
                                print()  # Extra line for readability
                        
                        else:
                            # Direct command execution
                            out, err = self.run_command(user_input)
                            if out:
                                print(f"\n{out}")
                            if err:
                                print(f"\nError:\n{err}")

                    except (KeyboardInterrupt, EOFError):
                        break
                    except Exception as e:
                        print(f"Unexpected error: {e}")

        finally:
            self.save_command_history()
            print("\n👋 Goodbye!")

if __name__ == "__main__":
    terminal = AITerminal()
    terminal.run()