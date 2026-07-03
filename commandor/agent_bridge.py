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
from pathlib import Path
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
from .agent.plugins import get_all_tools_with_plugins
from .utils.multimodal import build_multimodal_message, is_image_file


# Gemini/LangChain can raise this after successful tool calls if the final
# streamed model response is empty. Treat it as recoverable in the TUI bridge.
_EMPTY_GENERATION_MARKER = "No generations found in stream"


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


def _is_empty_generation_error(exc: Exception) -> bool:
    """Return True for provider stream failures with no final generation."""
    return _EMPTY_GENERATION_MARKER in str(exc)


def _content_to_text(content) -> str:  # noqa: ANN001
    """Normalise LangChain message content into readable text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
        return "\n".join(p for p in parts if p)
    return str(content or "")


def _current_turn_messages(state_values: dict) -> list:
    """Return messages belonging to the latest user turn."""
    messages = state_values.get("messages", [])
    last_human_idx = -1
    for idx, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            last_human_idx = idx
    return messages[last_human_idx:] if last_human_idx >= 0 else messages


def _extract_current_turn_answer(state_values: dict) -> str:
    """Extract an AI answer without falling back to a previous turn."""
    return _extract_final_answer({"messages": _current_turn_messages(state_values)})


def _build_recovery_prompt(task: str, state_values: dict) -> str:
    """Build a compact synthesis prompt from current-turn tool results."""
    tool_sections: list[str] = []
    other_sections: list[str] = []

    for msg in _current_turn_messages(state_values):
        text = _content_to_text(getattr(msg, "content", "")).strip()
        if not text:
            continue
        if isinstance(msg, ToolMessage):
            tool_sections.append(text)
        elif not isinstance(msg, HumanMessage):
            other_sections.append(text)

    evidence = "\n\n---\n\n".join(tool_sections or other_sections)
    if len(evidence) > 12_000:
        evidence = evidence[-12_000:]

    return (
        "The agent used tools for the user task, but the provider returned an "
        "empty final streamed generation. Based only on the current turn's "
        "tool results below, write the final answer the user should see. "
        "If the evidence is incomplete, say what was found and what remains.\n\n"
        f"User task:\n{task}\n\n"
        f"Tool results:\n{evidence or '(no tool output captured)'}"
    )


def _recover_empty_generation(llm, task: str, state_values: dict) -> str:  # noqa: ANN001
    """Produce a final answer after an empty-generation stream failure."""
    current_answer = _extract_current_turn_answer(state_values)
    if current_answer.strip() and current_answer != "Task completed.":
        return current_answer

    prompt = _build_recovery_prompt(task, state_values)
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        text = _content_to_text(getattr(response, "content", response)).strip()
        if text:
            return text
    except Exception:
        pass

    return (
        "I used tools and gathered results for this task, but the model returned "
        "an empty final response before it could synthesize them. Please retry, "
        "or ask a narrower follow-up and I can continue from the visible output."
    )


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
        candidate = _extract_current_turn_answer(state.values)
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
    image_paths: Optional[list[str]] = None,
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
        image_paths:  Optional list of local image paths to attach to the
                      first user message as multimodal content.  The chosen
                      model must support vision for this to be useful.
    """
    try:
        resolved_provider, api_key, resolved_model, resolved_base_url = _resolve_provider_model(
            provider, model
        )
    except ValueError as e:
        yield ErrorEvent(message=str(e))
        return

    try:
        llm = build_model(
            resolved_provider, api_key, resolved_model, base_url=resolved_base_url
        )
    except Exception as e:
        yield ErrorEvent(message=f"Failed to initialise model: {e}")
        return

    # Expose active model to the tokenizer so _approx_tokens picks the right one
    import commandor.agent.executor as _executor_mod
    _executor_mod._active_model = resolved_model

    system_prompt = _build_system_prompt()
    resolved_tid = thread_id or str(uuid.uuid4())

    effective_mode = "agent" if mode not in ("agent", "chat") else mode

    scoped_tid = f"{effective_mode}_{resolved_tid}"
    config: dict = {"configurable": {"thread_id": scoped_tid}}
    metrics: dict = {"model": resolved_model, "condensations": 0}

    yield StatusEvent(message=f"{effective_mode}  ·  {resolved_model}"
                      + (f"  ·  {session_name}" if session_name else ""))

    # Build the first user message — multimodal if any images are attached.
    # Filter out non-image paths so callers can pass a generous list.
    valid_images = [p for p in (image_paths or []) if is_image_file(p)]
    invalid = [p for p in (image_paths or []) if not is_image_file(p)]
    if invalid:
        yield StatusEvent(
            message=f"⚠ Skipped {len(invalid)} non-image attachment(s): "
                    + ", ".join(Path(p).name for p in invalid[:3])
        )

    if valid_images:
        try:
            content_blocks = build_multimodal_message(task, valid_images)
            first_message = HumanMessage(content=content_blocks)
        except (FileNotFoundError, ValueError) as exc:
            yield ErrorEvent(message=f"Failed to attach image: {exc}")
            return
    else:
        first_message = HumanMessage(content=task)

    try:
        plan_queue: list = []
        _plan_tls.queue = plan_queue
        if effective_mode == "chat":
            graph = build_chat_graph(llm, system_prompt)
            input_data = {"messages": [first_message]}
            try:
                streamed_answer = yield from _iter_graph(graph, input_data, config, metrics)
            except Exception as exc:
                if not _is_empty_generation_error(exc):
                    raise
                state = graph.get_state(config)
                final = _recover_empty_generation(llm, task, state.values)
                yield TokenEvent(text=final)
                streamed_answer = final
            else:
                state = graph.get_state(config)
                final = _extract_current_turn_answer(state.values)
                if (not final.strip() or final == "Task completed.") and streamed_answer:
                    final = streamed_answer

        else:  # agent (default)
            hook = _make_summarize_hook(llm, metrics)
            tools = get_all_tools_with_plugins()
            graph = build_agent_graph(llm, tools, system_prompt, pre_model_hook=hook)
            input_data = {"messages": [first_message]}
            try:
                streamed_answer = yield from _iter_graph(
                    graph, input_data, config, metrics, plan_queue=plan_queue
                )
            except Exception as exc:
                if not _is_empty_generation_error(exc):
                    raise
                if plan_queue:
                    yield from _drain_plan_queue(plan_queue)
                state = graph.get_state(config)
                final = _recover_empty_generation(llm, task, state.values)
                yield TokenEvent(text=final)
                streamed_answer = final
            else:
                state = graph.get_state(config)
                final = _extract_current_turn_answer(state.values)
                if (not final.strip() or final == "Task completed.") and streamed_answer:
                    final = streamed_answer

        metrics["approx_tokens"] = _approx_tokens(
            state.values.get("messages", [])
        )
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
