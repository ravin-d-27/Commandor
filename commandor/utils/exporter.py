"""Conversation-log exporters for the /export slash command.

Public API:
    export_markdown(log, session_name) -> str
    export_json(log, session_name, metadata) -> str
    export_html(log, session_name, metadata) -> str
    export_for_format(fmt, log, session_name, metadata) -> str

Each exporter returns the file contents as a string.  The caller writes
the result to disk.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Any


def _safe_meta(metadata: dict) -> dict:
    """Return a sanitised copy of *metadata* (JSON-safe)."""
    out: dict[str, Any] = {}
    for k, v in metadata.items():
        try:
            json.dumps(v)
            out[k] = v
        except (TypeError, ValueError):
            out[k] = str(v)
    return out


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def export_markdown(
    log: list[dict],
    session_name: str | None = None,
    metadata: dict | None = None,
) -> str:
    """Render the conversation log as a Markdown document."""
    lines: list[str] = ["# Commandor Session Export\n"]
    if session_name:
        lines.append(f"**Session:** {session_name}  ")
    lines.append(f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    if metadata:
        for k, v in metadata.items():
            lines.append(f"**{k}:** {v}  ")
    lines.append("\n---\n")

    for entry in log:
        role = entry.get("role", "?")
        mode = entry.get("mode", "")
        content = entry.get("content", "")
        if role == "user":
            heading = f"## ▸ USER ({mode.upper()})" if mode else "## ▸ USER"
        elif role == "ai":
            heading = "## ◆ Commandor"
        else:
            heading = f"## {role}"
        lines.append(f"{heading}\n")
        lines.append(f"{content}\n")
        lines.append("\n---\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def export_json(
    log: list[dict],
    session_name: str | None = None,
    metadata: dict | None = None,
) -> str:
    """Render the conversation log as a JSON document (pretty-printed)."""
    payload = {
        "session_name": session_name,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "metadata": _safe_meta(metadata or {}),
        "messages": [
            {
                "role": e.get("role", "?"),
                "mode": e.get("mode"),
                "content": e.get("content", ""),
                "timestamp": e.get("timestamp"),
            }
            for e in log
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_HTML_CSS = """\
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0a0a0a; color: #f5ecd0;
    max-width: 880px; margin: 40px auto; padding: 0 24px;
    line-height: 1.5;
}
h1 { color: #ffd700; border-bottom: 2px solid #ffd700; padding-bottom: 8px; }
.meta { color: #7a6b4a; font-size: 0.9em; margin-bottom: 24px; }
.msg { border-left: 3px solid #2a1f00; padding: 8px 16px; margin: 16px 0;
       background: #0a0a0a; }
.msg.user { border-left-color: #c8a800; }
.msg.ai   { border-left-color: #ffd700; }
.role { font-weight: bold; color: #ffd700; font-size: 0.9em;
        text-transform: uppercase; letter-spacing: 0.05em; }
.role.user { color: #c8a800; }
pre { background: #000; color: #f5ecd0; padding: 12px;
      border: 1px solid #2a1f00; overflow-x: auto; border-radius: 4px; }
code { background: #1a1300; color: #ffd700; padding: 1px 6px; border-radius: 3px;
       font-family: 'SF Mono', 'Monaco', 'Consolas', monospace; }
pre code { background: transparent; color: inherit; padding: 0; }
.timestamp { color: #7a6b4a; font-size: 0.8em; }
"""


def _md_to_html(text: str) -> str:
    """Very small Markdown → HTML converter.

    Handles: paragraphs, fenced code blocks, inline code, bold, italic,
    bullet lists.  Anything else passes through escaped.
    """
    out: list[str] = []
    lines = text.splitlines()
    i = 0
    in_code = False
    in_list = False
    paragraph: list[str] = []

    def _flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            joined = " ".join(paragraph)
            out.append(f"<p>{_inline_md(joined)}</p>")
            paragraph = []

    def _inline_md(s: str) -> str:
        # inline code
        s = _replace_pairs(s, "`", "<code>", "</code>")
        # bold
        s = _replace_pairs(s, "**", "<strong>", "</strong>")
        # italic
        s = _replace_pairs(s, "*", "<em>", "</em>")
        return s

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            _flush_paragraph()
            if in_list:
                out.append("</ul>")
                in_list = False
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                lang = stripped[3:].strip() or "text"
                out.append(f'<pre><code class="language-{html.escape(lang)}">')
                in_code = True
            i += 1
            continue
        if in_code:
            out.append(html.escape(line))
            i += 1
            continue

        if not stripped:
            _flush_paragraph()
            if in_list:
                out.append("</ul>")
                in_list = False
            i += 1
            continue

        if stripped.startswith(("- ", "* ")):
            _flush_paragraph()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline_md(stripped[2:])}</li>")
            i += 1
            continue

        if stripped.startswith("# "):
            _flush_paragraph()
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h1>{html.escape(stripped[2:])}</h1>")
            i += 1
            continue

        if stripped.startswith("## "):
            _flush_paragraph()
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h2>{html.escape(stripped[3:])}</h2>")
            i += 1
            continue

        paragraph.append(stripped)
        i += 1

    _flush_paragraph()
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def _replace_pairs(s: str, marker: str, open_tag: str, close_tag: str) -> str:
    """Replace paired *marker* in *s* with *open_tag* / *close_tag*."""
    parts = s.split(marker)
    if len(parts) < 3:
        return s
    out = parts[0]
    for idx, p in enumerate(parts[1:-1], start=1):
        if idx % 2 == 1:
            out += open_tag + p + close_tag
        else:
            out += marker + p + marker
    out += marker + parts[-1]
    return out


def export_html(
    log: list[dict],
    session_name: str | None = None,
    metadata: dict | None = None,
) -> str:
    """Render the conversation log as a self-contained HTML document."""
    meta_safe = _safe_meta(metadata or {})

    parts: list[str] = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>Commandor — {html.escape(session_name or 'Session')}</title>",
        f"<style>{_HTML_CSS}</style>",
        "</head>",
        "<body>",
        f"<h1>◆ Commandor — {html.escape(session_name or 'Session')}</h1>",
        '<div class="meta">',
        f"<div>Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>",
    ]
    for k, v in meta_safe.items():
        parts.append(f"<div>{html.escape(str(k))}: {html.escape(str(v))}</div>")
    parts.append("</div>")

    for entry in log:
        role = entry.get("role", "?")
        mode = entry.get("mode", "")
        content = entry.get("content", "")
        ts = entry.get("timestamp", "")
        if role == "user":
            role_label = f"USER · {mode.upper()}" if mode else "USER"
        elif role == "ai":
            role_label = "◆ COMMANDOR"
        else:
            role_label = role.upper()

        parts.append(f'<div class="msg {role}">')
        parts.append(f'<div class="role {role}">{html.escape(role_label)}</div>')
        if ts:
            parts.append(f'<div class="timestamp">{html.escape(str(ts))}</div>')
        parts.append(_md_to_html(content))
        parts.append("</div>")

    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

EXPORTERS = {
    "md":       ("markdown", export_markdown),
    "markdown": ("markdown", export_markdown),
    "json":     ("json",     export_json),
    "html":     ("html",     export_html),
}


def export_for_format(
    fmt: str,
    log: list[dict],
    session_name: str | None = None,
    metadata: dict | None = None,
) -> tuple[str, str]:
    """Return (content, suggested_extension) for the given *fmt* ('md', 'json', 'html')."""
    fmt = (fmt or "md").lower().lstrip(".")
    if fmt not in EXPORTERS:
        raise ValueError(
            f"Unknown export format: '{fmt}'.  "
            f"Supported: {', '.join(sorted(EXPORTERS))}"
        )
    label, fn = EXPORTERS[fmt]
    return fn(log, session_name, metadata), fmt
