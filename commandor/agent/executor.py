"""LangGraph-based agent executor.

Public API (backward-compatible with terminal.py):
    run_agent(task, mode, provider, model, thread_id, verbose, session_name) -> AgentResult
    run_agent_interactive(task, mode, provider, model, thread_id) -> AgentResult
    test_providers() -> dict

Modes:
    "agent"  — fully autonomous, uses all tools
    "chat"   — no tools, pure conversation
    "assist" — autonomous but pauses before tool calls for user approval
    "plan"   — plan-then-execute with human review
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from rich import box as rich_box
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from ..config import get_api_key, get_config
from ..providers.base import AgentResult
from .lc_graph import (
    PLANNING_SUFFIX,
    SYSTEM_PROMPT,
    build_agent_graph,
    build_assist_graph,
    build_chat_graph,
    get_checkpointer,
)
from .lc_models import build_model
from .lc_tools import ALL_TOOLS, DANGEROUS_TOOL_NAMES

_rc = Console()


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

    context_block = (
        f"\n## Current context\n"
        f"- **Working directory: `{cwd}`**  ← THIS is where all file operations happen by default\n"
        f"- Use `cd_tool` BEFORE starting work to navigate to the correct project folder\n"
        f"- NEVER create project files in the Commandor tool directory — always `cd_tool` into a dedicated project directory first\n"
        f"- Git: {git}\n"
    )
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


# ---------------------------------------------------------------------------
# Context summarization
# ---------------------------------------------------------------------------

# Default threshold: 80% of the model's context window (if detectable),
# otherwise fall back to this absolute token count.
# 30k is conservative enough not to trigger on normal file-reading tasks,
# while still protecting models with small context windows.
DEFAULT_SUMMARIZE_THRESHOLD = 100_000


def _get_context_window(llm) -> int | None:
    """Try to get the model's context_window attribute.

    Different providers expose it differently:
    - OpenAI/Anthropic: llm.context_window (int)
    - Gemini: llm._default_context_window or llm.model_version
    - Some wrappers: llm.max_tokens or llm.max_context_tokens

    Returns the token count or None if undetectable.
    """
    # OpenAI, Anthropic, Google GenAI (most common)
    if hasattr(llm, "context_window"):
        return llm.context_window

    # Some langchain wrappers expose max_tokens or similar
    if hasattr(llm, "max_tokens"):
        return llm.max_tokens

    # Gemini-specific: check model name for known context sizes
    if hasattr(llm, "model_name"):
        model = llm.model_name.lower()
        # gemini-1.5-pro: 2M, gemini-2.0-pro: 2M
        if "1.5-pro" in model or "2.0-pro" in model:
            return 2_000_000
        # gemini-1.5-flash, 2.0-flash, 2.5-flash, 3.0-flash, etc.
        if "flash" in model and "gemini" in model:
            return 1_000_000
        # gemini-2.5-pro, gemini-3-pro, etc.
        if "pro" in model and "gemini" in model:
            return 1_000_000
        # Any other gemini model — assume 1M (all recent Gemini have ≥1M context)
        if model.startswith("gemini"):
            return 1_000_000
        if "gemini-1.0" in model:
            return 32_768

    return None


def _approx_tokens(messages: list) -> int:
    """Rough token estimate: chars / 4 (no tokenizer dependency)."""
    from langchain_core.messages import get_buffer_string  # noqa: PLC0415
    return len(get_buffer_string(messages)) // 4


def _make_summarize_hook(llm, metrics: dict | None = None):
    """Return a pre_model_hook that compresses history when context grows large.

    The threshold is dynamically computed:
    - Try to get the LLM's context_window (OpenAI/Anthropic/Gemini)
    - Use 80%_window as the threshold
    - Fall back to DEFAULT of context_SUMMARIZE_THRESHOLD (12k tokens) if undetectable
    """
    # Compute threshold once at hook creation time
    ctx_window = _get_context_window(llm)
    if ctx_window:
        threshold = int(ctx_window * 0.8)
    else:
        threshold = DEFAULT_SUMMARIZE_THRESHOLD

    def _hook(state: dict) -> dict:
        from langchain_core.messages import (  # noqa: PLC0415
            HumanMessage,
            SystemMessage,
            get_buffer_string,
        )

        messages = state.get("messages", [])
        if _approx_tokens(messages) < threshold:
            return {}

        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        non_system  = [m for m in messages if not isinstance(m, SystemMessage)]

        keep_recent  = non_system[-4:]
        to_summarize = non_system[:-4]
        if not to_summarize:
            return {}

        history_text = get_buffer_string(to_summarize)
        summary_prompt = (
            "Summarize the following agent work session into 2-3 concise paragraphs. "
            "Focus on: what files were read, what was discovered, and what actions were taken. "
            "Be specific about file names and key findings. This summary will replace the "
            "raw history to free up context space.\n\n"
            f"History:\n{history_text[:12000]}"
        )
        try:
            response = llm.invoke([HumanMessage(content=summary_prompt)])
            summary_text = (
                response.content if hasattr(response, "content") else str(response)
            )
            if len(summary_text) > 3000:
                summary_text = summary_text[:3000] + "\n… (summary truncated)"
            condensed = HumanMessage(
                content=f"[Context summary — history condensed to save space]\n{summary_text}"
            )
            new_messages = system_msgs + [condensed] + keep_recent
            _rc.print("[dim]  ↻  context condensed[/dim]")
            if metrics is not None:
                metrics["condensations"] = metrics.get("condensations", 0) + 1
            return {"messages": new_messages}
        except Exception:
            return {}

    return _hook


# ---------------------------------------------------------------------------
# Run header / footer
# ---------------------------------------------------------------------------

def _print_run_header(mode: str, model: str, session_name: Optional[str] = None) -> None:
    """Print a styled Rule header at the start of a run.

    Example:  ──── agent  ·  gemini-2.5-flash  ·  ◆ my-project ────
    """
    _rc.print()
    parts = [f"[bold purple]{mode}[/bold purple]"]
    if model:
        parts.append(f"[dim]{model}[/dim]")
    if session_name:
        parts.append(f"[dim]◆  {session_name}[/dim]")
    title = "  [dim]·[/dim]  ".join(parts)
    _rc.print(Rule(title, style="dim purple"))
    _rc.print()


def _print_run_footer(metrics: dict, elapsed: float) -> None:
    """Print a styled Rule footer at the end of a run.

    Example:  ✓  done  ·  in 2,113 · out 343  ·  ~338 tok  ·  4.2s ────
    """
    parts: list[str] = ["[bold green]✓  done[/bold green]"]

    inp = metrics.get("input_tokens")
    out = metrics.get("output_tokens")
    if inp and out:
        parts.append(f"[dim]in {inp:,} · out {out:,}[/dim]")

    ctx = metrics.get("approx_tokens")
    if ctx:
        parts.append(f"[dim]~{ctx:,} tok[/dim]")

    cond = metrics.get("condensations", 0)
    if cond:
        parts.append(f"[dim]condensed {cond}×[/dim]")

    parts.append(f"[dim]{elapsed:.1f}s[/dim]")
    title = "  [dim]·[/dim]  ".join(parts)
    _rc.print()
    _rc.print(Rule(title, style="dim green", align="left"))
    _rc.print()


# ---------------------------------------------------------------------------
# Core streaming
# ---------------------------------------------------------------------------

def _stream_graph(
    graph,
    input_data,
    config: dict,
    metrics: dict | None = None,
    silent: bool = False,
) -> str:
    """Stream graph events, printing tool calls, tool outputs, and a final response panel.

    Visual design:
    - Spinner while waiting for first token / tool call (purple dots)
    - Thinking tokens → live-updating rounded purple panel (◈ thinking)
    - Tool calls  → "  ⚙  name  args"  (cyan)
    - Tool output → "     ↳  summary"  (dim, compact — max first line + total count)
    - Response    → rounded panel with dim border, left-aligned "◆  response" title

    When ``silent=True`` the final thinking + response panels are suppressed
    (used by ``_run_plan``'s planning phase to avoid the double-panel bug).

    Returns accumulated AI text (from streaming + graph state).
    """
    accumulated = ""
    thinking_accumulated = ""
    # call_id → tool_name, so outputs can reference back to their call
    seen_call_ids: dict[str, str] = {}
    last_usage = None

    # Live panel state
    live_thinking: Optional[Live] = None
    live_response: Optional[Live] = None

    status = _rc.status(
        "[dim]  thinking...[/dim]",
        spinner="dots",
        spinner_style="purple",
    )
    status.start()
    spinner_active = True

    def _stop_spinner() -> None:
        nonlocal spinner_active
        if spinner_active:
            status.stop()
            spinner_active = False

    def _stop_live_thinking() -> None:
        """Stop the live thinking display."""
        nonlocal live_thinking
        if live_thinking is not None:
            live_thinking.stop()
            live_thinking = None

    def _stop_live_response() -> None:
        """Stop the live response display (transient — it disappears)."""
        nonlocal live_response
        if live_response is not None:
            live_response.stop()
            live_response = None

    def _response_panel(text: str) -> Panel:
        return Panel(
            Text(text, overflow="fold"),
            title="[dim]◆  response[/dim]",
            title_align="left",
            border_style="dim",
            box=rich_box.ROUNDED,
            padding=(0, 2),
        )

    try:
        for chunk, _meta in graph.stream(input_data, config, stream_mode="messages"):

            # ----------------------------------------------------------------
            # Tool output (ToolMessage) — printed below its matching tool call
            # ----------------------------------------------------------------
            if isinstance(chunk, ToolMessage):
                _stop_live_response()
                call_id = getattr(chunk, "tool_call_id", "") or ""
                tool_name = seen_call_ids.get(call_id, "tool")
                content = chunk.content or ""
                if isinstance(content, list):
                    content = "\n".join(
                        b.get("text", str(b)) if isinstance(b, dict) else str(b)
                        for b in content
                    )
                content_str = str(content).strip()
                lines = content_str.splitlines() if content_str else []
                is_dangerous = tool_name in DANGEROUS_TOOL_NAMES

                if not lines:
                    _rc.print("     [dim]↳  (no output)[/dim]")
                elif len(lines) == 1:
                    clr = "yellow" if is_dangerous else "dim"
                    _rc.print(f"     [{clr}]↳  {lines[0][:120]}[/{clr}]")
                elif len(lines) <= 3:
                    for i, line in enumerate(lines):
                        prefix = "↳" if i == 0 else " "
                        clr = "yellow" if is_dangerous else "dim"
                        _rc.print(f"     [{clr}]{prefix}  {line[:120]}[/{clr}]")
                else:
                    preview = lines[0][:80].strip()
                    clr = "yellow" if is_dangerous else "dim"
                    _rc.print(
                        f"     [{clr}]↳  {len(lines):,} lines[/{clr}]"
                        f"  [dim italic]· {preview!r}[/dim italic]"
                    )
                _rc.print()
                continue

            if not isinstance(chunk, AIMessageChunk):
                continue

            # -- Track usage metadata --
            usage = getattr(chunk, "usage_metadata", None)
            if usage:
                last_usage = usage

            # -- Detect & stream thinking blocks (Gemini / Anthropic extended thinking) --
            if isinstance(chunk.content, list):
                for block in chunk.content:
                    if isinstance(block, dict) and block.get("type") == "thinking":
                        new_thinking = block.get("thinking", "")
                        if new_thinking:
                            thinking_accumulated += new_thinking
                            _stop_spinner()
                            thinking_panel = Panel(
                                Text(thinking_accumulated, overflow="fold"),
                                title="[bold purple]◈  thinking[/bold purple]",
                                title_align="left",
                                border_style="dim purple",
                                box=rich_box.ROUNDED,
                                padding=(0, 1),
                            )
                            if live_thinking is None:
                                live_thinking = Live(
                                    thinking_panel,
                                    console=_rc,
                                    refresh_per_second=10,
                                    transient=False,
                                )
                                live_thinking.start()
                            else:
                                live_thinking.update(thinking_panel)

            # -- Announce tool calls --
            tcc = getattr(chunk, "tool_call_chunks", []) or []
            for tc in tcc:
                name = (tc.get("name") or "").strip()
                call_id = (tc.get("id") or "").strip()
                if name and call_id and call_id not in seen_call_ids:
                    seen_call_ids[call_id] = name
                    _stop_live_thinking()
                    _stop_live_response()
                    _stop_spinner()
                    raw_args = tc.get("args") or ""
                    args_preview = (
                        raw_args[:80] + "…" if len(str(raw_args)) > 80 else raw_args
                    )
                    if name in DANGEROUS_TOOL_NAMES:
                        _rc.print(
                            f"  [bold cyan]⚙[/bold cyan]  [bold red]⚠[/bold red]"
                            f"  [cyan]{name}[/cyan]  [dim]{args_preview}[/dim]"
                        )
                    else:
                        _rc.print(
                            f"  [bold cyan]⚙[/bold cyan]  [cyan]{name}[/cyan]"
                            f"  [dim]{args_preview}[/dim]"
                        )

            # -- Stream text tokens live --
            if isinstance(chunk.content, str) and chunk.content:
                _stop_live_thinking()
                _stop_spinner()
                accumulated += chunk.content
                if not silent:
                    if live_response is None:
                        live_response = Live(
                            _response_panel(accumulated),
                            console=_rc,
                            refresh_per_second=15,
                            transient=True,
                        )
                        live_response.start()
                    else:
                        live_response.update(_response_panel(accumulated))

    finally:
        _stop_live_thinking()
        _stop_live_response()
        _stop_spinner()

    if not silent:
        # Finalized thinking panel with Markdown rendering
        if thinking_accumulated:
            _rc.print(Panel(
                Markdown(thinking_accumulated),
                title="[bold purple]◈  thinking[/bold purple]",
                title_align="left",
                border_style="dim purple",
                box=rich_box.ROUNDED,
                padding=(1, 1),
            ))

        # Treat whitespace-only streaming output as empty — model returned no real text
        if not accumulated.strip():
            accumulated = ""

        # If no accumulated text from streaming, get final answer from graph state
        if not accumulated:
            state = graph.get_state(config)
            candidate = _extract_final_answer(state.values)
            # Only accept it if it's not the generic placeholder AND has real content
            if candidate.strip() and candidate != "Task completed.":
                accumulated = candidate

        # Final response panel — Markdown-rendered (replaces the transient live panel)
        if accumulated:
            _rc.print(Panel(
                Markdown(accumulated),
                title="[dim]◆  response[/dim]",
                title_align="left",
                border_style="dim",
                box=rich_box.ROUNDED,
                padding=(0, 2),
            ))
        elif seen_call_ids:
            # Tools were called but model gave no text response — show a fallback
            _rc.print(Panel(
                "[dim]Task completed via tool execution.[/dim]",
                title="[dim]◆  response[/dim]",
                title_align="left",
                border_style="dim",
                box=rich_box.ROUNDED,
                padding=(0, 2),
            ))

    # Update metrics with token usage
    if metrics is not None and last_usage:
        metrics["input_tokens"] = (
            last_usage.get("input_tokens")
            or last_usage.get("prompt_tokens")
        )
        metrics["output_tokens"] = (
            last_usage.get("output_tokens")
            or last_usage.get("completion_tokens")
        )

    return accumulated


# ---------------------------------------------------------------------------
# Mode runners
# ---------------------------------------------------------------------------

def _run_agent(
    llm, task: str, system_prompt: str, config: dict,
    verbose: bool, metrics: dict, session_name: Optional[str] = None,
) -> AgentResult:
    """Fully autonomous agent run (streaming)."""
    _print_run_header("agent", metrics.get("model", ""), session_name)
    t0 = time.monotonic()

    hook = _make_summarize_hook(llm, metrics)
    graph = build_agent_graph(llm, ALL_TOOLS, system_prompt, pre_model_hook=hook)
    _stream_graph(graph, {"messages": [HumanMessage(content=task)]}, config, metrics)

    state = graph.get_state(config)
    metrics["approx_tokens"] = _approx_tokens(state.values.get("messages", []))
    _print_run_footer(metrics, time.monotonic() - t0)
    return AgentResult(
        success=True,
        final_answer=_extract_final_answer(state.values),
        steps=[],
        metrics=metrics,
    )


def _run_chat(
    llm, task: str, system_prompt: str, config: dict,
    verbose: bool, metrics: dict, session_name: Optional[str] = None,
) -> AgentResult:
    """Chat-only (no tools) run (streaming)."""
    _print_run_header("chat", metrics.get("model", ""), session_name)
    t0 = time.monotonic()

    graph = build_chat_graph(llm, system_prompt)
    _stream_graph(graph, {"messages": [HumanMessage(content=task)]}, config, metrics)

    state = graph.get_state(config)
    metrics["approx_tokens"] = _approx_tokens(state.values.get("messages", []))
    _print_run_footer(metrics, time.monotonic() - t0)
    return AgentResult(
        success=True,
        final_answer=_extract_final_answer(state.values),
        steps=[],
        metrics=metrics,
    )


def _run_assist(
    llm, task: str, system_prompt: str, config: dict,
    verbose: bool, metrics: dict, session_name: Optional[str] = None,
) -> AgentResult:
    """Human-in-the-loop assist run (streaming)."""
    _print_run_header("assist", metrics.get("model", ""), session_name)
    t0 = time.monotonic()

    hook = _make_summarize_hook(llm, metrics)
    graph = build_assist_graph(llm, ALL_TOOLS, system_prompt, pre_model_hook=hook)

    _stream_graph(graph, {"messages": [HumanMessage(content=task)]}, config, metrics)

    while True:
        state = graph.get_state(config)

        if not state.next:
            break

        if "tools" not in state.next:
            _stream_graph(graph, None, config, metrics)
            continue

        messages = state.values.get("messages", [])
        pending: list = []
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                pending = msg.tool_calls
                break

        if not pending:
            _stream_graph(graph, None, config, metrics)
            continue

        _rc.print("\n  [dim]planned actions:[/dim]")
        for tc in pending:
            name = tc.get("name", tc.get("type", "unknown"))
            args = tc.get("args", tc.get("arguments", {}))
            flag = "  [bold red]⚠[/bold red]" if name in DANGEROUS_TOOL_NAMES else ""
            _rc.print(f"  [cyan]▸[/cyan]{flag}  [cyan]{name}[/cyan]  [dim]{_format_args(args)[:80]}[/dim]")

        try:
            answer = input("\n  Proceed? [y]es / [n]o / [q]uit: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            answer = "q"

        if answer == "q":
            _print_run_footer(metrics, time.monotonic() - t0)
            return AgentResult(
                success=False,
                final_answer="Task cancelled by user.",
                steps=[],
                metrics=metrics,
            )

        if answer in ("y", "yes", ""):
            _stream_graph(graph, None, config, metrics)
        else:
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
            _stream_graph(graph, None, config, metrics)

    state = graph.get_state(config)
    metrics["approx_tokens"] = _approx_tokens(state.values.get("messages", []))
    _print_run_footer(metrics, time.monotonic() - t0)
    return AgentResult(
        success=True,
        final_answer=_extract_final_answer(state.values),
        steps=[],
        metrics=metrics,
    )


def _run_plan(
    llm, task: str, system_prompt: str, config: dict,
    verbose: bool, metrics: dict, resolved_tid: str | None = None,
    session_name: Optional[str] = None,
) -> AgentResult:
    """Plan-then-execute mode.

    Phase 1 — Planning: chat graph generates a numbered plan (silent=True suppresses
    the duplicate response panel). User reviews and can accept / edit / reject.

    Phase 2 — Execution: agent graph with approved plan injected into system prompt.
    """
    planning_prompt = system_prompt + PLANNING_SUFFIX

    def _generate_plan(prompt_text: str, extra_context: str = "") -> str:
        """Run one planning pass. silent=True prevents the duplicate panel."""
        plan_config = {"configurable": {"thread_id": f"plan_{uuid.uuid4()}"}}
        plan_graph = build_chat_graph(llm, planning_prompt)
        user_msg = prompt_text
        if extra_context:
            user_msg = extra_context + "\n\n" + prompt_text
        _stream_graph(
            plan_graph,
            {"messages": [HumanMessage(content=user_msg)]},
            plan_config,
            silent=True,
        )
        state = plan_graph.get_state(plan_config)
        return _extract_final_answer(state.values)

    _rc.print()
    _rc.print(Rule(
        "[bold purple]plan[/bold purple]  [dim]·[/dim]  "
        f"[dim]{metrics.get('model', '')}[/dim]"
        + (f"  [dim]·[/dim]  [dim]◆  {session_name}[/dim]" if session_name else ""),
        style="dim purple",
    ))
    _rc.print()
    _rc.print("[dim]  generating plan...[/dim]")

    plan_text = _generate_plan(task)

    for _ in range(3):
        _rc.print()
        _rc.print(Panel(
            Markdown(plan_text),
            title="[bold purple]◆  proposed plan[/bold purple]",
            title_align="left",
            border_style="dim purple",
            box=rich_box.ROUNDED,
            padding=(1, 2),
        ))

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
                metrics=metrics,
            )

        if answer in ("y", "yes", ""):
            break

        if answer.startswith("e"):
            try:
                feedback = input("  Your feedback: ").strip()
            except (KeyboardInterrupt, EOFError):
                return AgentResult(
                    success=False,
                    final_answer="Plan cancelled.",
                    steps=[],
                    metrics=metrics,
                )
            if feedback:
                _rc.print("\n[dim]  revising plan...[/dim]")
                revision_context = (
                    f"Task: {task}\n\n"
                    f"Previous plan:\n{plan_text}\n\n"
                    f"User feedback: {feedback}\n\n"
                    "Please revise the plan to incorporate this feedback."
                )
                plan_text = _generate_plan(task, extra_context=revision_context)
            continue

    # ------------------------------------------------------------------ #
    # Phase 2: execution                                                  #
    # ------------------------------------------------------------------ #
    execution_prompt = (
        system_prompt
        + "\n\n## Approved Plan\n"
        "Follow this plan step by step to complete the task:\n\n"
        + plan_text
        + "\n"
    )

    _rc.print()
    _rc.print(Rule(
        "[bold purple]execute[/bold purple]  [dim]·[/dim]  "
        f"[dim]{metrics.get('model', '')}[/dim]"
        + (f"  [dim]·[/dim]  [dim]◆  {session_name}[/dim]" if session_name else ""),
        style="dim purple",
    ))
    _rc.print()

    t0 = time.monotonic()
    exec_tid = f"agent_{resolved_tid}" if resolved_tid else f"plan_exec_{uuid.uuid4()}"
    exec_config = {"configurable": {"thread_id": exec_tid}}
    hook = _make_summarize_hook(llm, metrics)
    agent_graph = build_agent_graph(llm, ALL_TOOLS, execution_prompt, pre_model_hook=hook)
    _stream_graph(
        agent_graph,
        {"messages": [HumanMessage(content=task)]},
        exec_config,
        metrics,
    )

    exec_state = agent_graph.get_state(exec_config)
    metrics["approx_tokens"] = _approx_tokens(exec_state.values.get("messages", []))
    _print_run_footer(metrics, time.monotonic() - t0)
    return AgentResult(
        success=True,
        final_answer=_extract_final_answer(exec_state.values),
        steps=[],
        metrics=metrics,
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
    session_name: Optional[str] = None,
) -> AgentResult:
    """Run an agent task in the specified mode.

    Args:
        task:         The user's request / instruction.
        mode:         One of 'agent', 'chat', 'assist', 'plan'.
        provider:     AI provider ('gemini', 'anthropic', 'openai', 'openrouter').
                      Defaults to the configured default provider.
        model:        Model identifier. Defaults to the provider's default model.
        thread_id:    Conversation thread ID for memory continuity.
        verbose:      Whether to print progress messages.
        session_name: Human-readable session name shown in the run header.

    Returns:
        AgentResult with success flag and final_answer text.
    """
    try:
        resolved_provider, api_key, resolved_model = _resolve_provider_model(
            provider, model
        )
        llm = build_model(resolved_provider, api_key, resolved_model)
        system_prompt = _build_system_prompt()

        resolved_tid = thread_id or str(uuid.uuid4())
        scoped_tid = f"{mode}_{resolved_tid}"
        config = {"configurable": {"thread_id": scoped_tid}}

        metrics: dict = {"model": resolved_model, "condensations": 0}

        if mode == "agent":
            return _run_agent(llm, task, system_prompt, config, verbose, metrics, session_name)
        elif mode == "chat":
            return _run_chat(llm, task, system_prompt, config, verbose, metrics, session_name)
        elif mode == "assist":
            return _run_assist(llm, task, system_prompt, config, verbose, metrics, session_name)
        elif mode == "plan":
            return _run_plan(llm, task, system_prompt, config, verbose, metrics, resolved_tid, session_name)
        else:
            return AgentResult(
                success=False,
                final_answer=f"Unknown mode: '{mode}'. Valid modes: agent, chat, assist, plan.",
                steps=[],
            )

    except Exception as e:
        err_str = str(e)
        if "INVALID_CHAT_HISTORY" in err_str and "tool_calls" in err_str:
            try:
                cp = get_checkpointer()
                scoped_tid_local = f"{mode}_{thread_id}" if thread_id else None
                if scoped_tid_local:
                    cp.delete_thread(scoped_tid_local)
                    _rc.print(
                        "\n  [yellow]⚠[/yellow]  [dim]Corrupt checkpoint — session reset. Retrying...[/dim]"
                    )
                    return run_agent(task, mode=mode, provider=provider, model=model,
                                     thread_id=thread_id, verbose=verbose,
                                     session_name=session_name)
            except Exception:
                pass
        return AgentResult(
            success=False,
            final_answer=f"Error: {e}",
            steps=[],
        )


# Alias kept for backward compatibility
run_agent_interactive = run_agent


def test_providers() -> dict:
    """Test which providers have valid API keys configured."""
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
            llm.invoke("ping")
            results[name] = {"status": "ok"}
        except Exception as e:
            err = str(e).lower()
            if "authentication" in err or "api key" in err or "invalid" in err:
                results[name] = {"status": "invalid_key"}
            else:
                results[name] = {"status": "error", "error": str(e)}

    return results
