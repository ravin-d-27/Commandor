from typing import Optional, Callable
import sys
from pathlib import Path

from ..providers.base import BaseProvider
from ..providers.factory import ProviderFactory
from ..config import get_config, get_api_key
from .agent import Agent, AgentResult
from .modes import get_mode, list_modes


class AgentExecutor:
    """Executor for running agent tasks"""
    
    def __init__(
        self,
        provider: Optional[BaseProvider] = None,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.config = get_config()
        self.provider = provider
        self.provider_name = provider_name
        self.model = model
    
    def _get_provider(self) -> BaseProvider:
        """Get or create provider"""
        if self.provider:
            return self.provider
        
        # Get provider name from config or parameter
        provider_name = self.provider_name or self.config.config.default_provider
        
        # Get API key
        api_key = get_api_key(provider_name)
        if not api_key:
            raise ValueError(
                f"No API key for {provider_name}. "
                f"Run 'commandor setup' to configure."
            )
        
        # Get model
        model = self.model
        if not model:
            pconfig = self.config.get_provider_config(provider_name)
            model = pconfig.default_model if pconfig else ProviderFactory.get_default_model(provider_name)
        
        # Create provider
        return ProviderFactory.create(provider_name, api_key, model)
    
    def run(
        self,
        task: str,
        mode: str = "agent",
        max_iterations: int = None,
        confirm_destructive: bool = None,
        verbose: bool = True,
    ) -> AgentResult:
        """Run an agent task
        
        Args:
            task: The task to accomplish
            mode: Agent mode (agent, assist, chat)
            max_iterations: Max iterations (default from config)
            confirm_destructive: Whether to confirm dangerous actions
            verbose: Whether to show progress
        
        Returns:
            AgentResult with the outcome
        """
        if verbose:
            print(f"\n🤖 Running Commandor Agent")
            print(f"   Mode: {mode}")
            print(f"   Task: {task}")
            print("-" * 40)
        
        # Get provider
        provider = self._get_provider()
        
        # Get agent config
        agent_config = self.config.config.agent
        max_iterations = max_iterations or agent_config.max_iterations
        confirm_destructive = confirm_destructive if confirm_destructive is not None else agent_config.confirm_destructive
        
        # Create agent
        agent = Agent(
            provider=provider,
            mode=get_mode(mode),
            max_iterations=max_iterations,
            confirm_destructive=confirm_destructive
        )
        
        # Run
        try:
            result = agent.run(task)
            
            if verbose:
                print("-" * 40)
                print(f"✅ Completed in {result.iterations} iteration(s)")
                if result.error:
                    print(f"⚠️  {result.error}")
            
            return result
            
        except Exception as e:
            return AgentResult(
                success=False,
                final_answer=f"Error: {str(e)}",
                error=str(e)
            )


def run_agent(
    task: str,
    mode: str = "agent",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs
) -> AgentResult:
    """Convenience function to run an agent task"""
    executor = AgentExecutor(provider_name=provider, model=model)
    return executor.run(task, mode=mode, **kwargs)


def run_agent_interactive(
    task: str,
    mode: str = "agent",
    callback: Optional[Callable] = None,
    **kwargs
) -> AgentResult:
    """Run agent with interactive confirmation callback"""
    executor = AgentExecutor()
    
    # Wrap callback for mode
    if mode == "assist":
        original_callback = kwargs.get('confirm_callback')
        def wrapped_callback(action_desc):
            print(f"\n🤔 {action_desc}")
            response = input("   Proceed? (y/n/q): ").strip().lower()
            if response == 'q':
                raise KeyboardInterrupt("Cancelled by user")
            return response == 'y'
        kwargs['confirm_callback'] = wrapped_callback
    
    return executor.run(task, mode=mode, **kwargs)


def test_providers() -> dict:
    """Test all configured providers"""
    config = get_config()
    results = {}
    
    for name in config.get_enabled_providers():
        try:
            api_key = get_api_key(name)
            if not api_key:
                results[name] = {"status": "no_api_key"}
                continue
            
            provider = ProviderFactory.create(
                name,
                api_key,
                ProviderFactory.get_default_model(name)
            )
            
            results[name] = {
                "status": "ok" if provider.validate_key() else "invalid_key"
            }
        except Exception as e:
            results[name] = {"status": "error", "error": str(e)}
    
    return results
