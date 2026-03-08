from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
import json

from ..providers.base import BaseProvider, Message, Response, ToolCall
from .tools import ToolRegistry, get_registry
from .modes import AgentMode, AutonomousMode, get_mode
from .prompts import get_system_prompt, get_user_prompt


@dataclass
class ExecutionStep:
    """Represents a single step in execution"""
    step_number: int
    tool_name: str
    arguments: Dict[str, Any]
    result: str
    success: bool


@dataclass
class AgentResult:
    """Result of agent execution"""
    success: bool
    final_answer: str
    steps: List[ExecutionStep] = field(default_factory=list)
    iterations: int = 0
    error: Optional[str] = None


class Agent:
    """Core agent that executes tasks using AI and tools"""
    
    def __init__(
        self,
        provider: BaseProvider,
        mode: AgentMode = None,
        max_iterations: int = 50,
        confirm_destructive: bool = True,
    ):
        self.provider = provider
        self.mode = mode or AutonomousMode()
        self.max_iterations = max_iterations
        self.confirm_destructive = confirm_destructive
        
        self.tools = get_registry()
        self.messages: List[Message] = []
        self.steps: List[ExecutionStep] = []
        self.iterations = 0
    
    def reset(self):
        """Reset agent state for new task"""
        self.messages = []
        self.steps = []
        self.iterations = 0
    
    def _get_context(self) -> Dict[str, Any]:
        """Get project context"""
        context = {
            "cwd": str(Path.cwd()),
        }
        
        # Add git info if in a git repo
        try:
            from ..utils import shell
            context["git_info"] = shell.get_git_info()
        except:
            pass
        
        return context
    
    def _build_messages(self, task: str) -> List[Message]:
        """Build message list for API call"""
        # System message
        system_prompt = get_system_prompt(
            self.tools.get_schemas(),
            self._get_context()
        )
        messages = [Message(role="system", content=system_prompt)]
        
        # Add conversation history
        messages.extend(self.messages)
        
        # Add current task
        messages.append(Message(role="user", content=get_user_prompt(task)))
        
        return messages
    
    def _add_message(self, role: str, content: str, tool_calls: List[ToolCall] = None):
        """Add a message to history"""
        self.messages.append(Message(
            role=role,
            content=content,
            tool_calls=tool_calls
        ))
    
    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool and return result"""
        # Check for dangerous tools
        if self.tools.is_dangerous(tool_name) and self.confirm_destructive:
            action_desc = self.mode.format_action(tool_name, arguments)
            
            def confirm_callback():
                response = input(f"⚠️  {action_desc} (y/n): ").strip().lower()
                return response == 'y'
            
            if not self.mode.should_proceed(action_desc, confirm_callback):
                return "Cancelled by user"
        
        # Execute the tool
        print(f"\n{self.mode.format_action(tool_name, arguments)}")
        result = self.tools.execute(tool_name, **arguments)
        
        print(f"{self.mode.format_result(tool_name, result)}")
        
        return result
    
    def _process_tool_calls(self, tool_calls: List[ToolCall]) -> List[Message]:
        """Process tool calls from AI response"""
        results = []
        
        for tc in tool_calls:
            # Convert arguments if they're a string
            args = tc.arguments
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except:
                    args = {"input": args}
            
            # Execute tool
            result = self._execute_tool(tc.name, args)
            
            # Add to step history
            self.steps.append(ExecutionStep(
                step_number=len(self.steps) + 1,
                tool_name=tc.name,
                arguments=args,
                result=result,
                success=not result.startswith("Error")
            ))
            
            # Add tool result message
            results.append(Message(
                role="tool",
                content=result,
                tool_call_id=tc.id,
                tool_name=tc.name
            ))
        
        return results
    
    async def run_async(self, task: str) -> AgentResult:
        """Run agent asynchronously"""
        self.reset()
        
        try:
            # Build initial messages
            messages = self._build_messages(task)
            
            # Main loop
            for iteration in range(self.max_iterations):
                self.iterations = iteration + 1
                
                # Get AI response with tools
                response = self.provider.generate(
                    messages=messages,
                    tools=self.tools.get_schemas(),
                    temperature=0.7
                )
                
                # Check for tool calls
                if response.tool_calls:
                    # Add assistant message with tool calls
                    self._add_message("assistant", response.content, response.tool_calls)
                    messages.append(Message(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls
                    ))
                    
                    # Execute tools
                    tool_results = self._process_tool_calls(response.tool_calls)
                    messages.extend(tool_results)
                    
                    # Add tool results to conversation
                    for tr in tool_results:
                        self._add_message(tr.role, tr.content)
                
                elif response.content:
                    # Final answer
                    return AgentResult(
                        success=True,
                        final_answer=response.content,
                        steps=self.steps,
                        iterations=self.iterations
                    )
                
                else:
                    # No response
                    return AgentResult(
                        success=False,
                        final_answer="No response from AI",
                        steps=self.steps,
                        iterations=self.iterations,
                        error="Empty response"
                    )
            
            # Max iterations reached
            return AgentResult(
                success=False,
                final_answer="Maximum iterations reached",
                steps=self.steps,
                iterations=self.iterations,
                error="Max iterations"
            )
            
        except Exception as e:
            return AgentResult(
                success=False,
                final_answer=f"Error: {str(e)}",
                steps=self.steps,
                iterations=self.iterations,
                error=str(e)
            )
    
    def run(self, task: str) -> AgentResult:
        """Run agent synchronously"""
        try:
            import asyncio
            return asyncio.run(self.run_async(task))
        except RuntimeError:
            # Already in async context
            return asyncio.run(self.run_async(task))


def create_agent(
    provider: BaseProvider,
    mode_name: str = "agent",
    **kwargs
) -> Agent:
    """Create an agent with the specified mode"""
    mode = get_mode(mode_name)
    return Agent(provider=provider, mode=mode, **kwargs)
