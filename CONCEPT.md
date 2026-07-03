# Commandor Concepts & Architecture

This document explains the core concepts, architecture, and file responsibilities
of the Commandor project.

## Overview

Commandor is an AI-powered coding assistant embedded in a Textual terminal UI.
It uses a LangGraph ReAct workflow to explore codebases, plan changes, call tools,
edit files, run commands, and summarize results. In the TUI, plain text is treated
as an agent task by default; slash commands are still available for explicit modes
and utility actions.

## Interaction Model

Commandor supports four execution modes:

1. **Agent mode (`agent`)**: Fully autonomous. This is the default for plain TUI
   input and for `/agent <task>`. The agent can read files, call tools, edit code,
   run commands, and create a live task plan for multi-step work.
2. **Assist mode (`assist`)**: Agent mode with confirmation before tool execution.
3. **Plan mode (`plan`)**: Produces a plan first, then executes after approval.
4. **Chat mode (`chat`)**: Conversation only, with no tools.

Shell commands are explicit in the TUI: prefix them with `$ ` or `!`, for example
`$ git status`. This keeps normal prose available for natural agent tasks.

## Project Structure

### `commandor/` (Core Package)
- `__main__.py`: CLI entry point and non-interactive command handling.
- `textual_app.py`: Textual application shell.
- `widgets/terminal_widget.py`: Main interactive terminal. Handles natural agent
  input, slash commands, shell escapes, command history, `@` file suggestions,
  image attachments, sessions, exports, and rendering streamed events.
- `agent_bridge.py`: Converts LangGraph streaming output into typed TUI events.
  Includes recovery for provider streams that return tool output but no final
  generation.
- `session_manager.py`: Named session registry stored in
  `~/.commandor/sessions.json`.
- `api_manager.py`: Interactive provider/API-key management helpers.
- `config.py`: YAML configuration, provider defaults, API key resolution, and
  setup support.

### `commandor/agent/` (The Brain)
- `lc_graph.py`: LangGraph graph factories and shared SQLite checkpointer.
- `lc_models.py`: Model factory for Gemini, Anthropic, OpenAI, OpenRouter, Ollama,
  Groq, DeepSeek, and OpenAI-compatible endpoints.
- `lc_tools.py`: LangChain `@tool` wrappers around file, shell, web, git,
  delegation, and task-plan helpers.
- `executor.py`: Non-TUI orchestration for agent/chat/assist/plan modes.
- `plugins.py`: Entry-point based plugin discovery for custom tools exposed via
  the `commandor.tools` group.
- `subagent.py`: Short-lived focused sub-agents and parallel delegation.
- `modes.py`: Mode registry and descriptions.

### `commandor/utils/` (Utilities)
- `file_ops.py`: Low-level file read/write/edit/glob/search operations.
- `shell.py`: Shell execution, `cd`, environment, git summary, and safety checks.
- `git_ops.py`: Git status, diff, commit, and log helpers.
- `web_ops.py`: URL fetch and generic HTTP request helpers.
- `ignore.py`: `.commandorignore` parser and matcher.
- `multimodal.py`: Image validation and data-URL encoding for vision models.
- `exporter.py`: Markdown, JSON, and HTML conversation exporters.
- `tokenizer.py`: tiktoken-backed token counting with fallback behavior.
- `diff_display.py`: Unified Rich diff display.
- `diff_side_by_side.py`: Side-by-side syntax-highlighted diff rows/rendering.

## Key Concepts

### Natural TUI Input
The TUI routes plain text to agent mode. Users can type `fix the failing tests`
instead of `/agent fix the failing tests`. Explicit slash commands remain useful
for `/chat`, `/assist`, `/plan`, `/provider`, `/plugins`, `/image`, `/export`,
and other utility commands.

### `@` File References
The TUI supports `@path/to/file` references. While typing, `@` opens a live file
list from the current project; Tab completes the active reference. Quoted paths
with spaces are supported, for example `@"docs/My File.md"`.

Before sending the task to the model, Commandor expands matched references into
fenced code blocks so the model gets the file content immediately. Glob patterns
such as `@tests/**/*.py` are also supported.

### Persistent Memory
LangGraph checkpoints are stored in SQLite at `~/.commandor/checkpoints.db`.
Each session has a thread ID, and named session metadata is stored separately so
work can continue across terminal restarts.

### Context Management
`executor.py` and `agent_bridge.py` use a summarization hook to condense older
conversation history when a model approaches its context limit. Token estimation
uses `tiktoken` when available and falls back gracefully.

### Provider System
Provider selection is centralized in `lc_models.py`. Hosted providers use API
keys from config or environment variables. Ollama is keyless and uses a local
base URL. OpenAI-compatible endpoints can be pointed at local or custom servers.

### Tooling & Extensibility
The built-in tools cover file operations, shell execution, web/HTTP requests,
git operations, task planning, and sub-agent delegation. Installed packages can
add tools by exposing a `commandor.tools` entry point; `/plugins` lists or reloads
them in the TUI.

### Safety & Visibility
`.commandorignore` protects files and directories from agent access. Destructive
shell patterns are blocked. File mutations display diffs, and side-by-side diffs
are available when enabled. The TUI shows tool calls, tool output, live task
plans, context usage, and completion metrics.

### Multimodal & Export
`/image` attaches images to the next AI run for vision-capable models. `/export`
saves conversation history as Markdown, JSON, or HTML.

### Tests & CI
The repository includes pytest coverage for config, file operations, ignore
rules, token counting, exporters, web/git helpers, plugins, multimodal handling,
the agent bridge, and TUI input helpers. The GitHub Actions workflow runs the
test suite for PR and merge validation.
