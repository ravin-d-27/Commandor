"""Sub-agent delegation.

Allows the main agent to spawn short-lived, focused sub-agents that
work in parallel (or sequentially) on a subtask.  A sub-agent runs its
own graph, gets its own (scratch) thread_id, and returns a single string
result back to the caller.

Public API:
    delegate_task(subtask, mode, context) -> str
        Run *subtask* in a sub-agent.  Blocks until the sub-agent
        finishes.  Returns the sub-agent's final answer.
    parallel_delegate(tasks) -> list[str]
        Run multiple sub-tasks concurrently (max 4 in flight) using a
        ThreadPoolExecutor.  Returns results in the same order as *tasks*.

This module is intentionally minimal — the goal is to provide a working
delegation primitive, not a full multi-agent framework.  Use it for
things like:
    - "Review this PR while I work on the bug"
    - "Run these 3 doc lookups in parallel"
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .lc_graph import build_agent_graph, build_chat_graph, get_checkpointer
from .lc_models import build_model
from .plugins import get_all_tools_with_plugins

# Cap on concurrent sub-agents
_MAX_PARALLEL = 4

# Safety limit: a sub-agent should be a focused task, not a long session.
_MAX_ITERATIONS = 12


def _run_subagent(
    subtask: str,
    use_tools: bool,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    image_paths: Optional[list[str]] = None,
) -> str:
    """Run a single sub-agent and return its final answer text.

    Returns a plain string suitable for inclusion in a tool result.
    """
    # Import executor helpers lazily to avoid the startup cycle:
    # executor -> lc_tools -> subagent -> executor.
    from .executor import (  # noqa: PLC0415
        _build_first_message,
        _build_system_prompt,
        _make_summarize_hook,
        _resolve_provider_model,
    )

    try:
        resolved_provider, api_key, resolved_model, resolved_base_url = (
            _resolve_provider_model(provider, model)
        )
    except ValueError as exc:
        return f"[subagent error] {exc}"

    try:
        llm = build_model(
            resolved_provider, api_key, resolved_model, base_url=resolved_base_url
        )
    except Exception as exc:  # noqa: BLE001
        return f"[subagent error] Failed to build model: {exc}"

    sub_system_prompt = (
        _build_system_prompt()
        + "\n\n## Sub-agent context\n"
        "You are a Commandor sub-agent — a short-lived helper spawned by the main agent "
        "to handle a focused subtask.  Stay on-task, do not start new initiatives, and "
        "return a concise final answer.\n"
    )

    sub_tid = f"sub_{uuid.uuid4()}"
    sub_config = {"configurable": {"thread_id": sub_tid}, "recursion_limit": _MAX_ITERATIONS}

    first_message = _build_first_message(subtask, image_paths)

    if use_tools:
        graph = build_agent_graph(
            llm,
            get_all_tools_with_plugins(),
            sub_system_prompt,
            pre_model_hook=_make_summarize_hook(llm),
        )
    else:
        graph = build_chat_graph(llm, sub_system_prompt)

    final = ""
    try:
        for chunk, _meta in graph.stream(
            {"messages": [first_message]}, sub_config, stream_mode="messages"
        ):
            from langchain_core.messages import AIMessageChunk

            if isinstance(chunk, AIMessageChunk) and isinstance(chunk.content, str):
                final += chunk.content
    except Exception as exc:  # noqa: BLE001
        return f"[subagent error] {exc}"

    final = (final or "").strip()
    if not final:
        try:
            state = graph.get_state(sub_config)
            from .executor import _extract_final_answer
            final = _extract_final_answer(state.values)
        except Exception:  # noqa: BLE001
            final = "(subagent returned no answer)"

    # Free the sub-agent's checkpoint thread so it doesn't pile up.
    try:
        get_checkpointer().delete_thread(sub_tid)
    except Exception:  # noqa: BLE001
        pass

    return final.strip() or "(subagent returned no answer)"


def delegate_task(
    subtask: str,
    use_tools: bool = False,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Run *subtask* in a focused sub-agent and return its final answer.

    Args:
        subtask:   A self-contained instruction.  The sub-agent sees only
                   this text plus the base system prompt — it has no
                   access to the parent's conversation history.
        use_tools: If True, the sub-agent gets the same tool set as the
                   parent.  Default False (chat-only) is faster and
                   cheaper for lookups, summaries, etc.
        provider:  Override the provider (default: same as parent).
        model:     Override the model (default: same as parent).

    Returns:
        The sub-agent's final answer as a plain string.
    """
    if not subtask or not subtask.strip():
        return "[subagent error] Empty subtask."
    return _run_subagent(
        subtask.strip(),
        use_tools=use_tools,
        provider=provider,
        model=model,
    )


def parallel_delegate(
    tasks: list[dict],
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> list[dict]:
    """Run multiple sub-tasks concurrently and return their results.

    Args:
        tasks:    List of {"subtask": str, "use_tools": bool} dicts.
        provider: Optional provider override for all sub-agents.
        model:    Optional model override for all sub-agents.

    Returns:
        A list of {"subtask": str, "answer": str, "ok": bool} dicts in
        the same order as *tasks*.  Failures are captured as
        {"ok": False, "answer": "[subagent error] ..."}.
    """
    if not tasks:
        return []

    if len(tasks) > _MAX_PARALLEL:
        # Process the first N, queue the rest — keeps the executor small
        # while still allowing more than the cap.
        results: list[dict | None] = [None] * len(tasks)
        for chunk_start in range(0, len(tasks), _MAX_PARALLEL):
            chunk = tasks[chunk_start : chunk_start + _MAX_PARALLEL]
            chunk_results = parallel_delegate(chunk, provider=provider, model=model)
            for i, r in enumerate(chunk_results):
                results[chunk_start + i] = r
        return [r for r in results if r is not None]

    def _one(t: dict) -> dict:
        subtask = t.get("subtask", "")
        use_tools = bool(t.get("use_tools", False))
        answer = delegate_task(
            subtask, use_tools=use_tools, provider=provider, model=model
        )
        return {
            "subtask": subtask,
            "answer": answer,
            "ok": not answer.startswith("[subagent error]"),
        }

    results = []
    with ThreadPoolExecutor(max_workers=min(_MAX_PARALLEL, len(tasks))) as pool:
        futures = {pool.submit(_one, t): idx for idx, t in enumerate(tasks)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                results.append((idx, fut.result()))
            except Exception as exc:  # noqa: BLE001
                results.append((idx, {
                    "subtask": tasks[idx].get("subtask", ""),
                    "answer": f"[subagent error] {exc}",
                    "ok": False,
                }))

    # Re-order by original index
    results.sort(key=lambda pair: pair[0])
    return [r for _, r in results]
