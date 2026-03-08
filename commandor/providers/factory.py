from .anthropic import AnthropicProvider
from .base import AuthenticationError, BaseProvider, ProviderError
from .gemini import GeminiProvider
from .openai import OpenAIProvider
from .openrouter import OpenRouterProvider


class ProviderFactory:
    """Factory for creating AI providers"""

    _providers = {
        "gemini": GeminiProvider,
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
        "openrouter": OpenRouterProvider,
    }

    @classmethod
    def create(
        cls, provider_name: str, api_key: str, model: str = None, **kwargs
    ) -> BaseProvider:
        """Create a provider instance"""
        provider_class = cls._providers.get(provider_name.lower())

        if not provider_class:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown provider: {provider_name}. Available: {available}"
            )

        return provider_class(api_key=api_key, model=model, **kwargs)

    @classmethod
    def list_providers(cls) -> list:
        """List available provider names"""
        return list(cls._providers.keys())

    @classmethod
    def get_default_model(cls, provider_name: str) -> str:
        """Get default model for a provider"""
        defaults = {
            "gemini": "gemini-2.5-flash",
            "anthropic": "claude-3.5-sonnet-20241022",
            "openai": "gpt-4o",
            "openrouter": "anthropic/claude-3.5-sonnet",
        }
        return defaults.get(provider_name, "")


__all__ = [
    "BaseProvider",
    "ProviderFactory",
    "GeminiProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
    "ProviderError",
    "AuthenticationError",
]
