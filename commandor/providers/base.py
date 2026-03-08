from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass
import json


@dataclass
class ToolCall:
    """Represents a tool call from the AI"""
    name: str
    arguments: Dict[str, Any]
    id: Optional[str] = None


@dataclass
class Message:
    """Represents a message in the conversation"""
    role: str  # 'system', 'user', 'assistant', 'tool'
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None  # Name of the tool (needed for Gemini function responses)


@dataclass
class Response:
    """Represents a response from the AI"""
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: str = "stop"
    model: str = ""
    usage: Optional[Dict[str, int]] = None


class BaseProvider(ABC):
    """Abstract base class for AI providers"""
    
    name: str = "base"
    supports_vision: bool = False
    supports_tools: bool = True
    
    def __init__(
        self, 
        api_key: str, 
        model: str,
        **kwargs
    ):
        self.api_key = api_key
        self.model = model
        self.client = None
        self._configure(**kwargs)
    
    @abstractmethod
    def _configure(self, **kwargs):
        """Configure the provider client"""
        pass
    
    @abstractmethod
    def generate(
        self, 
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Response:
        """Generate a response from the AI"""
        pass
    
    @abstractmethod
    def generate_json(
        self, 
        messages: List[Message],
        schema: Dict,
        **kwargs
    ) -> Dict:
        """Generate a structured JSON response"""
        pass
    
    @abstractmethod
    def validate_key(self) -> bool:
        """Validate that the API key works"""
        pass
    
    def _format_tools(self, tools: Optional[List[Dict]]) -> Optional[Dict]:
        """Format tools for the provider's API"""
        if not tools:
            return None
        
        formatted = {
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {})
                    }
                }
                for tool in tools
            ]
        }
        return formatted
    
    def _parse_tool_calls(self, response_data: Any) -> Optional[List[ToolCall]]:
        """Parse tool calls from provider response"""
        return None
    
    def __repr__(self):
        return f"<{self.__class__.__name__} model={self.model}>"


class ProviderError(Exception):
    """Base exception for provider errors"""
    def __init__(self, message: str, provider: str = None):
        self.message = message
        self.provider = provider
        super().__init__(self.message)


class AuthenticationError(ProviderError):
    """API key authentication failed"""
    pass


class RateLimitError(ProviderError):
    """Rate limit exceeded"""
    pass


class ModelNotFoundError(ProviderError):
    """Model not found or not available"""
    pass
