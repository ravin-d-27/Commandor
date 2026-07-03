"""Factory for building LangChain BaseChatModel instances from provider name.

Supported providers (8 total):

    gemini          — Google Gemini  (langchain_google_genai)
    anthropic       — Anthropic Claude (langchain_anthropic)
    openai          — OpenAI GPT      (langchain_openai)
    openrouter      — OpenRouter      (langchain_openai + custom base_url)
    ollama          — Local Ollama    (langchain_ollama)
    groq            — Groq Cloud      (langchain_groq)
    deepseek        — DeepSeek        (langchain_openai + custom base_url)
    openai_compat   — Any OpenAI-compatible endpoint (LM Studio, vLLM,
                       llama.cpp server, etc.) — user provides base_url
"""

from __future__ import annotations

import os
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel


# Default model & base_url per provider, used when the user hasn't set one.
PROVIDER_DEFAULTS: dict[str, dict] = {
    "gemini":        {"model": "gemini-2.5-flash",                                "base_url": None},
    "anthropic":     {"model": "claude-3-5-sonnet-20241022",                      "base_url": None},
    "openai":        {"model": "gpt-4o",                                          "base_url": None},
    "openrouter":    {"model": "anthropic/claude-3.5-sonnet",                     "base_url": "https://openrouter.ai/api/v1"},
    "ollama":        {"model": "llama3.1",                                        "base_url": "http://localhost:11434"},
    "groq":          {"model": "llama-3.3-70b-versatile",                         "base_url": None},
    "deepseek":      {"model": "deepseek-chat",                                   "base_url": "https://api.deepseek.com/v1"},
    "openai_compat": {"model": "local-model",                                     "base_url": "http://localhost:1234/v1"},
}


def build_model(
    provider: str,
    api_key: str,
    model: str,
    base_url: Optional[str] = None,
) -> BaseChatModel:
    """Return an instantiated LangChain chat model for the given provider.

    Args:
        provider:  One of 'gemini', 'anthropic', 'openai', 'openrouter',
                   'ollama', 'groq', 'deepseek', 'openai_compat'.
        api_key:   The API key for the chosen provider (use any non-empty
                   string for keyless local providers like ollama).
        model:     The model identifier string.
        base_url:  Optional override for the API base URL.  Defaults are
                   taken from PROVIDER_DEFAULTS.  Required for
                   'openai_compat'.

    Returns:
        A LangChain BaseChatModel ready to be passed to create_react_agent.

    Raises:
        ValueError: If the provider name is not recognised.
        ImportError: If the required langchain integration package is missing.
    """
    if provider not in PROVIDER_DEFAULTS:
        raise ValueError(
            f"Unknown provider: '{provider}'.  "
            f"Valid choices are: {', '.join(PROVIDER_DEFAULTS)}."
        )

    defaults = PROVIDER_DEFAULTS[provider]
    resolved_base_url = base_url or defaults.get("base_url")

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0.7,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415

        return ChatAnthropic(
            model=model,
            anthropic_api_key=api_key,
            temperature=0.7,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq  # noqa: PLC0415

        return ChatGroq(
            model=model,
            api_key=api_key,
            temperature=0.7,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama  # noqa: PLC0415

        return ChatOllama(
            model=model,
            base_url=resolved_base_url or "http://localhost:11434",
            temperature=0.7,
        )

    # Everything below uses the OpenAI-compatible ChatOpenAI
    if provider == "openai":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=0.7,
        )

    if provider == "openrouter":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=resolved_base_url or "https://openrouter.ai/api/v1",
            temperature=0.7,
            default_headers={
                "HTTP-Referer": "https://github.com/ravin-d-27/Commandor",
                "X-Title": "Commandor",
            },
        )

    if provider == "deepseek":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=resolved_base_url or "https://api.deepseek.com/v1",
            temperature=0.7,
        )

    if provider == "openai_compat":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        if not resolved_base_url:
            raise ValueError(
                "Provider 'openai_compat' requires a base_url "
                "(e.g. http://localhost:1234/v1 for LM Studio, "
                "or your custom endpoint)."
            )
        return ChatOpenAI(
            model=model,
            api_key=api_key or "not-required",
            base_url=resolved_base_url,
            temperature=0.7,
        )

    # Unreachable — guarded by the first check above
    raise ValueError(f"Unhandled provider: '{provider}'")
