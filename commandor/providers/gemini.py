from google import genai
from google.genai import types
from typing import List, Dict, Any, Optional
from .base import BaseProvider, Response, ToolCall, Message, AuthenticationError


class GeminiProvider(BaseProvider):
    """Google Gemini provider using google-genai SDK"""
    
    name = "gemini"
    supports_vision = True
    supports_tools = True
    
    def _configure(self, **kwargs):
        """Configure Gemini client"""
        self.client = genai.Client(api_key=self.api_key)
    
    def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Response:
        """Generate response using Gemini"""
        try:
            # Build generation config
            generation_config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            # Convert messages to Gemini format
            gemini_messages = self._convert_messages(messages)
            
            # Add tools if provided
            if tools:
                function_declarations = [
                    types.FunctionDeclaration(
                        name=tool["name"],
                        description=tool.get("description", ""),
                        parameters=tool["parameters"]
                    )
                    for tool in tools
                ]
                generation_config.tools = [types.Tool(function_declarations=function_declarations)]
            
            # Generate content
            response = self.client.models.generate_content(
                model=self.model,
                contents=gemini_messages,
                config=generation_config
            )
            
            # Parse response — check function_calls first to avoid the
            # "non-text parts" warning that fires when accessing response.text
            # while function calls are present.
            content = ""
            tool_calls = None

            if response.function_calls:
                tool_calls = []
                for fc in response.function_calls:
                    args_dict = dict(fc.args) if hasattr(fc, 'args') else {}
                    tool_calls.append(ToolCall(
                        name=fc.name,
                        arguments=args_dict,
                        id=getattr(fc, 'id', None)
                    ))
            else:
                # Only read text when there are no function calls
                if response.text:
                    content = response.text

            # finish_reason lives on candidates[0], not on the response root
            finish_reason = "stop"
            if response.candidates:
                fr = response.candidates[0].finish_reason
                if fr is not None:
                    finish_reason = str(fr).lower()
            
            return Response(
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                model=self.model
            )
            
        except Exception as e:
            error_msg = str(e)
            if "API_KEY" in error_msg or "authentication" in error_msg.lower() or "permission" in error_msg.lower():
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
            Message("user", f"Respond with valid JSON matching this schema: {schema}")
        ]
        
        response = self.generate(messages, **kwargs)
        
        try:
            import json
            return json.loads(response.content)
        except:
            return {}
    
    def validate_key(self) -> bool:
        """Validate API key"""
        try:
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=["Hello"],
                config=types.GenerateContentConfig(max_output_tokens=10)
            )
            return response is not None
        except Exception:
            return False
    
    def _convert_messages(self, messages: List[Message]) -> List[types.Content]:
        """Convert Message objects to Gemini format"""
        contents = []
        
        for msg in messages:
            if msg.role == "system":
                # System messages are handled separately
                continue
            elif msg.role == "user":
                if msg.tool_call_id:
                    # Tool result — use from_function_response with the function name
                    # msg.tool_name carries the function name (set by the agent)
                    func_name = msg.tool_name or msg.tool_call_id
                    part = types.Part.from_function_response(
                        name=func_name,
                        response={"result": msg.content}
                    )
                    contents.append(types.Content(
                        role="user",
                        parts=[part]
                    ))
                else:
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part(text=msg.content)]
                    ))
            elif msg.role == "assistant":
                if msg.tool_calls:
                    # Handle tool calls
                    for tc in msg.tool_calls:
                        args_dict = tc.arguments if isinstance(tc.arguments, dict) else {}
                        function_call = types.FunctionCall(
                            name=tc.name,
                            args=args_dict,
                            id=tc.id
                        )
                        contents.append(types.Content(
                            role="model",
                            parts=[types.Part(function_call=function_call)]
                        ))
                else:
                    contents.append(types.Content(
                        role="model",
                        parts=[types.Part(text=msg.content)]
                    ))
            elif msg.role == "tool":
                # Tool result message — role="tool" is used by the agent
                func_name = msg.tool_name or msg.tool_call_id or "unknown"
                part = types.Part.from_function_response(
                    name=func_name,
                    response={"result": msg.content}
                )
                contents.append(types.Content(
                    role="user",
                    parts=[part]
                ))
        
        return contents
