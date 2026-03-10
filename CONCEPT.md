# Commandor Concepts & Architecture

This document explains the core concepts, architecture, and file responsibilities of the Commandor project.

## Overview

Commandor is an AI-powered coding assistant embedded in your terminal. It uses a graph-based agentic workflow to help developers explore codebases, plan changes, implement features, and run commands autonomously or with human oversight.

## Core Architecture

Commandor is built on **LangGraph**, which allows for complex, stateful multi-turn interactions. The agent's brain is a "ReAct" (Reasoning and Acting) loop that decides whether to provide a text response or call a tool.

### Interaction Modes

Commandor supports four primary modes of operation, defined in `commandor/agent/modes.py` and implemented in `commandor/agent/executor.py`:

1.  **Agent Mode (`agent`)**: Fully autonomous. The agent uses all available tools to complete a task without asking for permission.
2.  **Chat Mode (`chat`)**: A pure conversational mode with no tools. Useful for asking questions about code or general programming concepts.
3.  **Assist Mode (`assist`)**: Human-in-the-loop. The agent is autonomous but **pauses and waits for user approval** before executing any "dangerous" tools (like writing files or running shell commands).
4.  **Plan Mode (`plan`)**: A two-phase workflow.
    *   **Phase 1 (Planning)**: The agent explores the task and produces a structured, numbered plan using a chat-only graph.
    *   **Phase 2 (Execution)**: Once the user approves or edits the plan, a second agent executes it step-by-step using the full toolset.

## Project Structure

### `commandor/` (Core Package)
- `__main__.py`: The CLI entry point.
- `terminal.py`: The heart of the interactive session. Handles command parsing (e.g., `/agent`, `/sessions`), `@filepath` reference expansion, and the main loop.
- `tui.py`: Custom `prompt_toolkit` implementation for the interactive prompt, including the status toolbar (metrics, session name).
- `session_manager.py`: Manages session persistence, listing, and automatic naming using LLM-generated slugs.
- `api_manager.py`: Specialized manager for API keys and default model configurations across multiple providers.
- `config.py`: Handles global user configuration (YAML-based) and provider settings.

### `commandor/agent/` (The Brain)
- `lc_graph.py`: Defines the LangGraph state machines (Agent, Assist, Chat) and initializes the `SqliteSaver` checkpointer for persistent memory.
- `lc_tools.py`: LangChain `@tool` wrappers around utility functions. Includes logic for diff display on file mutation.
- `executor.py`: Orchestrates graph execution. Handles streaming output, thinking blocks, context condensation, and token metrics.
- `lc_models.py`: Factory for instantiating LLMs (Gemini, Anthropic, OpenAI, OpenRouter) with appropriate configurations.
- `modes.py`: Simple registry of available agent modes and their descriptions.

### `commandor/utils/` (Utilities)
- `file_ops.py`: Low-level file system operations (read, write, edit, glob, search).
- `shell.py`: Utilities for running shell commands and gathering system/git context.
- `diff_display.py`: Uses `rich` to render beautiful, colorized unified diffs when files are modified.

## Key Concepts

### Persistent Memory
Commandor uses a local SQLite database at `~/.commandor/checkpoints.db` to store conversation states. Every session has a unique `thread_id`, allowing you to resume work across terminal restarts.

### Context Management & Condensation
To prevent "context window overflow" in long-running tasks, `executor.py` includes a **summarization hook**. When the message history exceeds a model-specific threshold (e.g., 80% of the context window), Commandor:
1.  Summarizes the older part of the conversation.
2.  Replaces those messages with a single "Context summary" block.
3.  Preserves recent messages to maintain immediate context.

### Intelligent Context Expansion
The terminal supports **`@filepath` references**. Before sending a task to the agent, Commandor scans the input for `@path/to/file` tokens and automatically inlines the file's content into the prompt within `<file>` XML tags. This provides the agent with immediate access to relevant code without requiring it to use a "read" tool first.

### Session Management
Sessions can be named and managed via `/sessions`.
- **Auto-naming**: When starting a new task in an unnamed session, Commandor uses a quick LLM call to generate a relevant kebab-case name (e.g., `fix-auth-bug`).
- **Persistence**: Session metadata is stored in `~/.commandor/sessions.json`.

### Safety & Diffs
When an agent modifies a file using `write_file_tool`, `edit_file_tool`, or `patch_file_tool`, it captures the "before" and "after" states. `diff_display.py` then renders a visual diff so the user can verify exactly what changed. In `assist` mode, these changes are staged and only applied after explicit user confirmation.

### Real-time Metrics
The interactive prompt displays real-time metrics in the bottom toolbar:
- **Tokens**: Input/Output tokens for the last operation.
- **Context**: Approximate total tokens currently in the conversation buffer.
- **Cost**: Estimated session cost (if supported by the provider).
