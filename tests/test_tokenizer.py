"""Tests for commandor.utils.tokenizer."""
from dataclasses import dataclass

import pytest

from commandor.utils.tokenizer import (
    _pick_encoding_name,
    count_message_tokens,
    count_tokens,
    get_encoding,
    is_accurate,
)


@dataclass
class _FakeMessage:
    content: object


class TestPickEncodingName:
    @pytest.mark.parametrize("model,expected", [
        ("gpt-4o", "o200k_base"),
        ("gpt-4o-mini", "o200k_base"),
        ("gpt-4", "cl100k_base"),
        ("gpt-4-turbo", "cl100k_base"),
        ("gpt-3.5-turbo", "cl100k_base"),
        ("o1-mini", "o200k_base"),
        ("o3-mini", "o200k_base"),
        ("claude-3.5-sonnet", "cl100k_base"),
        ("llama3.1", "cl100k_base"),
        ("gemini-2.5-flash", "cl100k_base"),
        ("deepseek-chat", "cl100k_base"),
    ])
    def test_known_models(self, model, expected):
        assert _pick_encoding_name(model) == expected

    def test_unknown_returns_none(self):
        assert _pick_encoding_name("some-new-experimental-model") is None

    def test_empty_returns_none(self):
        assert _pick_encoding_name("") is None


class TestCountTokens:
    def test_empty_text(self):
        assert count_tokens("") == 0

    def test_simple_text(self):
        n = count_tokens("hello world")
        assert n >= 1
        # If tiktoken is available, expect 2 tokens; fallback gives 2 (len 11 // 4 = 2).
        assert n <= 5

    def test_long_text_scales_sublinearly(self):
        short = count_tokens("hello")
        long = count_tokens("hello " * 200)
        assert long > short
        assert long < 1000  # sanity: not absurd

    def test_count_tokens_falls_back_when_encoding_unavailable(self, monkeypatch):
        from commandor.utils import tokenizer

        monkeypatch.setattr(tokenizer, "get_encoding", lambda model=None: None)
        # 20 chars / 4 = 5
        assert count_tokens("x" * 20) == 5
        assert count_tokens("x" * 0) == 0


class TestCountMessageTokens:
    def test_string_content_includes_overhead(self):
        msgs = [_FakeMessage("hello")]
        n = count_message_tokens(msgs)
        # 4 (overhead) + tokens for "hello" → at least 5
        assert n >= 5

    def test_multimodal_blocks(self):
        msgs = [
            _FakeMessage([
                {"type": "text", "text": "look at this"},
                {"type": "image_url", "image_url": {"url": "data:..."}},
            ])
        ]
        n = count_message_tokens(msgs)
        # text tokens + 4 (overhead) + 85 (image) ≥ 90
        assert n >= 90

    def test_empty_message_list(self):
        assert count_message_tokens([]) == 0

    def test_unknown_content_type_coerced(self):
        msgs = [_FakeMessage(12345)]  # int content
        n = count_message_tokens(msgs)
        assert n >= 0  # no crash


class TestIsAccurate:
    def test_returns_bool(self):
        assert isinstance(is_accurate(), bool)


class TestGetEncoding:
    def test_caches_result(self):
        e1 = get_encoding("gpt-4o")
        e2 = get_encoding("gpt-4o")
        # Cached — same object
        assert e1 is e2
