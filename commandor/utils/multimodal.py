"""Multimodal content utilities for sending images to vision-capable LLMs.

Public API:
    encode_image_to_data_url(path) -> str
        Read a local image file and return a base64 data: URL suitable
        for inclusion in an OpenAI / Anthropic / Gemini multimodal
        message.
    build_multimodal_message(text, image_paths) -> list[dict]
        Convert text + image paths to a list of content blocks
        (compatible with langchain_core.messages.HumanMessage content).
    is_image_file(path) -> bool

Multimodal support requires the chosen model to support vision
(Gemini, Claude 3+, GPT-4o, GPT-4-Turbo, etc.).  This module does
NOT check that — it's a transport-level helper.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Iterable

# Conservative size limit for inline images (5 MB).
# Above this, the LLM API will reject the request.
MAX_IMAGE_BYTES = 5 * 1024 * 1024

_IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".heic",
}


def is_image_file(path: str | Path) -> bool:
    """True if *path* looks like an image (by extension)."""
    p = Path(path)
    return p.suffix.lower() in _IMAGE_EXTENSIONS


def _guess_mime(path: Path) -> str:
    """Return a MIME type for *path*, falling back to application/octet-stream."""
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def encode_image_to_data_url(path: str | Path) -> str:
    """Read an image file and return a base64 data URL.

    Format: ``data:<mime>;base64,<payload>``

    Raises FileNotFoundError, ValueError (if too large), or OSError.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    if not p.is_file():
        raise ValueError(f"Not a file: {path}")
    if p.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError(
            f"Image too large: {p.stat().st_size:,} bytes (max {MAX_IMAGE_BYTES:,})"
        )

    mime = _guess_mime(p)
    payload = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def build_multimodal_message(
    text: str,
    image_paths: Iterable[str | Path] = (),
) -> list[dict]:
    """Build a list of content blocks combining text and inline images.

    Output is compatible with the LangChain HumanMessage content list
    format: a list of dicts, each with a 'type' key.

    Returns:
        [
            {"type": "text", "text": "..."},
            {"type": "image_url", "image_url": {"url": "data:..."}},
            ...
        ]

    Raises:
        FileNotFoundError, ValueError: see encode_image_to_data_url.
    """
    blocks: list[dict] = []
    if text:
        blocks.append({"type": "text", "text": text})
    for img in image_paths:
        url = encode_image_to_data_url(img)
        blocks.append({
            "type": "image_url",
            "image_url": {"url": url},
        })
    return blocks
