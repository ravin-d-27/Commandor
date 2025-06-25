"""
AI Assistant Module
Handles AI-related functionality including natural language processing
and conversation management.
"""

import os
import json
import ollama
from utils import Colors


class AIAssistant:
    """Handles AI interactions for command generation and conversation."""
    
    def __init__(self):
        # Command history for AI suggestions
        self.command_history = []
        self.load_command_history()
        
        # Conversation history for /ask feature
        self.conversation_history = []
    
    def save_command_history(self):
        """Save command history to file for learning patterns."""
        try:
            with open('.ai_command_history.json', 'w') as f:
                json.dump(self.command_history[-100:], f)  # Keep last 100 commands
        except Exception as e:
            print(f"{Colors.YELLOW}Warning: Could not save command history: {e}{Colors.RESET}")
    
    def load_command_history(self):
        """Load command history from file."""
        try:
            if os.path.exists('.ai_command_history.json'):
                with open('.ai_command_history.json', 'r') as f:
                    self.command_history = json.load(f)
        except Exception as e:
            print(f"{Colors.YELLOW}Warning: Could not load command history: {e}{Colors.RESET}")
    
    def get_system_context(self):
        """Get current system context for better command generation."""
        try:
            current_dir = os.getcwd()
            username = os.getenv('USERNAME', 'user')
            return f"Current directory: {current_dir}\nUsername: {username}"
        except:
            return "System context unavailable"
    
    def natural_to_command(self, prompt):
        """Convert natural language to shell command using Ollama."""
        try:
            system_context = self.get_system_context()
            
            # Enhanced prompt with system context and safety guidelines
            full_prompt = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert Linux command-line assistant. Convert natural language instructions to Linux commands.\n"
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
            command = self._clean_command_output(command)
            
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
        """Have a normal conversation with AI."""
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
    
    def _clean_command_output(self, command):
        """Clean up command output from potential markdown or explanations."""
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
    
    def show_ai_help(self):
        """Show AI-specific help and examples."""
        examples = [
            "list all files and folders",
            "create a backup of my documents folder",
            "find all python files in this directory",
            "show disk space usage",
            "display network configuration",
            "compress this folder into a zip file",
            "show running processes"
        ]
        
        print(f"\n{Colors.CYAN}AI Command Examples:{Colors.RESET}")
        print(f"{Colors.CYAN}==================={Colors.RESET}")
        for example in examples:
            print(f"{Colors.GREEN}/ai {example}{Colors.RESET}")
        print()
    
    def show_ask_help(self):
        """Show conversation-specific help and examples."""
        examples = [
            "what is the difference between git merge and git rebase?",
            "how do I debug a Python script?",
            "explain REST APIs in simple terms",
            "what are the best practices for password security?",
            "how does machine learning work?",
            "why is my code running slowly?",
            "what is the difference between compiled and interpreted languages?"
        ]
        
        print(f"\n{Colors.CYAN}AI Conversation Examples:{Colors.RESET}")
        print(f"{Colors.CYAN}========================{Colors.RESET}")
        
        for example in examples:
            print(f"{Colors.GREEN}/ask {example}{Colors.RESET}")
        print()
        print(f"{Colors.YELLOW}💡 Tip: I remember our conversation context, so you can ask follow-up questions!{Colors.RESET}")
        print()