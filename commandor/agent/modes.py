from abc import ABC, abstractmethod
from typing import Callable, Optional
import sys


class AgentMode(ABC):
    """Base class for agent modes"""
    
    name: str = "base"
    description: str = ""
    requires_confirmation: bool = False
    
    @abstractmethod
    def should_proceed(self, action_description: str, callback: Callable[[], bool]) -> bool:
        """Check if action should proceed
        
        Args:
            action_description: Description of the action
            callback: Function to call to get user confirmation
        
        Returns:
            True if should proceed, False otherwise
        """
        pass
    
    @abstractmethod
    def format_action(self, tool_name: str, args: dict) -> str:
        """Format action for display"""
        pass
    
    @abstractmethod
    def format_result(self, tool_name: str, result: str) -> str:
        """Format result for display"""
        pass


class AutonomousMode(AgentMode):
    """Agent acts autonomously without confirmation"""
    
    name = "agent"
    description = "Autonomous mode - agent acts without asking for confirmation"
    requires_confirmation = False
    
    def should_proceed(self, action_description: str, callback: Callable[[], bool]) -> bool:
        """Always proceed in autonomous mode"""
        return True
    
    def format_action(self, tool_name: str, args: dict) -> str:
        """Format action for display"""
        args_str = ", ".join(f"{k}={v}" for k, v in args.items())
        return f"🔧 Executing {tool_name}({args_str})..."
    
    def format_result(self, tool_name: str, result: str) -> str:
        """Format result for display"""
        if len(result) > 500:
            result = result[:500] + "..."
        return f"✅ {tool_name}: {result}"


class AssistMode(AgentMode):
    """Human-in-the-loop: confirms each action"""
    
    name = "assist"
    description = "Assist mode - agent asks for confirmation before each action"
    requires_confirmation = True
    
    def should_proceed(self, action_description: str, callback: Callable[[], bool]) -> bool:
        """Ask for confirmation in assist mode"""
        print(f"\n🤔 {action_description}")
        return callback()
    
    def format_action(self, tool_name: str, args: dict) -> str:
        """Format action for display"""
        args_str = ", ".join(f"{k}={v}" for k, v in args.items())
        return f"🔧 Execute {tool_name}({args_str})?"
    
    def format_result(self, tool_name: str, result: str) -> str:
        """Format result for display"""
        if len(result) > 500:
            result = result[:500] + "..."
        return f"📋 Result:\n{result}"


class ChatMode(AgentMode):
    """Simple Q&A mode - no tools, just conversation"""
    
    name = "chat"
    description = "Chat mode - ask questions without executing actions"
    requires_confirmation = False
    
    def should_proceed(self, action_description: str, callback: Callable[[], bool]) -> bool:
        """Always proceed in chat mode"""
        return True
    
    def format_action(self, tool_name: str, args: dict) -> str:
        args_str = ", ".join(f"{k}={v}" for k, v in args.items())
        return f"🔧 {tool_name}({args_str})"
    
    def format_result(self, tool_name: str, result: str) -> str:
        return result


# Mode registry
MODES = {
    "agent": AutonomousMode(),
    "assist": AssistMode(),
    "chat": ChatMode(),
}


def get_mode(name: str) -> AgentMode:
    """Get a mode by name"""
    return MODES.get(name, AutonomousMode())


def list_modes() -> dict:
    """List all available modes"""
    return {name: mode.description for name, mode in MODES.items()}
