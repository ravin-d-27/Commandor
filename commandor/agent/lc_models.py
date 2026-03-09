"""Factory for building LangChain BaseChatModel instances from provider name."""

from langchain_core.language_models.chat_models import BaseChatModel


def build_model(provider: str, api_key: str, model: str) -> BaseChatModel:
    """Return an instantiated LangChain chat model for the given provider.

    Args:
        provider: One of 'gemini', 'anthropic', 'openai', 'openrouter'.
        api_key:  The API key for the chosen provider.
        model:    The model identifier string (e.g. 'gemini-2.5-flash').

    Returns:
        A LangChain BaseChatModel ready to be passed to create_react_agent.

    Raises:
        ValueError: If the provider name is not recognised.
        ImportError: If the required langchain integration package is missing.
    """
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0.7,
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415

        return ChatAnthropic(
            model=model,
            anthropic_api_key=api_key,
            temperature=0.7,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=0.7,
        )

    elif provider == "openrouter":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0.7,
            default_headers={
                "HTTP-Referer": "https://github.com/ravin-d-27/Commandor",
                "X-Title": "Commandor",
            },
        )

    else:
        raise ValueError(
            f"Unknown provider: '{provider}'. "
            "Valid choices are: gemini, anthropic, openai, openrouter."
        )
