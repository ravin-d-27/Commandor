# Commandor - Agentic CLI

<p align="center">
  <img src="assets/logo.png" alt="Commandor" width="200"/>
</p>

Commandor is an **Agentic CLI** (similar to OpenCode or Codex CLI) that uses AI to autonomously accomplish coding tasks. It can read, write, edit files, run commands, and complete multi-step tasks.

[![GitHub stars](https://img.shields.io/github/stars/ravin-d-27/Commandor?style=social)](https://github.com/ravin-d-27/Commandor/stargazers)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://python.org)

---

## Key Features

### Agent Modes
- **`/agent`** - Autonomous mode: Agent executes tasks without asking for confirmation
- **`/assist`** - Assist mode: Agent asks for confirmation before each action
- **`/plan`** - Plan mode: Generate plan first, then execute (review before run)
- **`/chat`** - Chat mode: Ask questions without executing actions

### Multi-Provider Support
- **Google Gemini** - gemini-2.5-flash, gemini-1.5-pro
- **Anthropic Claude** - claude-3.5-sonnet, claude-3-opus
- **OpenAI GPT** - gpt-4o, gpt-4-turbo, gpt-3.5-turbo
- **OpenRouter** - Access to 100+ models

### Tools
- **File Operations**: Read, Write, Edit files
- **Search**: Glob, Grep for finding files and content
- **Shell**: Run commands, list directories
- **Project**: Git info, project files, environment info
- **Session Management**: Save, resume, and manage sessions
- **API Management**: Configure providers and models
- **Rich Markdown Rendering**: AI responses with enhanced formatting

---

## Installation

### From PyPI (Recommended)
```bash
pip install commandor-ai
```

### From Source
```bash
git clone https://github.com/ravin-d-27/Commandor.git
cd Commandor
pip install -e .
```

### Set Up API Keys

Run the interactive setup:
```bash
commandor --setup
```

Or set environment variables:
```bash
# Google Gemini
export GEMINI_API_KEY=your_key

# Anthropic Claude  
export ANTHROPIC_API_KEY=your_key

# OpenAI
export OPENAI_API_KEY=your_key

# OpenRouter
export OPENROUTER_API_KEY=your_key
```

---

## Usage

### Interactive Mode
```bash
commandor
```

### Command Line Mode

#### Autonomous Agent
```bash
commandor -a "fix the bug in main.py"
commandor --agent "add tests for auth module"
```

#### Assist Mode (with confirmations)
```bash
commandor --assist "create a new feature"
```

#### Chat Mode (Q&A only)
```bash
commandor --chat "what is async/await in Python?"
```

---

## Available Commands

### In Interactive Terminal

| Command | Description |
|---------|-------------|
| `/agent <task>` | Run autonomous agent |
| `/assist <task>` | Run with confirmations |
| `/plan <task>` | Plan then execute (review before run) |
| `/chat <question>` | Ask AI questions |
| `/ai <instruction>` | Convert natural language to shell command |
| `/ask <question>` | Ask AI any question directly |
| `/provider <name>` | Switch AI provider |
| `/providers` | List available providers |
| `/modes` | Show agent modes |
| `/setup` | Run interactive setup |
| `/test-providers` | Test all configured providers |
| `/help` | Show help |
| `/info` | Show system information |
| `/history` | Show recent command history |
| `/ask-history` | Show your question history |
| `/ask-search <term>` | Search your question history |
| `/clear` | Clear the screen |
| `/config` | Show configuration info |
| `/reset-api` | Reset and reconfigure API key |
| `/test-api` | Test current API key |
| `/api` | Show API key status table |
| `/api set <provider> <key>` | Set API key for a provider |
| `/api model <provider> <model>` | Set default model for a provider |
| `/api test [provider]` | Test one or all providers |
| `/api remove <provider>` | Remove a provider's API key |
| `/api default <provider>` | Set default provider |
| `/sessions` | List saved sessions |
| `/sessions save <name>` | Name the current session |
| `/sessions new <name>` | Start a fresh named session |
| `/sessions resume <name>` | Switch to a saved session |
| `/sessions rename <old> <new>` | Rename a session |
| `/sessions delete <name>` | Delete a session |
| `/exit` | Exit |

---

## Configuration

Config file: `~/.commandor/config`

```yaml
default_provider: openrouter

providers:
  gemini:
    enabled: true
    default_model: gemini-2.5-flash
  
  anthropic:
    enabled: true  
    default_model: claude-3.5-sonnet-20241022
  
  openai:
    enabled: true
    default_model: gpt-4o
  
  openrouter:
    enabled: true
    default_model: anthropic/claude-3.5-sonnet

agent:
  max_iterations: 50
  confirm_destructive: true
```

---

## Examples

### Agent Mode Examples
```bash
commandor > /agent fix all TypeScript errors in src/
commandor > /agent add error handling to auth.py
commandor > /agent create a README.md for this project
```

### Assist Mode Examples
```bash
commandor > /assist create a new React component
commandor > /assist refactor this function
```

### Shell Commands
```bash
commandor > /ai list all python files recursively
commandor > /ai find files larger than 100MB
commandor > /ai show disk usage
```

---

## Docker Usage

```bash
# Pull the image
docker pull ravind2704/commandor

# Run
docker run -it ravind2704/commandor

# With API keys
docker run -it -e OPENAI_API_KEY=your_key ravind2704/commandor
```

---

## Project Structure

```
commandor/
├── commandor/
│   ├── __init__.py
│   ├── __main__.py       # CLI entry point
│   ├── main.py           # Legacy entry
│   ├── terminal.py       # Interactive terminal
│   ├── config.py         # Configuration management
│   ├── providers/        # AI providers
│   │   ├── base.py
│   │   ├── factory.py
│   │   ├── gemini.py
│   │   ├── anthropic.py
│   │   ├── openai.py
│   │   └── openrouter.py
│   ├── agent/            # Agent system
│   │   ├── agent.py
│   │   ├── tools.py
│   │   ├── modes.py
│   │   ├── executor.py
│   │   └── prompts.py
│   └── utils/           # Utilities
│       ├── file_ops.py
│       └── shell.py
├── pyproject.toml
├── setup.py
└── README.md
```

---

## Requirements

- Python 3.9+
- API key for at least one AI provider

---

## Troubleshooting

**Command not found**
- Confirm installation: `pip show commandor-ai`
- Check PATH or activate virtual environment

**API Key errors**
- Run `commandor --setup` to configure
- Or set environment variables
- Test with `/test-providers` in interactive mode

**Need help?**
- Check `/help` in interactive terminal
- Report issues at https://github.com/ravin-d-27/Commandor/issues

---

## Contributing

1. Star the repository
2. Report bugs and request features via GitHub Issues
3. Submit pull requests with improvements
4. Follow code conventions and include tests

---

## License

MIT License - see [LICENSE](LICENSE)

---

## Author

Created by **Ravin D**

- GitHub: https://github.com/ravin-d-27
- Email: ravin.d3107@outlook.com

---

**Version:** 0.2.0
**Status:** Actively maintained
