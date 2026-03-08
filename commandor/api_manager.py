"""Comprehensive API-key and provider management for Commandor.

Public API:
    APIManager              — class; instantiate once, call methods as needed
    APIManager.show_status()             → Rich table of all providers
    APIManager.set_key(provider, key)    → save API key to config
    APIManager.remove_key(provider)      → clear API key from config
    APIManager.set_model(provider, model)→ set default model for provider
    APIManager.set_default(provider)     → set as active default provider
    APIManager.test_provider(provider)   → live connectivity check (LLM ping)
    APIManager.test_all()                → test all providers and print summary

Usage from the terminal:
    /api                            → show provider table
    /api set <provider> <key>       → set API key
    /api model <provider> <model>   → set default model
    /api test <provider>            → test one provider
    /api test                       → test all providers
    /api remove <provider>          → remove API key
    /api default <provider>         → set default provider
"""

from __future__ import annotations

from typing import Optional

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .config import get_api_key, get_config

# ---------------------------------------------------------------------------
# Provider metadata
# ---------------------------------------------------------------------------

PROVIDERS = ["gemini", "anthropic", "openai", "openrouter"]

_DISPLAY_NAMES = {
    "gemini":     "Google Gemini",
    "anthropic":  "Anthropic Claude",
    "openai":     "OpenAI",
    "openrouter": "OpenRouter",
}

_ENV_VARS = {
    "gemini":     "GEMINI_API_KEY",
    "anthropic":  "ANTHROPIC_API_KEY",
    "openai":     "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

_DEFAULT_MODELS = {
    "gemini":     "gemini-2.5-flash",
    "anthropic":  "claude-3.5-sonnet-20241022",
    "openai":     "gpt-4o",
    "openrouter": "anthropic/claude-3.5-sonnet",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mask_key(key: str) -> str:
    """Return a masked version: first 4 chars + '...' + last 4 chars."""
    if not key:
        return "—"
    if len(key) <= 10:
        return "*" * len(key)
    return key[:4] + "..." + key[-4:]


def _validate_provider(name: str, console: Console) -> bool:
    """Print an error and return False if *name* is not a known provider."""
    if name not in PROVIDERS:
        console.print(
            f"[red]Unknown provider: [bold]{name}[/bold]. "
            f"Valid options: {', '.join(PROVIDERS)}[/red]"
        )
        return False
    return True


# ---------------------------------------------------------------------------
# APIManager
# ---------------------------------------------------------------------------

class APIManager:
    """Manages API keys, default models, and provider connectivity."""

    def __init__(self) -> None:
        self._console = Console()

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def show_status(self) -> None:
        """Print a Rich table summarising all providers."""
        cfg = get_config()
        default_provider = cfg.config.default_provider if cfg.config else "gemini"

        table = Table(
            title="[bold]API Providers[/bold]",
            border_style="blue",
            show_lines=True,
            highlight=True,
        )
        table.add_column("Provider",      style="bold cyan",  no_wrap=True)
        table.add_column("Display Name",  style="dim")
        table.add_column("Status",        no_wrap=True)
        table.add_column("Key",           no_wrap=True)
        table.add_column("Default Model", style="dim", overflow="fold")
        table.add_column("",              no_wrap=True)  # default marker

        for name in PROVIDERS:
            pconfig = cfg.get_provider_config(name)
            key = get_api_key(name)

            if key:
                status = "[green]✓ set[/green]"
                masked = f"[dim]{_mask_key(key)}[/dim]"
            else:
                status = "[red]✗ none[/red]"
                masked = "[dim]—[/dim]"

            model = (pconfig.default_model if pconfig and pconfig.default_model
                     else _DEFAULT_MODELS.get(name, "—"))
            is_default = "[yellow]★ default[/yellow]" if name == default_provider else ""

            table.add_row(
                name,
                _DISPLAY_NAMES.get(name, name),
                status,
                masked,
                model,
                is_default,
            )

        self._console.print()
        self._console.print(table)
        self._console.print()

        # Quick-reference command hints
        hints = Text(justify="left")
        hints.append("Commands: ", style="dim")
        cmds = [
            "/api set <provider> <key>",
            "/api model <provider> <model>",
            "/api test [provider]",
            "/api remove <provider>",
            "/api default <provider>",
        ]
        hints.append(" • ".join(cmds), style="dim cyan")
        self._console.print(hints)
        self._console.print()

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def set_key(self, provider: str, key: str) -> None:
        """Save *key* as the API key for *provider*."""
        if not _validate_provider(provider, self._console):
            return
        if not key.strip():
            self._console.print("[red]API key cannot be empty.[/red]")
            return
        cfg = get_config()
        cfg.set_provider_key(provider, key.strip())
        masked = _mask_key(key.strip())
        self._console.print(
            f"[green]✓ API key saved for [bold]{provider}[/bold]  ({masked})[/green]"
        )

    def remove_key(self, provider: str) -> None:
        """Clear the stored API key for *provider*."""
        if not _validate_provider(provider, self._console):
            return
        cfg = get_config()
        existing = get_api_key(provider)
        if not existing:
            self._console.print(
                f"[yellow]No API key configured for [bold]{provider}[/bold] — nothing to remove.[/yellow]"
            )
            return
        cfg.remove_provider_key(provider)
        self._console.print(
            f"[yellow]API key removed for [bold]{provider}[/bold].[/yellow]"
        )

    def set_model(self, provider: str, model: str) -> None:
        """Set the default model for *provider*."""
        if not _validate_provider(provider, self._console):
            return
        if not model.strip():
            self._console.print("[red]Model name cannot be empty.[/red]")
            return
        cfg = get_config()
        cfg.set_provider_model(provider, model.strip())
        self._console.print(
            f"[green]✓ Default model for [bold]{provider}[/bold] set to: [cyan]{model.strip()}[/cyan][/green]"
        )

    def set_default(self, provider: str) -> None:
        """Set *provider* as the active default provider."""
        if not _validate_provider(provider, self._console):
            return
        cfg = get_config()
        cfg.set_default_provider(provider)
        self._console.print(
            f"[green]✓ Default provider set to: [bold]{provider}[/bold][/green]"
        )

    # ------------------------------------------------------------------
    # Connectivity tests
    # ------------------------------------------------------------------

    def test_provider(self, provider: str) -> bool:
        """Test connectivity for a single *provider*.  Returns True on success."""
        if not _validate_provider(provider, self._console):
            return False

        self._console.print(
            f"  Testing [bold cyan]{provider}[/bold cyan]...", end=" "
        )

        key = get_api_key(provider)
        if not key:
            self._console.print("[red]✗  No API key configured[/red]")
            return False

        try:
            from .agent.lc_models import build_model  # noqa: PLC0415

            cfg = get_config()
            pconfig = cfg.get_provider_config(provider)
            model = (
                pconfig.default_model
                if pconfig and pconfig.default_model
                else _DEFAULT_MODELS.get(provider, "")
            )
            llm = build_model(provider, key, model)
            llm.invoke("ping")
            self._console.print("[green]✓  OK[/green]")
            return True

        except Exception as exc:
            err = str(exc).lower()
            if any(kw in err for kw in ("authentication", "api key", "invalid", "unauthorized")):
                self._console.print("[red]✗  Invalid API key[/red]")
            else:
                # Show a short version of the error
                short = str(exc)[:120]
                self._console.print(f"[red]✗  Error: {short}[/red]")
            return False

    def test_all(self) -> dict[str, bool]:
        """Test all providers and print a summary table.  Returns a dict of results."""
        self._console.print("\n[bold]Testing all providers...[/bold]\n")
        results: dict[str, bool] = {}
        for name in PROVIDERS:
            results[name] = self.test_provider(name)
        self._console.print()

        ok = sum(1 for v in results.values() if v)
        total = len(results)
        colour = "green" if ok == total else ("yellow" if ok > 0 else "red")
        self._console.print(
            f"[{colour}]{ok}/{total} provider(s) healthy.[/{colour}]"
        )
        return results
