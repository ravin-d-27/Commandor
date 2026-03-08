import anthropic
from typing import List, Dict, Any, Optional
from .base import BaseProvider, Response, ToolCall, Message, AuthenticationError


class AnthropicProvider(BaseProvider):
    """Anthropic Claude provider"""
    
    name = "anthropic"
    supports_vision = True
    supports_tools = True
    
    def _configure(self, **kwargs):
        """Configure Anthropic client"""
        self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Response:
        """Generate response using Claude"""
        try:
            # Convert messages to Anthropic format
            anthropic_messages = self._convert_messages(messages)
            
            # Build request params
            params = {
                "model": self.model,
                "messages": anthropic_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,
            }
            
            if tools:
                params["tools"] = [
                    {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "input_schema": tool["parameters"]
                    }
                    for tool in tools
                ]
            
            response = self.client.messages.create(**params)
            
            # Parse response
            content = ""
            tool_calls = None
            
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append(ToolCall(
                        name=block.name,
                        arguments=block.input,
                        id=block.id
                    ))
            
            return Response(
                content=content,
                tool_calls=tool_calls,
                finish_reason=response.stop_reason or "stop",
                model=self.model,
                usage={
                    "input_tokens": response.usage.input_tokens if hasattr(response, 'usage') else 0,
                    "output_tokens": response.usage.output_tokens if hasattr(response, 'usage') else 0,
                }
            )
            
        except anthropic.AuthenticationError as e:
            raise AuthenticationError("Invalid API key", self.name)
        except Exception as e:
            raise
    
    def generate_json(
        self,
        messages: List[Message],
        schema: Dict,
        **kwargs
    ) -> Dict:
        """Generate JSON response"""
        # Add JSON instruction
        messages = messages + [
            Message("user", f"Respond ONLY with valid JSON matching this schema: {schema}. No other text.")
        ]
        
        response = self.generate(messages, **kwargs)
        
        try:
            import json
            # Try to extract JSON from response
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())
        except:
            return {}
    
    def validate_key(self) -> bool:
        """Validate API key"""
        try:
            self.client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            return True
        except Exception:
            return False
    
    def _convert_messages(self, messages: List[Message]) -> List[Dict]:
        """Convert Message objects to Anthropic format"""
        anthropic_messages = []
        
        for msg in messages:
            if msg.role == "system":
                # Anthropic uses system parameter separately
                continue
            
            role = "assistant" if msg.role in ["assistant", "system"] else msg.role
            
            if msg.tool_calls:
                # Handle tool calls for assistant messages
                for tc in msg.tool_calls:
                    anthropic_messages.append({
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": tc.id or "temp",
                                "name": tc.name,
                                "input": tc.arguments
                            }
                        ]
                    })
            elif msg.tool_call_id:
                # Tool result
                anthropic_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content
                        }
                    ]
                })
            else:
                anthropic_messages.append({
                    "role": role,
                    "content": msg.content
                })
        
        return anthropic_messages
