"""LangGraph-based agent executor.

Public API (backward-compatible with terminal.py):
    run_agent(task, mode, provider, model, thread_id, verbose) -> AgentResult
    run_agent_interactive(task, mode, provider, model, thread_id) -> AgentResult
    test_providers() -> dict

Modes:
    "agent"  — fully autonomous, uses all tools
    "chat"   — no tools, pure conversation
    "assist" — autonomous but pauses before tool calls for user approval
"""

from __future__ import annotations

import uuid
from typing import Optional

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from ..config import get_api_key, get_config
from ..providers.base import AgentResult
from .lc_graph import (
    PLANNING_SUFFIX,
    SYSTEM_PROMPT,
    build_agent_graph,
    build_assist_graph,
    build_chat_graph,
)
from .lc_models import build_model
from .lc_tools import ALL_TOOLS, DANGEROUS_TOOL_NAMES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_provider_model(
    provider: Optional[str],
    model: Optional[str],
) -> tuple[str, str, str]:
    """Return (provider_name, api_key, model_id), filling gaps from config."""
    cfg = get_config()

    if provider is None:
        provider = cfg.config.default_provider if cfg.config else "gemini"

    pconfig = cfg.get_provider_config(provider)

    if model is None:
        model = pconfig.default_model if pconfig else "gemini-2.5-flash"

    api_key = get_api_key(provider)
    if not api_key:
        raise ValueError(
            f"No API key found for provider '{provider}'. "
            "Run /setup or set the appropriate environment variable."
        )

    return provider, api_key, model


def _build_system_prompt() -> str:
    """Inject live context (cwd, git) into the base system prompt."""
    from ..utils.shell import get_git_info, get_working_directory  # noqa: PLC0415

    cwd = get_working_directory()
    git = get_git_info()

    context_block = f"\n## Current context\n- Working directory: {cwd}\n- Git: {git}\n"
    return SYSTEM_PROMPT + context_block


def _extract_final_answer(state: dict) -> str:
    """Pull the last AI text message out of a graph state dict."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            if isinstance(msg.content, str):
                return msg.content
            # content can be a list of blocks (e.g. tool_use + text)
            text_parts = [
                block if isinstance(block, str)
                else block.get("text", "")
                for block in msg.content
                if isinstance(block, (str, dict))
            ]
            joined = "".join(text_parts).strip()
            if joined:
                return joined
    return "Task completed."


def _stream_graph(graph, input_data, config: dict) -> str:
    """Stream graph events; print tokens live and announce tool activity.

    Iterates ``graph.stream(..., stream_mode='messages')``.  For each event:

    * ``AIMessageChunk`` with text content  → printed immediately (no newline)
      so the response typewriter-scrolls to the terminal.
    * ``AIMessageChunk`` with a new tool call → prints a ``⚙ tool_name [⚠️]``
      activity line so the user can see what the agent is doing.
    * ``ToolMessage``                        → tool already ran (diff display
      was handled inside the tool itself); nothing extra to print here.

    Returns the accumulated text from all ``AIMessageChunk.content`` strings.
    """
    accumulated = ""
    seen_call_ids: set[str] = set()  # deduplicate per tool-call id

    for chunk, metadata in graph.stream(input_data, config, stream_mode="messages"):
        if isinstance(chunk, AIMessageChunk):
            # -- Stream text tokens --
            if isinstance(chunk.content, str) and chunk.content:
                print(chunk.content, end="", flush=True)
                accumulated += chunk.content

            # -- Announce tool calls (first chunk that names the call) --
            tcc = getattr(chunk, "tool_call_chunks", []) or []
            for tc in tcc:
                name = (tc.get("name") or "").strip()
                call_id = (tc.get("id") or "").strip()
                if name and call_id and call_id not in seen_call_ids:
                    seen_call_ids.add(call_id)
                    flag = " ⚠️ " if name in DANGEROUS_TOOL_NAMES else " "
                    raw_args = tc.get("args") or ""
                    args_preview = (
                        raw_args[:80] + "..." if len(str(raw_args)) > 80 else raw_args
                    )
                    print(f"\n  ⚙{flag}{name}  {args_preview}", flush=True)

        # ToolMessage: diff was already printed inside the tool; nothing to do.

    # Ensure cursor is on a fresh line after all tokens are flushed
    if accumulated and not accumulated.endswith("\n"):
        print()

    return accumulated


# ---------------------------------------------------------------------------
# Mode runners
# ---------------------------------------------------------------------------

def _run_agent(llm, task: str, system_prompt: str, config: dict, verbose: bool) -> AgentResult:
    """Fully autonomous agent run (streaming)."""
    graph = build_agent_graph(llm, ALL_TOOLS, system_prompt)

    if verbose:
        print("  [agent] thinking...\n")

    _stream_graph(graph, {"messages": [HumanMessage(content=task)]}, config)

    state = graph.get_state(config)
    return AgentResult(
        success=True,
        final_answer=_extract_final_answer(state.values),
        steps=[],
    )


def _run_chat(llm, task: str, system_prompt: str, config: dict, verbose: bool) -> AgentResult:
    """Chat-only (no tools) run (streaming)."""
    graph = build_chat_graph(llm, system_prompt)

    if verbose:
        print("  [chat] thinking...\n")

    _stream_graph(graph, {"messages": [HumanMessage(content=task)]}, config)

    state = graph.get_state(config)
    return AgentResult(
        success=True,
        final_answer=_extract_final_answer(state.values),
        steps=[],
    )


def _run_assist(llm, task: str, system_prompt: str, config: dict, verbose: bool) -> AgentResult:
    """Human-in-the-loop assist run (streaming).

    Streams each graph segment; pauses before every tool-call batch for user
    approval (y/n/q).  Denied calls inject synthetic ToolMessages so the LLM
    can recover gracefully.
    """
    graph = build_assist_graph(llm, ALL_TOOLS, system_prompt)

    if verbose:
        print("  [assist] thinking...\n")

    # Stream the initial segment — graph stops at interrupt_before="tools"
    _stream_graph(graph, {"messages": [HumanMessage(content=task)]}, config)

    while True:
        state = graph.get_state(config)

        # Nothing left to run — we're done.
        if not state.next:
            break

        if "tools" not in state.next:
            # Unexpected non-tool interrupt; just resume.
            _stream_graph(graph, None, config)
            continue

        # -- Human-in-the-loop: show pending tool calls --
        messages = state.values.get("messages", [])
        pending: list = []
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                pending = msg.tool_calls
                break

        if not pending:
            _stream_graph(graph, None, config)
            continue

        print("\n  [assist] Planned actions:")
        for tc in pending:
            name = tc.get("name", tc.get("type", "unknown"))
            args = tc.get("args", tc.get("arguments", {}))
            flag = " ⚠️" if name in DANGEROUS_TOOL_NAMES else ""
            print(f"    • {name}{flag}({_format_args(args)})")

        try:
            answer = input("\n  Proceed? [y]es / [n]o / [q]uit: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            answer = "q"

        if answer == "q":
            return AgentResult(
                success=False,
                final_answer="Task cancelled by user.",
                steps=[],
            )

        if answer in ("y", "yes", ""):
            # Execute the tools and stream what follows
            _stream_graph(graph, None, config)
        else:
            # Inject denied ToolMessages, then stream the LLM's recovery reply
            denied_msgs = [
                ToolMessage(
                    content="Action denied by user. Please try a different approach.",
                    tool_call_id=tc.get("id", str(uuid.uuid4())),
                )
                for tc in pending
            ]
            graph.update_state(
                config,
                {"messages": denied_msgs},
                as_node="tools",
            )
            _stream_graph(graph, None, config)

    state = graph.get_state(config)
    return AgentResult(
        success=True,
        final_answer=_extract_final_answer(state.values),
        steps=[],
    )


def _run_plan(llm, task: str, system_prompt: str, config: dict, verbose: bool) -> AgentResult:
    """Plan-then-execute mode.

    Phase 1 — Planning (no tools):
        A chat graph runs with a planning-only system-prompt suffix.
        The LLM streams a numbered plan back to the terminal.
        The user is shown the plan in a Rich panel and prompted:
            [y]es  → proceed to execution
            [e]dit → type feedback; plan is revised (up to 2 revision cycles)
            [n]o   → cancel

    Phase 2 — Execution:
        The approved plan text is injected into the system prompt as an
        "Approved Plan" context block.  A fresh agent graph runs the task
        with the full tool suite, streaming output as normal.
    """
    from rich.console import Console  # noqa: PLC0415
    from rich.markdown import Markdown  # noqa: PLC0415
    from rich.panel import Panel  # noqa: PLC0415

    _rc = Console()

    planning_prompt = system_prompt + PLANNING_SUFFIX

    def _generate_plan(prompt_text: str, extra_context: str = "") -> str:
        """Run a single planning pass and return the plan text."""
        plan_config = {"configurable": {"thread_id": f"plan_{uuid.uuid4()}"}}
        plan_graph = build_chat_graph(llm, planning_prompt)
        user_msg = prompt_text
        if extra_context:
            user_msg = extra_context + "\n\n" + prompt_text
        _stream_graph(
            plan_graph,
            {"messages": [HumanMessage(content=user_msg)]},
            plan_config,
        )
        state = plan_graph.get_state(plan_config)
        return _extract_final_answer(state.values)

    if verbose:
        print("  [plan] Generating plan...\n")

    plan_text = _generate_plan(task)

    # Up to 2 revision cycles so the loop runs at most 3 times (initial + 2 edits)
    for _ in range(3):
        _rc.print()
        _rc.print(
            Panel(
                Markdown(plan_text),
                title="[bold cyan]Proposed Plan[/bold cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

        try:
            answer = input(
                "\n  Proceed with this plan? [y]es / [e]dit / [n]o: "
            ).strip().lower()
        except (KeyboardInterrupt, EOFError):
            answer = "n"

        if answer in ("n", "no"):
            return AgentResult(
                success=False,
                final_answer="Plan rejected by user.",
                steps=[],
            )

        if answer in ("y", "yes", ""):
            break  # proceed to execution

        if answer.startswith("e"):
            try:
                feedback = input("  Your feedback: ").strip()
            except (KeyboardInterrupt, EOFError):
                return AgentResult(
                    success=False,
                    final_answer="Plan cancelled.",
                    steps=[],
                )
            if feedback:
                print("\n  [plan] Revising plan...\n")
                revision_context = (
                    f"Task: {task}\n\n"
                    f"Previous plan:\n{plan_text}\n\n"
                    f"User feedback: {feedback}\n\n"
                    "Please revise the plan to incorporate this feedback."
                )
                plan_text = _generate_plan(task, extra_context=revision_context)
            continue

    # ------------------------------------------------------------------ #
    # Phase 2: execution with the approved plan injected into context     #
    # ------------------------------------------------------------------ #
    execution_prompt = (
        system_prompt
        + "\n\n## Approved Plan\n"
        "Follow this plan step by step to complete the task:\n\n"
        + plan_text
        + "\n"
    )

    print("\n  [plan] Executing approved plan...\n")
    exec_config = {"configurable": {"thread_id": f"plan_exec_{uuid.uuid4()}"}}
    agent_graph = build_agent_graph(llm, ALL_TOOLS, execution_prompt)
    _stream_graph(
        agent_graph,
        {"messages": [HumanMessage(content=task)]},
        exec_config,
    )

    exec_state = agent_graph.get_state(exec_config)
    return AgentResult(
        success=True,
        final_answer=_extract_final_answer(exec_state.values),
        steps=[],
    )


def _format_args(args: dict) -> str:
    """Format tool call args for display, truncating long values."""
    if not args:
        return ""
    parts = []
    for k, v in args.items():
        v_str = repr(v)
        if len(v_str) > 60:
            v_str = v_str[:57] + "..."
        parts.append(f"{k}={v_str}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_agent(
    task: str,
    mode: str = "agent",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    thread_id: Optional[str] = None,
    verbose: bool = True,
) -> AgentResult:
    """Run an agent task in the specified mode.

    Args:
        task:      The user's request / instruction.
        mode:      One of 'agent', 'chat', 'assist'.
        provider:  AI provider ('gemini', 'anthropic', 'openai', 'openrouter').
                   Defaults to the configured default provider.
        model:     Model identifier. Defaults to the provider's default model.
        thread_id: Conversation thread ID for memory continuity.
                   If None, a fresh UUID is generated (no memory across calls).
        verbose:   Whether to print progress messages.

    Returns:
        AgentResult with success flag and final_answer text.
    """
    try:
        resolved_provider, api_key, resolved_model = _resolve_provider_model(
            provider, model
        )
        llm = build_model(resolved_provider, api_key, resolved_model)
        system_prompt = _build_system_prompt()

        # Scope thread_id by mode to prevent checkpoint conflicts
        scoped_tid = f"{mode}_{thread_id or uuid.uuid4()}"
        config = {"configurable": {"thread_id": scoped_tid}}

        if mode == "agent":
            return _run_agent(llm, task, system_prompt, config, verbose)
        elif mode == "chat":
            return _run_chat(llm, task, system_prompt, config, verbose)
        elif mode == "assist":
            return _run_assist(llm, task, system_prompt, config, verbose)
        elif mode == "plan":
            return _run_plan(llm, task, system_prompt, config, verbose)
        else:
            return AgentResult(
                success=False,
                final_answer=f"Unknown mode: '{mode}'. Valid modes: agent, chat, assist, plan.",
                steps=[],
            )

    except Exception as e:
        return AgentResult(
            success=False,
            final_answer=f"Error: {e}",
            steps=[],
        )


# Alias kept for backward compatibility with any existing callers
run_agent_interactive = run_agent


def test_providers() -> dict:
    """Test which providers have valid API keys configured.

    Returns:
        Dict mapping provider name to a status dict with keys:
          'status': 'ok' | 'no_api_key' | 'error'
          'error':  error message (only present when status == 'error')
    """
    results = {}
    providers = ["gemini", "anthropic", "openai", "openrouter"]

    for name in providers:
        key = get_api_key(name)
        if not key:
            results[name] = {"status": "no_api_key"}
            continue
        try:
            cfg = get_config()
            pconfig = cfg.get_provider_config(name)
            m = pconfig.default_model if pconfig else ""
            llm = build_model(name, key, m)
            # Minimal invocation — just check the key is accepted
            llm.invoke("ping")
            results[name] = {"status": "ok"}
        except Exception as e:
            err = str(e).lower()
            if "authentication" in err or "api key" in err or "invalid" in err:
                results[name] = {"status": "invalid_key"}
            else:
                results[name] = {"status": "error", "error": str(e)}

    return results
