"""Tests for TUI agent streaming bridge helpers."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from commandor.agent_bridge import (
    _build_recovery_prompt,
    _extract_current_turn_answer,
    _is_empty_generation_error,
)


def test_empty_generation_error_detection():
    assert _is_empty_generation_error(Exception("No generations found in stream."))
    assert not _is_empty_generation_error(Exception("different provider error"))


def test_extract_current_turn_answer_ignores_previous_ai_message():
    state = {
        "messages": [
            HumanMessage(content="old question"),
            AIMessage(content="old answer"),
            HumanMessage(content="new question"),
            AIMessage(content=""),
        ]
    }

    assert _extract_current_turn_answer(state) == "Task completed."


def test_build_recovery_prompt_uses_current_tool_output_only():
    state = {
        "messages": [
            HumanMessage(content="old question"),
            ToolMessage(content="old tool output", tool_call_id="old"),
            HumanMessage(content="new question"),
            ToolMessage(content="new tool output", tool_call_id="new"),
        ]
    }

    prompt = _build_recovery_prompt("new question", state)
    assert "new tool output" in prompt
    assert "old tool output" not in prompt
