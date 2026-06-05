"""Tests for commandor.config.

These tests pin the env via :func:`isolated_config` (see conftest) so
they don't touch the user's real ``~/.commandor`` config.
"""
import os

import pytest

from commandor.config import (
    ConfigManager,
    ProviderConfig,
    get_api_key,
)


class TestProviderConfigDataclass:
    def test_defaults(self):
        p = ProviderConfig()
        assert p.enabled is True
        assert p.api_key is None
        assert p.default_model == ""
        assert p.base_url is None

    def test_full(self):
        p = ProviderConfig(
            enabled=False,
            api_key="x",
            default_model="gpt-4o",
            base_url="https://example.com/v1",
        )
        assert p.base_url == "https://example.com/v1"


class TestConfigManager:
    def test_first_run_creates_default(self, isolated_config):
        cm = ConfigManager()
        # Default file should now exist
        assert cm.config_file.exists()
        # Should have at least the four original providers
        names = list(cm.config.providers.keys())
        assert "gemini" in names
        assert "anthropic" in names
        assert "openai" in names
        assert "openrouter" in names

    def test_set_provider_key(self, isolated_config):
        cm = ConfigManager()
        cm.set_provider_key("gemini", "test-key-12345")
        assert cm.get_provider_config("gemini").api_key == "test-key-12345"

    def test_set_provider_model(self, isolated_config):
        cm = ConfigManager()
        cm.set_provider_model("gemini", "gemini-2.5-pro")
        assert cm.get_provider_config("gemini").default_model == "gemini-2.5-pro"

    def test_set_provider_base_url(self, isolated_config):
        cm = ConfigManager()
        cm.set_provider_base_url("openai", "https://my-proxy.example/v1")
        assert cm.get_provider_config("openai").base_url == "https://my-proxy.example/v1"

    def test_set_base_url_clears_with_empty_string(self, isolated_config):
        cm = ConfigManager()
        cm.set_provider_base_url("openai", "https://x")
        cm.set_provider_base_url("openai", "")
        assert cm.get_provider_config("openai").base_url is None

    def test_remove_provider_key(self, isolated_config):
        cm = ConfigManager()
        cm.set_provider_key("gemini", "abc")
        cm.remove_provider_key("gemini")
        assert cm.get_provider_config("gemini").api_key is None

    def test_set_default_provider(self, isolated_config):
        cm = ConfigManager()
        cm.set_default_provider("anthropic")
        assert cm.config.default_provider == "anthropic"

    def test_get_enabled_providers(self, isolated_config):
        cm = ConfigManager()
        enabled = cm.get_enabled_providers()
        # All defaults have enabled: true
        assert "gemini" in enabled
        assert "anthropic" in enabled

    def test_set_unknown_provider_model_creates_entry(self, isolated_config):
        cm = ConfigManager()
        cm.set_provider_model("brand-new", "model-x")
        assert cm.get_provider_config("brand-new").default_model == "model-x"


class TestGetApiKey:
    def test_returns_yaml_value_first(self, isolated_config, monkeypatch):
        cm = ConfigManager()
        cm.set_provider_key("gemini", "yaml-key")
        monkeypatch.setenv("GEMINI_API_KEY", "env-key")
        assert get_api_key("gemini") == "yaml-key"  # yaml wins

    def test_falls_back_to_env(self, isolated_config, monkeypatch):
        # Don't set yaml key
        ConfigManager()  # trigger creation
        monkeypatch.setenv("OPENAI_API_KEY", "env-only")
        assert get_api_key("openai") == "env-only"

    def test_falls_back_to_env_for_new_providers(self, isolated_config, monkeypatch):
        ConfigManager()
        monkeypatch.setenv("GROQ_API_KEY", "g-12345")
        assert get_api_key("groq") == "g-12345"
        monkeypatch.setenv("DEEPSEEK_API_KEY", "d-12345")
        assert get_api_key("deepseek") == "d-12345"

    def test_returns_none_if_nowhere_set(self, isolated_config, monkeypatch):
        ConfigManager()
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        # yaml is also None
        assert get_api_key("gemini") is None
