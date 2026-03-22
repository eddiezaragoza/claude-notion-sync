"""
notion_to_md.py -- Convert Notion block objects back to markdown text.

Handles:
  - heading_1/2/3  ->  # / ## / ###
  - paragraph      ->  plain text line
  - bulleted_list_item  ->  - item
  - numbered_list_item  ->  1. item
  - code           ->  ```lang\ncontent\n```
  - divider        ->  ---
  - to_do          ->  - [x] or - [ ]
  - quote/callout  ->  > text

Rich text annotations:
  bold             ->  **text**
  italic           ->  *text*
  strikethrough    ->  ~~text~~
  code             ->  `text`

Unknown block types are silently skipped.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    """Convert a list of Notion block dicts to a markdown string."""
    lines: list[str] = []
    for block in blocks:
        block_type = block.get("type", "")
        handler = _HANDLERS.get(block_type)
        if handler is None:
            continue
        lines.append(handler(block))
    return "".join(lines)


# ---------------------------------------------------------------------------
# Block handlers
# ---------------------------------------------------------------------------

def _handle_heading(level: int, block: dict[str, Any]) -> str:
    key = f"heading_{level}"
    rich_text = block[key].get("rich_text", [])
    prefix = "#" * level
    return f"{prefix} {_render_rich_text(rich_text)}\n"


def _handle_paragraph(block: dict[str, Any]) -> str:
    rich_text = block["paragraph"].get("rich_text", [])
    return f"{_render_rich_text(rich_text)}\n"


def _handle_bulleted(block: dict[str, Any]) -> str:
    rich_text = block["bulleted_list_item"].get("rich_text", [])
    return f"- {_render_rich_text(rich_text)}\n"


def _handle_numbered(block: dict[str, Any]) -> str:
    rich_text = block["numbered_list_item"].get("rich_text", [])
    return f"1. {_render_rich_text(rich_text)}\n"


def _handle_code(block: dict[str, Any]) -> str:
    rich_text = block["code"].get("rich_text", [])
    lang = block["code"].get("language", "plain text")
    # "plain text" -> omit language label for clean markdown
    lang_label = "" if lang == "plain text" else lang
    content = _render_rich_text(rich_text)
    return f"```{lang_label}\n{content}\n```\n"


def _handle_divider(_block: dict[str, Any]) -> str:
    return "---\n"


def _handle_to_do(block: dict[str, Any]) -> str:
    rich_text = block["to_do"].get("rich_text", [])
    checked = block["to_do"].get("checked", False)
    mark = "x" if checked else " "
    return f"- [{mark}] {_render_rich_text(rich_text)}\n"


def _handle_quote(block: dict[str, Any]) -> str:
    rich_text = block["quote"].get("rich_text", [])
    return f"> {_render_rich_text(rich_text)}\n"


def _handle_callout(block: dict[str, Any]) -> str:
    rich_text = block["callout"].get("rich_text", [])
    return f"> {_render_rich_text(rich_text)}\n"


# Dispatch table -- maps Notion block type -> handler function
_HANDLERS: dict[str, Any] = {
    "heading_1":          lambda b: _handle_heading(1, b),
    "heading_2":          lambda b: _handle_heading(2, b),
    "heading_3":          lambda b: _handle_heading(3, b),
    "paragraph":          _handle_paragraph,
    "bulleted_list_item": _handle_bulleted,
    "numbered_list_item": _handle_numbered,
    "code":               _handle_code,
    "divider":            _handle_divider,
    "to_do":              _handle_to_do,
    "quote":              _handle_quote,
    "callout":            _handle_callout,
}


# ---------------------------------------------------------------------------
# Rich text rendering
# ---------------------------------------------------------------------------

def _render_rich_text(rich_text: list[dict[str, Any]]) -> str:
    """Render a list of Notion rich_text segments into a markdown string."""
    parts: list[str] = []
    for segment in rich_text:
        content = segment.get("text", {}).get("content", "")
        annotations = segment.get("annotations", {})
        content = _apply_annotations(content, annotations)
        parts.append(content)
    return "".join(parts)


def _apply_annotations(text: str, annotations: dict[str, Any]) -> str:
    """Wrap text with markdown markers based on Notion annotations."""
    if not text:
        return text

    # Apply in a stable order: code wins over others (can't nest inside code)
    if annotations.get("code"):
        return f"`{text}`"

    # Bold and italic can combine
    if annotations.get("bold") and annotations.get("italic"):
        return f"***{text}***"
    if annotations.get("bold"):
        text = f"**{text}**"
    if annotations.get("italic"):
        text = f"*{text}*"
    if annotations.get("strikethrough"):
        text = f"~~{text}~~"

    return text
