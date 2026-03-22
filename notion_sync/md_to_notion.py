"""
md_to_notion.py -- Convert markdown text into Notion API block objects.

Handles:
  - Headings (h1/h2/h3)
  - Paragraphs
  - Bullet and numbered lists
  - Fenced code blocks (with language)
  - Horizontal rules
  - Markdown tables (rendered as code blocks -- Notion API table support is limited)
  - Inline formatting: **bold**, *italic*, ~~strikethrough~~, `inline code`
  - Rich text truncated at 2000 chars per Notion API limit
"""

from __future__ import annotations

import re
from typing import Any

# Notion API hard limit for rich_text content per segment
RICH_TEXT_LIMIT = 2000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def markdown_to_blocks(md: str) -> list[dict[str, Any]]:
    """Parse a markdown string and return a list of Notion block dicts."""
    lines = md.split("\n")
    blocks: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # -- Fenced code block ------------------------------------------------
        code_match = re.match(r"^```(\S*)\s*$", line)
        if code_match:
            lang = code_match.group(1).strip() or "plain text"
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not re.match(r"^```\s*$", lines[i]):
                code_lines.append(lines[i])
                i += 1
            content = "\n".join(code_lines)
            blocks.append(_code_block(content, lang))
            i += 1
            continue

        # -- Table (detect by leading pipe) -----------------------------------
        if line.startswith("|"):
            table_lines: list[str] = []
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            content = "\n".join(table_lines)
            blocks.append(_code_block(content, "plain text"))
            continue

        # -- Horizontal rule --------------------------------------------------
        if re.match(r"^---+\s*$", line):
            blocks.append({"type": "divider", "divider": {}})
            i += 1
            continue

        # -- Headings ---------------------------------------------------------
        heading_match = re.match(r"^(#{1,3})\s+(.*)", line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            block_type = f"heading_{level}"
            blocks.append({
                "type": block_type,
                block_type: {"rich_text": _parse_inline(text)},
            })
            i += 1
            continue

        # -- Bullet list item -------------------------------------------------
        bullet_match = re.match(r"^[-*]\s+(.*)", line)
        if bullet_match:
            text = bullet_match.group(1)
            blocks.append({
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": _parse_inline(text)},
            })
            i += 1
            continue

        # -- Numbered list item -----------------------------------------------
        numbered_match = re.match(r"^\d+\.\s+(.*)", line)
        if numbered_match:
            text = numbered_match.group(1)
            blocks.append({
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": _parse_inline(text)},
            })
            i += 1
            continue

        # -- Empty line (skip) ------------------------------------------------
        if not line.strip():
            i += 1
            continue

        # -- Paragraph (fallback) ---------------------------------------------
        blocks.append({
            "type": "paragraph",
            "paragraph": {"rich_text": _parse_inline(line)},
        })
        i += 1

    return blocks


def chunk_blocks(blocks: list[dict[str, Any]], max_size: int = 100) -> list[list[dict[str, Any]]]:
    """Split a list of Notion blocks into chunks of at most max_size.

    Notion's append-block-children endpoint accepts at most 100 blocks per call.
    """
    if not blocks:
        return []
    return [blocks[i:i + max_size] for i in range(0, len(blocks), max_size)]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_NOTION_LANGUAGES = {
    "abap", "abc", "agda", "arduino", "ascii art", "assembly", "bash", "basic",
    "bnf", "c", "c#", "c++", "clojure", "coffeescript", "coq", "css", "dart",
    "dhall", "diff", "docker", "ebnf", "elixir", "elm", "erlang", "f#", "flow",
    "fortran", "gherkin", "glsl", "go", "graphql", "groovy", "haskell", "hcl",
    "html", "idris", "java", "javascript", "json", "julia", "kotlin", "latex",
    "less", "lisp", "livescript", "llvm ir", "lua", "makefile", "markdown",
    "markup", "matlab", "mathematica", "mermaid", "nix", "notion formula",
    "objective-c", "ocaml", "pascal", "perl", "php", "plain text", "powershell",
    "prolog", "protobuf", "purescript", "python", "r", "racket", "reason", "ruby",
    "rust", "sass", "scala", "scheme", "scss", "shell", "smalltalk", "solidity",
    "sql", "swift", "toml", "typescript", "vb.net", "verilog", "vhdl",
    "visual basic", "webassembly", "xml", "yaml", "java/c/c++/c#",
}


def _normalize_language(lang: str) -> str:
    """Map a code fence language to a Notion-supported language."""
    if lang in _NOTION_LANGUAGES:
        return lang
    # Common aliases
    aliases = {
        "sh": "shell", "zsh": "shell", "py": "python", "js": "javascript",
        "ts": "typescript", "rb": "ruby", "rs": "rust", "yml": "yaml",
        "dockerfile": "docker", "apex": "java/c/c++/c#", "cls": "java/c/c++/c#",
        "trigger": "java/c/c++/c#", "soql": "sql", "sosl": "sql",
        "tf": "hcl", "jsx": "javascript", "tsx": "typescript",
    }
    return aliases.get(lang.lower(), "plain text")


def _code_block(content: str, language: str) -> dict[str, Any]:
    return {
        "type": "code",
        "code": {
            "rich_text": [_plain_text(content)],
            "language": _normalize_language(language),
        },
    }


def _plain_text(content: str) -> dict[str, Any]:
    """Return a plain (no annotation) rich_text segment, truncated at 2000 chars."""
    return {
        "type": "text",
        "text": {"content": content[:RICH_TEXT_LIMIT]},
        "annotations": _default_annotations(),
    }


def _default_annotations(
    bold: bool = False,
    italic: bool = False,
    strikethrough: bool = False,
    code: bool = False,
) -> dict[str, Any]:
    return {
        "bold": bold,
        "italic": italic,
        "strikethrough": strikethrough,
        "underline": False,
        "code": code,
        "color": "default",
    }


def _rich_text_segment(
    content: str,
    bold: bool = False,
    italic: bool = False,
    strikethrough: bool = False,
    code: bool = False,
) -> dict[str, Any]:
    return {
        "type": "text",
        "text": {"content": content[:RICH_TEXT_LIMIT]},
        "annotations": _default_annotations(
            bold=bold, italic=italic, strikethrough=strikethrough, code=code
        ),
    }


# Inline pattern token types in order of precedence.
# Each tuple: (token_name, regex_pattern, annotation_kwargs)
_INLINE_PATTERNS: list[tuple[str, re.Pattern, dict]] = [
    ("bold",          re.compile(r"\*\*(.+?)\*\*"),   {"bold": True}),
    ("italic",        re.compile(r"\*(.+?)\*"),        {"italic": True}),
    ("strikethrough", re.compile(r"~~(.+?)~~"),        {"strikethrough": True}),
    ("code",          re.compile(r"`(.+?)`"),          {"code": True}),
]


def _parse_inline(text: str) -> list[dict[str, Any]]:
    """Parse inline markdown formatting and return a list of rich_text segments.

    Processes bold, italic, strikethrough, and inline code. Unformatted spans
    become plain segments. Each segment is truncated at 2000 chars.
    """
    segments: list[dict[str, Any]] = []

    # Build a list of all markup matches across the text so we can process
    # them in order of appearance.
    matches: list[tuple[int, int, str, dict]] = []  # (start, end, content, annotations)
    for _name, pattern, annotations in _INLINE_PATTERNS:
        for m in pattern.finditer(text):
            matches.append((m.start(), m.end(), m.group(1), annotations))

    # Sort by start position; for overlaps keep the first one found.
    matches.sort(key=lambda x: x[0])

    # Walk through matches, emitting plain text between them.
    cursor = 0
    used_ranges: list[tuple[int, int]] = []

    # Filter out overlapping matches (keep earliest).
    filtered: list[tuple[int, int, str, dict]] = []
    for start, end, content, annotations in matches:
        if any(s < end and start < e for s, e in used_ranges):
            continue
        filtered.append((start, end, content, annotations))
        used_ranges.append((start, end))

    for start, end, content, annotations in filtered:
        # Plain text before this match
        if cursor < start:
            plain = text[cursor:start]
            if plain:
                segments.append(_rich_text_segment(plain))
        # Annotated segment
        segments.append(_rich_text_segment(content, **annotations))
        cursor = end

    # Remaining plain text
    if cursor < len(text):
        remaining = text[cursor:]
        if remaining:
            segments.append(_rich_text_segment(remaining))

    # If nothing was parsed, return a single plain segment
    if not segments:
        segments.append(_rich_text_segment(text))

    return segments
