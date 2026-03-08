from openai import OpenAI
from typing import List, Dict, Any, Optional
from .base import BaseProvider, Response, ToolCall, Message, AuthenticationError


class OpenRouterProvider(BaseProvider):
    """OpenRouter provider - aggregates multiple AI providers"""
    
    name = "openrouter"
    supports_vision = True
    supports_tools = True
    
    BASE_URL = "https://openrouter.ai/api/v1"
    
    def _configure(self, **kwargs):
        """Configure OpenRouter client"""
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.BASE_URL
        )
    
    def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Response:
        """Generate response using OpenRouter"""
        try:
            # Convert messages to OpenAI format (same API)
            openai_messages = self._convert_messages(messages)
            
            # Build request params
            params = {
                "model": self.model,
                "messages": openai_messages,
                "temperature": temperature,
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
            
            if tools:
                params["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool.get("description", ""),
                            "parameters": tool["parameters"]
                        }
                    }
                    for tool in tools
                ]
                params["tool_choice"] = "auto"
            
            # Add OpenRouter specific headers
            extra_headers = {
                "HTTP-Referer": "https://github.com/ravin-d-27/Commandor",
                "X-Title": "Commandor"
            }
            
            response = self.client.chat.completions.create(
                **params,
                extra_headers=extra_headers
            )
            
            # Parse response (same as OpenAI)
            choice = response.choices[0]
            content = choice.message.content or ""
            
            tool_calls = None
            if choice.message.tool_calls:
                tool_calls = []
                for tc in choice.message.tool_calls:
                    tool_calls.append(ToolCall(
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                        id=tc.id
                    ))
            
            return Response(
                content=content,
                tool_calls=tool_calls,
                finish_reason=choice.finish_reason or "stop",
                model=response.model,
                usage={
                    "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "output_tokens": response.usage.completion_tokens if response.usage else 0,
                }
            )
            
        except Exception as e:
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                raise AuthenticationError("Invalid API key", self.name)
            raise
    
    def generate_json(
        self,
        messages: List[Message],
        schema: Dict,
        **kwargs
    ) -> Dict:
        """Generate JSON response"""
        messages = messages + [
            Message("user", f"Respond ONLY with valid JSON matching this schema: {schema}. No other text.")
        ]
        
        response = self.generate(messages, **kwargs)
        
        try:
            import json
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())
        except:
            return {}
    
    def validate_key(self) -> bool:
        """Validate API key"""
        try:
            self.client.chat.completions.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
                extra_headers={
                    "HTTP-Referer": "https://github.com/ravin-d-27/Commandor",
                    "X-Title": "Commandor"
                }
            )
            return True
        except Exception:
            return False
    
    def _convert_messages(self, messages: List[Message]) -> List[Dict]:
        """Convert Message objects to OpenAI format"""
        openai_messages = []
        
        for msg in messages:
            if msg.role == "system":
                openai_messages.append({
                    "role": "system",
                    "content": msg.content
                })
            elif msg.role == "user":
                if msg.tool_call_id:
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content
                    })
                else:
                    openai_messages.append({
                        "role": "user",
                        "content": msg.content
                    })
            elif msg.role == "assistant":
                if msg.tool_calls:
                    openai_messages.append({
                        "role": "assistant",
                        "content": msg.content,
                        "tool_calls": [
                            {
                                "id": tc.id or f"call_{tc.name}",
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": tc.arguments if isinstance(tc.arguments, str) else str(tc.arguments)
                                }
                            }
                            for tc in msg.tool_calls
                        ]
                    })
                else:
                    openai_messages.append({
                        "role": "assistant",
                        "content": msg.content
                    })
        
        return openai_messages
