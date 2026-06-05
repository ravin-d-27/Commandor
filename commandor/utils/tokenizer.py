"""Accurate token counting via tiktoken with a char-based fallback.

Public API:
    count_tokens(text, model="gpt-4o") -> int
    count_message_tokens(messages, model="gpt-4o") -> int
    get_encoding(model="gpt-4o") -> tiktoken.Encoding

Why tiktoken?
    The previous implementation used `len(text) // 4` which is wildly
    inaccurate for code (lots of symbols, short tokens).  tiktoken gives
    the exact same count the OpenAI / Anthropic-compatible tokenizer
    would, so the context-window bar and the condensation threshold
    become reliable.

For non-OpenAI models we still fall back to cl100k_base (used by GPT-4
    and Claude) which is a much better approximation than chars/4.
"""

from __future__ import annotations

import threading
from typing import Optional

try:
    import tiktoken
    _HAS_TIKTOKEN = True
except ImportError:  # pragma: no cover - optional dep
    tiktoken = None  # type: ignore[assignment]
    _HAS_TIKTOKEN = False


# ---------------------------------------------------------------------------
# Encoding cache (one encoding per model name)
# ---------------------------------------------------------------------------

_encoding_cache: dict[str, "tiktoken.Encoding | None"] = {}
_cache_lock = threading.Lock()


def get_encoding(model: str = "gpt-4o"):
    """Return a tiktoken.Encoding for *model* (cached).

    Returns None if tiktoken is unavailable.  Falls back to cl100k_base
    for unknown model names.
    """
    if not _HAS_TIKTOKEN:
        return None

    with _cache_lock:
        if model in _encoding_cache:
            return _encoding_cache[model]

        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            try:
                enc = tiktoken.get_encoding("cl100k_base")
            except Exception:
                enc = None

        _encoding_cache[model] = enc
        return enc


# Map well-known models to their canonical tiktoken encoding name.
# This avoids calling encoding_for_model() (which downloads a mapping
# from the internet) for models that obviously use cl100k or o200k.
_TIKTOKEN_MODEL_HINTS: dict[str, str] = {
    "gpt-4": "cl100k_base",
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
    "o1": "o200k_base",
    "o1-mini": "o200k_base",
    "o3-mini": "o200k_base",
    "claude": "cl100k_base",
    "llama": "cl100k_base",
    "gemini": "cl100k_base",
    "deepseek": "cl100k_base",
}


def _pick_encoding_name(model: str) -> Optional[str]:
    """Best-effort: return a tiktoken encoding name for *model*."""
    m = (model or "").lower()
    for prefix, enc_name in _TIKTOKEN_MODEL_HINTS.items():
        if prefix in m:
            return enc_name
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Return the token count for *text* using tiktoken.

    Falls back to `len(text) // 4` if tiktoken is not installed.
    """
    if not text:
        return 0
    enc = get_encoding(model)
    if enc is not None:
        try:
            return len(enc.encode(text, disallowed_special=()))
        except Exception:
            pass
    # Fallback: chars/4 — still better than nothing
    return len(text) // 4


def count_message_tokens(messages, model: str = "gpt-4o") -> int:
    """Count tokens for a list of LangChain BaseMessage objects.

    Each message has a small per-message overhead (4 tokens for role
    markers and formatting, per OpenAI's cookbook).
    """
    if not _HAS_TIKTOKEN:
        # crude fallback
        total = 0
        for m in messages:
            content = getattr(m, "content", "") or ""
            total += len(str(content)) // 4 + 4
        return total

    enc_name = _pick_encoding_name(model) or "cl100k_base"
    try:
        enc = tiktoken.get_encoding(enc_name)
    except Exception:
        return sum(count_tokens(str(getattr(m, "content", "")), model) for m in messages)

    total = 0
    for m in messages:
        content = getattr(m, "content", "") or ""
        # Per-message overhead (matches OpenAI cookbook)
        total += 4
        if isinstance(content, str):
            try:
                total += len(enc.encode(content, disallowed_special=()))
            except Exception:
                total += len(content) // 4
        elif isinstance(content, list):
            # Multimodal content blocks (text + images)
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text = block.get("text", "")
                        try:
                            total += len(enc.encode(text, disallowed_special=()))
                        except Exception:
                            total += len(text) // 4
                    elif block.get("type") == "image_url":
                        # Images count as ~85 tokens for low-res,
                        # ~170 for high-res per OpenAI's spec.
                        total += 85
    return total


def is_accurate() -> bool:
    """True iff tiktoken is installed and working."""
    return _HAS_TIKTOKEN
