# Commandor

<p align="center">
  <img src="assets/logo.png" alt="Commandor" width="200"/>
</p>

<h3 align="center">🤖 Agentic CLI — Autonomous Coding Assistant</h3>

<p align="center">
  <strong>AI-powered terminal assistant</strong> that autonomously implements features, fixes bugs, refactors code, writes tests, and manages files — all from a single unified terminal interface.
</p>

[![GitHub stars](https://img.shields.io/github/stars/ravin-d-27/Commandor?style=social)](https://github.com/ravin-d-27/Commandor/stargazers)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-ReAct-blue)](https://langchain-ai.github.io/langgraph/)
[![Textual](https://img.shields.io/badge/Textual-TUI-green)](https://textual.textualize.io/)

---

## ✨ Why Commandor?

Traditional AI coding assistants work as separate tools — you switch contexts between your editor, terminal, and chat window. **Commandor** brings the AI directly into your terminal as a **first-class citizen**, capable of:

- 🚀 **Autonomous execution** — Describe a task, watch it get done
- 🔧 **Full tool access** — Read, write, edit, search, run commands
- 💾 **Persistent sessions** — Conversations survive restarts
- 🎯 **Smart context** — Auto-summarizes long conversations, tracks token usage
- 🛡️ **Safety first** — Dangerous operations flagged, human-in-the-loop mode
- 🌈 **Beautiful TUI** — Modern Textual interface with real-time streaming

Built on **LangGraph** for robust agent orchestration and **Textual** for a rich terminal experience.

---

## 🎯 Agent Modes

Commandor offers four distinct interaction modes, each optimized for different workflows:

| Mode | Command | Description |
|------|---------|-------------|
| **Autonomous** | `/agent <task>` | The AI works independently, using all tools freely until the task is complete. Best for straightforward tasks. |
| **Assist** | `/assist <task>` | Human-in-the-loop: The AI proposes actions and asks for your confirmation before executing each tool. Perfect for learning or high-stakes changes. |
| **Plan** | `/plan <task>` | Two-phase: First, the AI generates a numbered plan for your review. You can accept, edit, or reject it before execution begins. Great for complex refactors. |
| **Chat** | `/chat <message>` or `/ask` | Pure conversation — no tool access. Use for questions, explanations, code reviews, or brainstorming. |

---

## 🧠 Intelligent Context Management

### @File References
Inline file contents directly into your prompts without manual copying:

```bash
/agent refactor this function: @src/utils.py
/agent write tests for @app/models.py
/chat explain @Dockerfile
```

Supports glob patterns too:
```bash
/agent fix all type errors in @**/*.py
```

### Persistent Sessions
- **Auto-save**: Every conversation is automatically saved with a unique thread ID
- **Name & organize**: Use `/sessions save <name>` to name important sessions
- **Resume later**: `/sessions resume <name>` continues where you left off
- **Multiple sessions**: Keep separate contexts for different projects or tasks
- **Checkpoint storage**: Uses SQLite (`~/.commandor/checkpoints.db`) for durability

### Real-time Metrics
Watch token usage and performance as you work:
- Context window usage (with visual progress bar)
- Input/output token counts
- Context condensation events (when history is summarized to save space)
- Model name and execution time

---

## 🤖 Multi-Provider Support

Commandor works with the leading AI providers. Configure one or all:

| Provider | Models | Setup |
|----------|--------|-------|
| **Google Gemini** | `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-1.5-pro`, `gemini-1.5-flash` | `GEMINI_API_KEY` |
| **Anthropic Claude** | `claude-3-5-sonnet-20241022`, `claude-3-7-sonnet-20250219`, `claude-3-opus-20240229`, `claude-3-5-haiku-20241022` | `ANTHROPIC_API_KEY` |
| **OpenAI GPT** | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `o1`, `o3-mini` | `OPENAI_API_KEY` |
| **OpenRouter** | 100+ models (including `anthropic/claude-3.5-sonnet`, `google/gemini-2.5-pro`) | `OPENROUTER_API_KEY` |

Switch providers on the fly with `/provider <name>` and models with `/model <id>`.

---

## 🔧 Built-in Tools

The agent has access to a comprehensive toolkit for software development:

### File Operations
- **`read_file_tool`** — Read files with optional line ranges
- **`write_file_tool`** — Create or overwrite files (with diff preview)
- **`edit_file_tool`** — Surgical string replacement (preserves formatting)
- **`patch_file_tool`** — Apply unified diffs (uses `patch` command or pure-Python fallback)

### Search & Discovery
- **`glob_tool`** — Find files by pattern (e.g., `**/*.py`, `*.ts`)
- **`grep_tool`** — Search file contents with regex
- **`list_directory_tool`** — Explore directory structure
- **`get_project_files_tool`** — List all source files by extension

### Shell & System
- **`run_command_tool`** — Execute shell commands (with timeout protection)
- **`cd_tool`** — Change working directory (native support, updates prompt)
- **`get_directory_tool`** — Get current working directory
- **`get_git_info_tool`** — Git status, branch, recent commits
- **`get_environment_tool`** — OS, Python version, shell, user info

### Session & Project
- **`get_project_files_tool`** — Enumerate project source files
- Session management via `/sessions` commands (see below)

All tools include **rich diff displays** when modifying files, so you always see exactly what changed.

---

## 📦 Installation

### Prerequisites
- Python 3.9 or higher
- API key from at least one supported provider (Gemini, Anthropic, OpenAI, or OpenRouter)

### From PyPI (Recommended)
```bash
pip install commandor-ai
```

### From Source (Development)
```bash
git clone https://github.com/ravin-d-27/Commandor.git
cd Commandor
pip install -e .
```

### Optional Dependencies
For enhanced experience, install additional packages:
```bash
pip install commandor-ai[dev]  # Testing & linting tools
```

On Windows, `pyreadline3` is automatically installed for better command-line editing.

---

## 🔑 API Key Setup

### Interactive Setup (Recommended)
Launch Commandor and run the setup wizard:
```bash
commandor
/setup
```

The wizard will:
1. List available providers
2. Prompt for API keys (or skip if you'll use environment variables)
3. Let you choose a default provider
4. Save everything to `~/.commandor/config`

### Manual Configuration
Edit the config file directly:
```bash
# Create the config directory
mkdir -p ~/.commandor

# Edit config
nano ~/.commandor/config
```

Example config:
```yaml
default_provider: openrouter

providers:
  gemini:
    enabled: true
    api_key: null  # Will fall back to GEMINI_API_KEY env var
    default_model: gemini-2.5-flash
  
  anthropic:
    enabled: true
    api_key: "your-key-here"  # Can store directly (file protected at 600)
    default_model: claude-3.5-sonnet-20241022
  
  openai:
    enabled: true
    api_key: null
    default_model: gpt-4o
  
  openrouter:
    enabled: true
    api_key: null
    default_model: anthropic/claude-3.5-sonnet

agent:
  max_iterations: 50
  max_tokens_per_response: 4096
  confirm_destructive: true
  auto_scroll: true

ui:
  color_scheme: auto
  show_thinking: true
  verbose: true
```

### Environment Variables
You can also set API keys via environment variables (takes precedence over config file):

```bash
export GEMINI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
export OPENROUTER_API_KEY="your-key"
```

---

## 🚀 Usage

### Interactive Terminal (TUI)
Launch the full Textual UI:
```bash
commandor
```

Features:
- Single-pane terminal: shell commands and AI chat coexist
- Real-time streaming of AI responses and tool outputs
- Command history (↑/↓)
- Tab completion for slash commands
- Rich syntax highlighting and markdown rendering

**Quick start:**
```bash
# Run a shell command
ls -la

# Ask a question
/chat what's the difference between async/await and threads?

# Autonomous task
/agent refactor this codebase to use type hints

# Use file references
/agent write tests for @src/main.py
```

### Command-Line Mode (Non-Interactive)
Run a single task without entering the TUI:

```bash
# Autonomous agent
commandor -a "fix the bug in main.py"
commandor --agent "add comprehensive tests for the auth module"

# Assist mode (with confirmations)
commandor --assist "migrate from SQLite to PostgreSQL"

# Plan mode
commandor --plan "design a new authentication system"

# Chat mode
commandor --chat "explain how LangGraph works"
```

Options:
- `-p, --provider <name>` — Override the default provider
- `-m, --model <id>` — Use a specific model
- `--setup` — Run the interactive configuration wizard
- `--version` — Show version information

Examples with provider/model selection:
```bash
commandor -a "review this PR" -p anthropic -m claude-3-7-sonnet-20250219
commandor --chat "explain quantum computing" -p openai -m o1
```

---

## ⌨️ Command Reference

### AI Commands

| Command | Mode | Description |
|---------|------|-------------|
| `/agent <task>` | Autonomous | Execute task independently using all tools |
| `/assist <task>` | Assist | Execute with confirmation before each tool call |
| `/plan <task>` | Plan | Generate a plan, review, then execute |
| `/chat <message>` | Chat | Conversational Q&A (no tools) |
| `/ask <question>` | Chat | Alias for `/chat` |
| `/retry` | Any | Re-run the last AI command |
| `/reset` | Any | Clear conversation memory, start fresh session |

### Provider & Model Management

| Command | Description |
|---------|-------------|
| `/providers` | List all providers with configuration status |
| `/provider <name>` | Switch active provider (gemini, anthropic, openai, openrouter) |
| `/model <id>` | Set model for current provider (e.g., `claude-3-7-sonnet-20250219`) |

### Session Management

| Command | Description |
|---------|-------------|
| `/sessions` | List all saved sessions with metadata |
| `/sessions save <name>` | Name the current session |
| `/sessions new <name>` | Create fresh named session and switch to it |
| `/sessions resume <name>` | Switch to a saved session (loads its conversation history) |
| `/sessions rename <old> <new>` | Rename a session |
| `/sessions delete <name>` | Delete a session and its checkpoints |

### Configuration & Help

| Command | Description |
|---------|-------------|
| `/setup` | Interactive API key configuration wizard |
| `/setup <provider>` | Configure a specific provider (e.g., `/setup anthropic`) |
| `/help` | Show comprehensive help with all commands |
| `/clear` or `Ctrl+L` | Clear the terminal screen |
| `/exit` or `Ctrl+Q` | Exit Commandor |

### Export & Utilities

| Command | Description |
|---------|-------------|
| `/export [filename]` | Save conversation as Markdown (default: `commandor-YYYYMMDD-HHMMSS.md`) |

---

### Shell Commands

Any input that **doesn't start with `/`** is executed as a shell command in the current working directory.

Special handling:
- `cd <path>` — Changes the working directory natively (no subprocess). Supports `~`, relative paths, and environment variable expansion.
- All other commands run in your default shell (`$SHELL` or `/bin/bash`)

Examples:
```bash
# Navigate
cd ~/projects/myapp

# Git operations
git status
git diff HEAD~1

# Package managers
npm install
pip install -r requirements.txt

# Build & test
pytest tests/
python -m pytest --cov

# Project exploration
find . -name "*.py" | head -20
ls -R | grep ".js"
```

---

## 🎨 User Interface

### Visual Design
- **Theme**: Batman-inspired dark mode (black background, gold accents)
- **Layout**: Single-pane terminal with input at bottom
- **Streaming**: Real-time token-by-token response rendering
- **Panels**: 
  - Status bar (top): provider, model, context usage, session name
  - Log area (center): conversation history, tool outputs, errors
  - Stream preview (bottom, temporary): live "thinking" indicator

### Key Bindings
| Key | Action |
|-----|--------|
| `↑ / ↓` | Navigate command history |
| `Tab` | Auto-complete slash commands |
| `Ctrl+L` | Clear screen |
| `Ctrl+Q` | Quit |

### Context Window Bar
The status bar displays context usage with a visual progress bar:
```
▓▓▓▓▓░░░░ 12.3k/128k (9%)  ← 12.3k tokens used of 128k limit
```
- Automatically detects model context limits
- Shows percentage of context window used
- Updates in real-time as conversation grows

When usage exceeds 80% of the context window, Commandor **automatically summarizes** the conversation history to free up space (you'll see a small `↻ context condensed` indicator).

---

## ⚙️ Configuration

### Config File Location
- **Linux/macOS**: `~/.commandor/config`
- **Windows**: `%USERPROFILE%\.commandor\config`

### Configuration Schema

```yaml
# Default provider (gemini, anthropic, openai, openrouter)
default_provider: openrouter

# Provider-specific settings
providers:
  gemini:
    enabled: true              # Enable/disable this provider
    api_key: null             # null = use GEMINI_API_KEY env var
    default_model: gemini-2.5-flash
  
  anthropic:
    enabled: true
    api_key: null             # or set directly (file permissions: 600)
    default_model: claude-3.5-sonnet-20241022
  
  openai:
    enabled: true
    api_key: null
    default_model: gpt-4o
  
  openrouter:
    enabled: true
    api_key: null
    default_model: anthropic/claude-3.5-sonnet

# Agent behavior
agent:
  max_iterations: 50          # Maximum tool calls per task
  max_tokens_per_response: 4096  # Max tokens per LLM response
  confirm_destructive: true   # Always ask before rm, drop_db, etc.
  auto_scroll: true           # Auto-scroll log during streaming

# UI settings
ui:
  color_scheme: auto          # auto/dark/light (Textual theme)
  show_thinking: true         # Show AI reasoning blocks
  verbose: true               # Show detailed tool output
```

### Precedence Order for API Keys
1. **Config file** (`api_key` field) — if set and non-null
2. **Environment variable** — `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, etc.
3. **`.env` file** — Legacy support: `~/.commandor/.env`
4. **None** — Provider will be marked as unconfigured

---

## 📦 Docker Support

### Pull the Image
```bash
docker pull ravind2704/commandor:latest
```

### Run Interactively
```bash
docker run -it ravind2704/commandor
```

### With API Keys (Recommended)
```bash
docker run -it \
  -e GEMINI_API_KEY=your_key \
  -e ANTHROPIC_API_KEY=your_key \
  -e OPENAI_API_KEY=your_key \
  -e OPENROUTER_API_KEY=your_key \
  ravind2704/commandor
```

### Mount Your Project
```bash
# Mount current directory into container
docker run -it \
  -v $(pwd):/workspace \
  -w /workspace \
  -e OPENAI_API_KEY=your_key \
  ravind2704/commandor
```

### Build from Source
```bash
docker build -t commandor .
docker run -it commandor
```

---

## 🏗️ Project Structure

```
Commandor/
├── commandor/                    # Main package
│   ├── __init__.py               # Package metadata
│   ├── __main__.py               # CLI entry point (argparse, TUI launcher)
│   ├── main.py                   # Legacy terminal entry (kept for compatibility)
│   ├── textual_app.py            # Textual TUI application
│   ├── agent_bridge.py           # Streaming event bridge (TUI ↔ LangGraph)
│   ├── config.py                 # ConfigManager, setup wizard, API key resolution
│   ├── api_manager.py            # (deprecated — functionality moved to config.py)
│   ├── session_manager.py        # Named session persistence (JSON registry)
│   │
│   ├── agents/                   # **Note: directory is `agent/` (singular)**
│   │   ├── __init__.py
│   │   ├── executor.py           # run_agent(), _run_* mode runners, metrics
│   │   ├── lc_graph.py           # LangGraph factory (build_agent_graph, etc.)
│   │   ├── lc_models.py          # build_model() — provider model factory
│   │   ├── lc_tools.py           # All @tool-decorated functions
│   │   ├── modes.py              # Mode descriptions
│   │   └── prompts.py            # (if exists) Additional prompt templates
│   │
│   ├── providers/                # AI provider integrations
│   │   ├── __init__.py
│   │   ├── base.py               # AgentResult dataclass, provider base
│   │   ├── factory.py            # Provider factory (if exists)
│   │   ├── gemini.py             # Gemini-specific logic
│   │   ├── anthropic.py          # Anthropic-specific logic
│   │   ├── openai.py             # OpenAI-specific logic
│   │   └── openrouter.py         # OpenRouter-specific logic
│   │
│   ├── utils/                    # Utility modules
│   │   ├── __init__.py
│   │   ├── file_ops.py           # Low-level file read/write/edit/patch
│   │   ├── shell.py              # Shell execution, cd, git, env info
│   │   └── diff_display.py       # Rich diff rendering for file changes
│   │
│   └── widgets/                  # Textual UI components
│       ├── __init__.py
│       ├── terminal_widget.py    # Main unified terminal (shell + AI)
│       └── chat_panel.py         # (if exists) Alternative chat UI
│
├── tests/                        # Test suite (if exists)
├── pyproject.toml                # Modern Python packaging
├── setup.py                      # Legacy setuptools (still used for install)
├── requirements.txt              # Dev dependencies (optional)
├── Dockerfile                    # Container image definition
├── LICENSE                       # MIT License
└── README.md                     # This file
```

### Key Architecture Insights

**LangGraph Integration:**
- Uses `create_react_agent()` from LangGraph for ReAct pattern
- Checkpointer: `SqliteSaver` at `~/.commandor/checkpoints.db` for persistence
- Thread IDs scoped by mode: `{mode}_{uuid}` to separate chat/agent/plan histories

**Streaming Pipeline:**
1. `terminal_widget.py` → `_run_ai()` → spawns worker
2. Worker calls `agent_bridge.stream_agent_events()`
3. `stream_agent_events()` builds LLM, constructs graph, calls `_iter_graph()`
4. Events (`TokenEvent`, `ToolCallEvent`, etc.) yielded back to UI
5. `TerminalWidget._on_ai_event()` renders each event type

**Context Summarization:**
- Hook `_make_summarize_hook()` runs before each LLM call
- Checks `_approx_tokens(messages)` against threshold (80% of context window)
- If exceeded, summarizes old messages into a single `HumanMessage` with summary
- Prevents context overflow while preserving key information

---

## 🧪 Examples

### Basic File Operations
```bash
# Read a file
/chat show me the contents of @commandor/config.py

# Create a new module
/agent create a new module @utils/helpers.py with functions for validation

# Edit a file
/agent in @app/main.py, replace the print statement with proper logging

# Apply a patch
/agent apply this diff to @src/components/Button.tsx:
# --- a/src/components/Button.tsx
# +++ b/src/components/Button.tsx
# @@ -10,7 +10,7 @@
# -  return <button className="btn">{children}</button>
# +  return <button className="btn primary">{children}</button>
```

### Project Exploration
```bash
# Find all test files
/agent find all test files in the project

# Search for a function
/chat where is the authenticate_user function defined?

# Understand architecture
/plan analyze the project structure and document the main components
```

### Shell + AI Hybrid
```bash
# Check git status first
git status

# Then ask AI to fix conflicts
/agent resolve the git conflicts in @src/auth.py

# Run tests, then fix failures
pytest tests/ -v
/agent fix the failing tests and re-run
```

### Complex Refactoring with Plan Mode
```bash
/plan refactor the user authentication system to use JWT tokens

# AI will output a plan like:
# 1. Read current auth implementation (read_file_tool)
# 2. Identify user model and login flow
# 3. Design JWT integration strategy
# 4. Add JWT secret to config
# 5. Implement token generation in login endpoint
# ...

# You review, edit if needed, then approve. AI executes step by step.
```

### Session Management
```bash
# Start a task
/agent implement OAuth2 login

# Name it for later
/sessions save oauth-login

# Later, resume
/sessions resume oauth-login

# List all sessions
/sessions

# Delete old session
/sessions delete old-project
```

---

## 🐛 Troubleshooting

### "No API key found for provider 'X'"
**Cause**: The provider isn't configured with an API key.

**Solutions**:
1. Run `/setup` inside Commandor and enter your key
2. Set the environment variable (`export GEMINI_API_KEY=...`)
3. Edit `~/.commandor/config` and add the key under the provider
4. Test status: `/providers` (shows ✓/✗ for each)

### "Command not found" after installation
**Cause**: Scripts directory not in PATH or virtual environment not activated.

**Solutions**:
```bash
# Check if installed
pip show commandor-ai

# If in venv, activate it
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Or use full path
python -m commandor
```

### Context window exceeded / Memory issues
**Cause**: Very long conversations can hit model token limits.

**Solutions**:
- Commandor auto-summarizes at 80% capacity, but you can also:
  - Use `/reset` to start fresh
  - Start a new session: `/sessions new <name>`
  - Use a model with larger context (e.g., `gemini-2.5-pro` has 2M tokens)

### "Corrupt checkpoint" errors
**Cause**: SQLite database corruption (rare, usually from abrupt termination).

**Solutions**:
- Delete `~/.commandor/checkpoints.db` — Commandor will recreate it
- Sessions themselves (in `~/.commandor/sessions.json`) are safe to keep

### Tool execution fails (permission denied, file not found)
**Tips**:
- Always use `cd_tool` to navigate to the correct project directory first
- Check file paths are relative to CWD (shown in prompt)
- Some tools require files to exist; use `list_directory_tool` to verify
- For shell commands, ensure you have execute permissions

### Textual UI glitches / display issues
**Solutions**:
- Update Textual: `pip install -U textual`
- Try a different color scheme: edit `~/.commandor/config`, set `ui.color_scheme: dark`
- Disable live streaming: set `ui.verbose: false`
- Run with `TERM=xterm-256color` if colors are broken

### Provider-specific errors
- **Gemini**: Ensure API key has Generative Language API enabled
- **Anthropic**: Check you're using an API key from console.anthropic.com
- **OpenAI**: Verify organization and billing are set up
- **OpenRouter**: Some models require credits; check your balance

---

## 🧪 Testing

### Run the test suite
```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# With coverage
pytest --cov=commandor
```

### Manual smoke test
```bash
# Quick interactive test
commandor
/setup  # configure a provider
/agent create a simple Python hello world script
```

### Test provider connectivity
```bash
# From Python
from commandor.agent.executor import test_providers
results = test_providers()
print(results)
# Output: {'gemini': {'status': 'ok'}, 'anthropic': {'status': 'no_api_key'}, ...}
```

---

## 🛠️ Development

### Setting Up a Dev Environment
```bash
# Clone
git clone https://github.com/ravin-d-27/Commandor.git
cd Commandor

# Create venv
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install in editable mode with dev deps
pip install -e ".[dev]"

# Run locally
commandor --version
```

### Code Style
- **Python**: Follow PEP 8, use `ruff` for linting
- **Imports**: Sort with `ruff` or `isort`
- **Types**: Use type hints (checked with `mypy`)
- **Commits**: Conventional Commits recommended (feat:, fix:, docs:, etc.)

### Pre-commit Hooks (optional)
```bash
pip install pre-commit
pre-commit install
# Runs ruff, mypy, etc. on staged files
```

### Building & Publishing
```bash
# Build distribution
pip install build
python -m build

# Check
twine check dist/*

# Upload to PyPI (maintainers only)
twine upload dist/*
```

---

## 🤝 Contributing

Contributions are **welcome** and **appreciated**!

### How to Contribute
1. **Report bugs**: Open an issue with steps to reproduce, expected vs actual behavior, environment details
2. **Request features**: Describe the use case and proposed solution
3. **Submit PRs**: 
   - Fork the repo
   - Create a feature branch (`git checkout -b feat/amazing-feature`)
   - Make changes, add tests if applicable
   - Ensure tests pass (`pytest`)
   - Open a PR with clear description

### Areas Needing Help
- [ ] Support for more providers (Groq, Together, etc.)
- [ ] Enhanced diff viewer (side-by-side, syntax highlighting)
- [ ] Export formats (JSON, HTML, PDF)
- [ ] Plugin system for custom tools
- [ ] Windows-specific improvements
- [ ] Performance optimizations for large repos
- [ ] Better error recovery and retry logic

### Code of Conduct
Please be respectful and constructive. Harassment or toxic behavior will not be tolerated.

---

## 📜 License

MIT License — see [LICENSE](LICENSE) file for full text.

Short version: Use this software for any purpose, modify it, distribute it. Just include the original license and copyright notice.

---

## 🙏 Acknowledgments

Built with these amazing open-source projects:
- [LangGraph](https://langchain-ai.github.io/langgraph/) — Agent orchestration
- [Textual](https://textual.textualize.io/) — TUI framework
- [Rich](https://rich.readthedocs.io/) — Terminal formatting
- [LangChain](https://www.langchain.com/) — LLM abstractions
- [OpenAI / Anthropic / Google](https://github.com) — Model providers

---

## 📞 Contact

**Author**: Ravin D  
- GitHub: https://github.com/ravin-d-27
- Email: ravin.d3107@outlook.com  
- Issues: https://github.com/ravin-d-27/Commandor/issues

---

## 📊 Version & Status

- **Current Version**: 0.2.0
- **Status**: Actively maintained
- **Last Major Update**: Recent commits include session autosave, metrics monitoring, and classifier improvements
- **Roadmap**: See [GitHub Projects](https://github.com/ravin-d-27/Commandor/projects) for upcoming features

---

## ⭐ Support

If you find Commandor useful, please consider:
- **Starring** the repository on GitHub
- **Reporting** bugs and suggesting improvements
- **Sharing** with your network
- **Contributing** code or documentation

Your support helps keep the project alive! 🚀
