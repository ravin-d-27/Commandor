"""agent_bridge.py — TUI-friendly streaming interface for the LangGraph agent.

Instead of printing Rich output to stdout (like executor.py does), this module
yields typed event dataclasses that the Textual UI can consume and render
inside its own widgets.

Usage (in a Textual @work(thread=True) worker):

    for event in stream_agent_events(task, mode=mode, ...):
        if isinstance(event, TokenEvent):
            self.app.call_from_thread(self._on_token, event.text)
        elif isinstance(event, ToolCallEvent):
            self.app.call_from_thread(self._on_tool_call, event)
        ...
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Generator, Optional

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from .agent.executor import (
    _approx_tokens,
    _build_system_prompt,
    _extract_final_answer,
    _make_summarize_hook,
    _resolve_provider_model,
)
from .agent.lc_graph import (
    build_agent_graph,
    build_chat_graph,
    get_checkpointer,
)
from .agent.lc_models import build_model
from .agent.lc_tools import ALL_TOOLS, _plan_tls


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

@dataclass
class ThinkingEvent:
    """Incremental thinking/reasoning token."""
    text: str


@dataclass
class TokenEvent:
    """Incremental text response token."""
    text: str


@dataclass
class ToolCallEvent:
    """Agent is about to call a tool."""
    name: str
    args_preview: str
    is_dangerous: bool = False


@dataclass
class ToolOutputEvent:
    """Result from a tool execution."""
    tool_name: str
    content: str
    line_count: int


@dataclass
class StatusEvent:
    """Informational status message (thinking spinner, condensation notice, etc.)."""
    message: str


@dataclass
class ErrorEvent:
    """An error occurred."""
    message: str


@dataclass
class DoneEvent:
    """Stream finished. Contains final answer and metrics."""
    final_answer: str
    metrics: dict = field(default_factory=dict)


@dataclass
class PlanCreatedEvent:
    """Agent called create_task_plan — a new todo list to display."""
    items: list


@dataclass
class PlanItemDoneEvent:
    """Agent called complete_task — tick off one item in the todo list."""
    index: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _drain_plan_queue(plan_queue: list) -> Generator:
    """Yield PlanCreatedEvent / PlanItemDoneEvent from the thread-local queue."""
    while plan_queue:
        ev = plan_queue.pop(0)
        if ev[0] == "plan_created":
            yield PlanCreatedEvent(items=ev[1])
        elif ev[0] == "task_done":
            yield PlanItemDoneEvent(index=ev[1])


def _iter_graph(
    graph,
    input_data,
    config: dict,
    metrics: dict | None = None,
    plan_queue: list | None = None,
) -> Generator:
    """Core streaming loop — yields typed events instead of printing to stdout."""
    from .agent.lc_tools import DANGEROUS_TOOL_NAMES  # noqa: PLC0415

    accumulated = ""
    thinking_accumulated = ""
    seen_call_ids: dict[str, str] = {}
    last_usage = None

    for chunk, _meta in graph.stream(input_data, config, stream_mode="messages"):

        # Drain plan events pushed by the previous tool execution
        if plan_queue:
            yield from _drain_plan_queue(plan_queue)

        # ----------------------------------------------------------------
        # ToolMessage — result of a tool call
        # ----------------------------------------------------------------
        if isinstance(chunk, ToolMessage):
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
            yield ToolOutputEvent(
                tool_name=tool_name,
                content=content_str[:500],
                line_count=len(lines),
            )
            continue

        if not isinstance(chunk, AIMessageChunk):
            continue

        # -- Track usage metadata --
        usage = getattr(chunk, "usage_metadata", None)
        if usage:
            last_usage = usage

        # -- Thinking blocks --
        if isinstance(chunk.content, list):
            for block in chunk.content:
                if isinstance(block, dict) and block.get("type") == "thinking":
                    new_thinking = block.get("thinking", "")
                    if new_thinking:
                        thinking_accumulated += new_thinking
                        yield ThinkingEvent(text=new_thinking)

        # -- Tool calls --
        tcc = getattr(chunk, "tool_call_chunks", []) or []
        for tc in tcc:
            name = (tc.get("name") or "").strip()
            call_id = (tc.get("id") or "").strip()
            if name and call_id and call_id not in seen_call_ids:
                seen_call_ids[call_id] = name
                raw_args = tc.get("args") or ""
                args_preview = (
                    str(raw_args)[:80] + "…"
                    if len(str(raw_args)) > 80
                    else str(raw_args)
                )
                yield ToolCallEvent(
                    name=name,
                    args_preview=args_preview,
                    is_dangerous=name in DANGEROUS_TOOL_NAMES,
                )

        # -- Text tokens --
        if isinstance(chunk.content, str) and chunk.content:
            accumulated += chunk.content
            yield TokenEvent(text=chunk.content)

    # -- Update metrics --
    if metrics is not None and last_usage:
        metrics["input_tokens"] = (
            last_usage.get("input_tokens") or last_usage.get("prompt_tokens")
        )
        metrics["output_tokens"] = (
            last_usage.get("output_tokens") or last_usage.get("completion_tokens")
        )

    # -- Drain any remaining plan events from the last tool call --
    if plan_queue:
        yield from _drain_plan_queue(plan_queue)

    # -- Final answer fallback (Gemini often returns no streaming tokens) --
    if not accumulated.strip():
        state = graph.get_state(config)
        candidate = _extract_final_answer(state.values)
        if candidate.strip() and candidate != "Task completed.":
            accumulated = candidate
            yield TokenEvent(text=accumulated)  # emit the whole answer as one token

    # Return via generator (caller reads the accumulated value from DoneEvent)
    return accumulated


# ---------------------------------------------------------------------------
# Public streaming API
# ---------------------------------------------------------------------------

def stream_agent_events(
    task: str,
    mode: str = "agent",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    thread_id: Optional[str] = None,
    session_name: Optional[str] = None,
) -> Generator:
    """Stream agent execution events for a Textual worker thread.

    Yields a sequence of typed events:
        StatusEvent, ThinkingEvent, TokenEvent, ToolCallEvent,
        ToolOutputEvent, ErrorEvent, DoneEvent

    The final event is always DoneEvent (or ErrorEvent if something fails).

    Args:
        task:         The user's message/task.
        mode:         'agent' (autonomous, uses tools) or 'chat' (no tools).
        provider:     AI provider. Defaults to config default.
        model:        Model ID. Defaults to provider default.
        thread_id:    Session UUID for conversation memory.
        session_name: Human-readable name shown in UI headers.
    """
    try:
        resolved_provider, api_key, resolved_model = _resolve_provider_model(
            provider, model
        )
    except ValueError as e:
        yield ErrorEvent(message=str(e))
        return

    try:
        llm = build_model(resolved_provider, api_key, resolved_model)
    except Exception as e:
        yield ErrorEvent(message=f"Failed to initialise model: {e}")
        return

    system_prompt = _build_system_prompt()
    resolved_tid = thread_id or str(uuid.uuid4())

    effective_mode = "agent" if mode not in ("agent", "chat") else mode

    scoped_tid = f"{effective_mode}_{resolved_tid}"
    config: dict = {"configurable": {"thread_id": scoped_tid}}
    metrics: dict = {"model": resolved_model, "condensations": 0}

    yield StatusEvent(message=f"{effective_mode}  ·  {resolved_model}"
                      + (f"  ·  {session_name}" if session_name else ""))

    try:
        plan_queue: list = []
        _plan_tls.queue = plan_queue
        if effective_mode == "chat":
            graph = build_chat_graph(llm, system_prompt)
            input_data = {"messages": [HumanMessage(content=task)]}
            yield from _iter_graph(graph, input_data, config, metrics)
            state = graph.get_state(config)

        else:  # agent (default)
            hook = _make_summarize_hook(llm, metrics)
            graph = build_agent_graph(llm, ALL_TOOLS, system_prompt, pre_model_hook=hook)
            input_data = {"messages": [HumanMessage(content=task)]}
            yield from _iter_graph(graph, input_data, config, metrics, plan_queue=plan_queue)
            state = graph.get_state(config)

        metrics["approx_tokens"] = _approx_tokens(
            state.values.get("messages", [])
        )
        final = _extract_final_answer(state.values)
        yield DoneEvent(final_answer=final, metrics=metrics)

    except Exception as e:
        err = str(e)
        # Corrupt checkpoint recovery
        if "INVALID_CHAT_HISTORY" in err and "tool_calls" in err:
            try:
                cp = get_checkpointer()
                cp.delete_thread(scoped_tid)
                yield StatusEvent(message="Corrupt checkpoint reset — retrying…")
                yield from stream_agent_events(
                    task, mode=mode, provider=provider, model=model,
                    thread_id=thread_id, session_name=session_name,
                )
                return
            except Exception:
                pass
        yield ErrorEvent(message=f"Agent error: {e}")
    finally:
        _plan_tls.queue = None
