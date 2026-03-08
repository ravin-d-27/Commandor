import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class ProviderConfig:
    """Configuration for a single provider"""

    enabled: bool = True
    api_key: Optional[str] = None
    default_model: str = ""


@dataclass
class AgentConfig:
    """Configuration for agent behavior"""

    max_iterations: int = 50
    max_tokens_per_response: int = 4096
    confirm_destructive: bool = True
    auto_scroll: bool = True


@dataclass
class UIConfig:
    """Configuration for UI appearance"""

    color_scheme: str = "auto"
    show_thinking: bool = True
    verbose: bool = True


@dataclass
class Config:
    """Main configuration class"""

    default_provider: str = "gemini"
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)
    agent: AgentConfig = field(default_factory=AgentConfig)
    ui: UIConfig = field(default_factory=UIConfig)


class ConfigManager:
    """Manages Commandor configuration"""

    DEFAULT_CONFIG = """# Commandor Configuration
# Generated on first run

default_provider: gemini

providers:
  gemini:
    enabled: true
    default_model: gemini-2.5-flash
    api_key: null

  anthropic:
    enabled: true
    default_model: claude-3.5-sonnet-20241022
    api_key: null

  openai:
    enabled: true
    default_model: gpt-4o
    api_key: null

  openrouter:
    enabled: true
    default_model: anthropic/claude-3.5-sonnet
    api_key: null

agent:
  max_iterations: 50
  max_tokens_per_response: 4096
  confirm_destructive: true
  auto_scroll: true

ui:
  color_scheme: auto
  show_thinking: true
  verbose: true
"""

    def __init__(self):
        self.config_dir = Path.home() / ".commandor"
        self.config_file = self.config_dir / "config"
        self.config: Optional[Config] = None
        self._load()

    def _load(self):
        """Load configuration from file"""
        if not self.config_file.exists():
            self._create_default()

        try:
            with open(self.config_file, "r") as f:
                data = yaml.safe_load(f)

            providers = {}
            if "providers" in data:
                for name, pdata in data["providers"].items():
                    providers[name] = ProviderConfig(**pdata)

            agent_data = data.get("agent", {})
            ui_data = data.get("ui", {})

            self.config = Config(
                default_provider=data.get("default_provider", "gemini"),
                providers=providers,
                agent=AgentConfig(**agent_data),
                ui=UIConfig(**ui_data),
            )
        except Exception as e:
            print(f"Error loading config: {e}")
            self._create_default()

    def _create_default(self):
        """Create default configuration"""
        self.config_dir.mkdir(exist_ok=True)
        with open(self.config_file, "w") as f:
            f.write(self.DEFAULT_CONFIG)

        # Set file permissions (Unix)
        if os.name != "nt":
            os.chmod(self.config_file, 0o600)

    def save(self):
        """Save configuration to file"""
        data = {
            "default_provider": self.config.default_provider,
            "providers": {
                name: {
                    "enabled": p.enabled,
                    "api_key": p.api_key,
                    "default_model": p.default_model,
                }
                for name, p in self.config.providers.items()
            },
            "agent": {
                "max_iterations": self.config.agent.max_iterations,
                "max_tokens_per_response": self.config.agent.max_tokens_per_response,
                "confirm_destructive": self.config.agent.confirm_destructive,
                "auto_scroll": self.config.agent.auto_scroll,
            },
            "ui": {
                "color_scheme": self.config.ui.color_scheme,
                "show_thinking": self.config.ui.show_thinking,
                "verbose": self.config.ui.verbose,
            },
        }

        with open(self.config_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def get_provider_config(self, name: str) -> Optional[ProviderConfig]:
        """Get configuration for a specific provider"""
        return self.config.providers.get(name)

    def set_provider_key(self, name: str, api_key: str):
        """Set API key for a provider"""
        if name in self.config.providers:
            self.config.providers[name].api_key = api_key
            self.save()

    def get_enabled_providers(self) -> list:
        """Get list of enabled provider names"""
        return [name for name, p in self.config.providers.items() if p.enabled]

    def set_default_provider(self, name: str):
        """Set the default provider"""
        if name in self.config.providers:
            self.config.default_provider = name
            self.save()

    @property
    def default_provider_config(self) -> ProviderConfig:
        """Get the default provider config"""
        return self.config.providers.get(self.config.default_provider, ProviderConfig())


# Global config instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get the global config manager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def load_config() -> Config:
    """Load and return the configuration"""
    return get_config().config


def setup_interactive():
    """Run interactive setup wizard"""
    config = get_config()

    print("\n" + "=" * 50)
    print("🔧 Commandor Setup Wizard")
    print("=" * 50)

    print("\nAvailable providers:")
    print("1. Google Gemini (gemini)")
    print("2. Anthropic Claude (anthropic)")
    print("3. OpenAI GPT (openai)")
    print("4. OpenRouter (openrouter)")

    # Set up each provider
    providers_info = {
        "gemini": ("Google Gemini", "GEMINI_API_KEY"),
        "anthropic": ("Anthropic Claude", "ANTHROPIC_API_KEY"),
        "openai": ("OpenAI", "OPENAI_API_KEY"),
        "openrouter": ("OpenRouter", "OPENROUTER_API_KEY"),
    }

    for key, (name, env_var) in providers_info.items():
        pconfig = config.get_provider_config(key)
        if pconfig:
            env_key = env_var
            api_key = os.environ.get(env_key)

            if not api_key:
                print(f"\n{name} API Key (optional, press Enter to skip):")
                print(f"  Get your key from the provider's website")
                api_key = input(f"  > ").strip()

            if api_key:
                pconfig.api_key = api_key
                pconfig.enabled = True
                print(f"  ✅ {name} configured")
            else:
                print(f"  ⏭️  {name} skipped (can be configured later)")

    # Set default provider
    print("\nSelect default provider:")
    enabled = config.get_enabled_providers()
    for i, p in enumerate(enabled, 1):
        print(f"  {i}. {p}")

    if enabled:
        try:
            choice = int(input(f"  Default [1]: ") or "1")
            if 1 <= choice <= len(enabled):
                config.config.default_provider = enabled[choice - 1]
        except ValueError:
            pass

    config.save()
    print("\n✅ Configuration saved!")
    print(f"   Config file: {config.config_file}")


# Environment variable helpers
def get_api_key(provider: str) -> Optional[str]:
    """Get API key from config, .env file, or environment variable"""
    config = get_config()
    pconfig = config.get_provider_config(provider)

    # First check YAML config
    if pconfig and pconfig.api_key:
        return pconfig.api_key

    # Check .env file in config directory (backward compatibility)
    config_dir = Path.home() / '.commandor'
    env_file = config_dir / '.env'
    
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Check for GEMINI_API_KEY or just GEMINI
                    if provider == 'gemini':
                        if line.startswith('GEMINI='):
                            key = line.split('=', 1)[1].strip().strip('"\'')
                            if key:
                                return key
                    elif line.startswith(f'{provider.upper()}_API_KEY='):
                        return line.split('=', 1)[1].strip().strip('"\'')
        except Exception:
            pass

    # Try environment variables
    env_map = {
        "gemini": "GEMINI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }

    return os.environ.get(env_map.get(provider, f"{provider.upper()}_API_KEY"))
