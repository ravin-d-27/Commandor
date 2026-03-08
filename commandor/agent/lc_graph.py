"""LangGraph graph builders for all agent modes.

Graph factory functions:
  - build_agent_graph  → fully autonomous, runs tools without interruption
  - build_chat_graph   → no tools, pure conversation
  - build_assist_graph → pauses before every tool node (human-in-the-loop)

A single module-level SqliteSaver is shared across all graphs so that
conversation memory persists across multiple run_agent() calls and across
terminal restarts (stored at ~/.commandor/checkpoints.db).

Constants:
  - SYSTEM_PROMPT   → base system prompt for all modes
  - PLANNING_SUFFIX → appended for plan-mode Phase 1 (planning only, no tools)
"""

import sqlite3
import warnings
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from langgraph.prebuilt import create_react_agent

# ---------------------------------------------------------------------------
# Shared persistent checkpoint store.
# Uses SqliteSaver so sessions survive process restarts.
# Falls back to MemorySaver if the sqlite package is unavailable.
# ---------------------------------------------------------------------------
_db_path = Path.home() / ".commandor" / "checkpoints.db"
_db_path.parent.mkdir(exist_ok=True)

try:
    from langgraph.checkpoint.sqlite import SqliteSaver as _SaverClass

    _conn = sqlite3.connect(str(_db_path), check_same_thread=False)
    _checkpointer = _SaverClass(_conn)
    _checkpointer.setup()
except Exception:  # pragma: no cover
    from langgraph.checkpoint.memory import MemorySaver as _SaverClass  # type: ignore[assignment]

    _checkpointer = _SaverClass()


def get_checkpointer():
    """Return the module-level checkpoint store (SqliteSaver or MemorySaver)."""
    return _checkpointer

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are Commandor, an expert AI coding agent embedded in a developer's terminal.

## Your mission
Help the developer implement features, fix bugs, refactor code, write tests, understand
codebases, and manage files — efficiently and correctly.

## Workflow
1. **Explore first** — read relevant files, list directories, search for patterns.
2. **Plan** — think through the changes needed before modifying anything.
3. **Implement** — make targeted, minimal edits. Prefer editing existing files over creating new ones.
4. **Verify** — run tests, linters, or the program itself to confirm the change works.
5. **Report** — summarise what you did, what changed, and any caveats.

## File editing rules
- Always read a file before editing it.
- Use `edit_file_tool` for surgical replacements; use `write_file_tool` only when creating a new file
  or when the entire content needs to be replaced.
- Never leave partial/broken code in a file.
- Preserve the existing code style, indentation, and formatting conventions.

## Code quality
- Write clean, idiomatic code for the language in use.
- Add docstrings / comments where they aid understanding.
- Handle errors gracefully.
- Avoid introducing new dependencies unless explicitly asked.

## Safety
- Do not delete files unless explicitly instructed.
- Do not run destructive shell commands (e.g. `rm -rf`) without explicit user approval.
- If a task is ambiguous or risky, state your assumptions clearly and ask for confirmation.

## Communication style
- Be concise. The developer is busy.
- When you've finished a task, give a short summary of what you did.
- If something went wrong or you're blocked, say so clearly and suggest next steps.
"""

# ---------------------------------------------------------------------------
# Planning-phase system-prompt suffix (used by plan mode, Phase 1 only)
# ---------------------------------------------------------------------------
PLANNING_SUFFIX = """
## PLANNING PHASE — do NOT use any tools yet

Your sole job right now is to produce a structured, numbered plan describing
exactly how you will complete the task.  Do not call any tools.  Do not start
implementing.  Just plan.

For each step:
- State what you will do in one concise sentence.
- Mention which tool(s) you expect to use, e.g. `(tool: read_file_tool)`.
- If no tool is needed for a step, write `(no tool)`.

Format your response exactly as:

## Plan

1. [Step description]  (tool: xxx_tool)
2. [Step description]  (tool: yyy_tool)
…

## Summary

One or two sentences describing the overall approach and any key assumptions.
"""


# ---------------------------------------------------------------------------
# Graph factory functions
# ---------------------------------------------------------------------------

def build_agent_graph(
    llm: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str | None = None,
) -> CompiledStateGraph:
    """Build a fully autonomous agent graph.

    The LLM will call tools automatically until the task is complete.
    No human interruption.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return create_react_agent(
            llm,
            tools=tools,
            prompt=system_prompt or SYSTEM_PROMPT,
            checkpointer=_checkpointer,
        )


def build_chat_graph(
    llm: BaseChatModel,
    system_prompt: str | None = None,
) -> CompiledStateGraph:
    """Build a chat-only graph with no tools.

    Used for questions, explanations, and general conversation.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return create_react_agent(
            llm,
            tools=[],
            prompt=system_prompt or SYSTEM_PROMPT,
            checkpointer=_checkpointer,
        )


def build_assist_graph(
    llm: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str | None = None,
) -> CompiledStateGraph:
    """Build a human-in-the-loop assist graph.

    The graph will pause (interrupt_before="tools") before every tool
    execution so the caller can inspect and approve/deny the planned actions.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return create_react_agent(
            llm,
            tools=tools,
            prompt=system_prompt or SYSTEM_PROMPT,
            checkpointer=_checkpointer,
            interrupt_before=["tools"],
        )
