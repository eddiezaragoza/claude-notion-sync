import pytest
from notion_sync.notion_to_md import blocks_to_markdown


def _text(content, bold=False, italic=False, strikethrough=False, code=False):
    return {
        "type": "text",
        "text": {"content": content},
        "annotations": {
            "bold": bold, "italic": italic, "strikethrough": strikethrough,
            "underline": False, "code": code, "color": "default"
        }
    }


def test_heading_1():
    blocks = [{"type": "heading_1", "heading_1": {"rich_text": [_text("Title")]}}]
    assert blocks_to_markdown(blocks) == "# Title\n"


def test_heading_2():
    blocks = [{"type": "heading_2", "heading_2": {"rich_text": [_text("Sub")]}}]
    assert blocks_to_markdown(blocks) == "## Sub\n"


def test_heading_3():
    blocks = [{"type": "heading_3", "heading_3": {"rich_text": [_text("Section")]}}]
    assert blocks_to_markdown(blocks) == "### Section\n"


def test_paragraph():
    blocks = [{"type": "paragraph", "paragraph": {"rich_text": [_text("Hello")]}}]
    assert blocks_to_markdown(blocks) == "Hello\n"


def test_bullet_list():
    blocks = [
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [_text("A")]}},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [_text("B")]}}
    ]
    assert blocks_to_markdown(blocks) == "- A\n- B\n"


def test_numbered_list():
    blocks = [
        {"type": "numbered_list_item", "numbered_list_item": {"rich_text": [_text("First")]}},
        {"type": "numbered_list_item", "numbered_list_item": {"rich_text": [_text("Second")]}}
    ]
    assert blocks_to_markdown(blocks) == "1. First\n1. Second\n"


def test_code_block():
    blocks = [{"type": "code", "code": {
        "rich_text": [_text("print('hi')")], "language": "python"
    }}]
    assert blocks_to_markdown(blocks) == "```python\nprint('hi')\n```\n"


def test_code_block_plain_text_language():
    blocks = [{"type": "code", "code": {
        "rich_text": [_text("some code")], "language": "plain text"
    }}]
    assert blocks_to_markdown(blocks) == "```\nsome code\n```\n"


def test_divider():
    blocks = [{"type": "divider", "divider": {}}]
    assert blocks_to_markdown(blocks) == "---\n"


def test_bold_annotation():
    blocks = [{"type": "paragraph", "paragraph": {"rich_text": [
        _text("This is "), _text("bold", bold=True), _text(" text")
    ]}}]
    assert blocks_to_markdown(blocks) == "This is **bold** text\n"


def test_italic_annotation():
    blocks = [{"type": "paragraph", "paragraph": {"rich_text": [
        _text("This is "), _text("italic", italic=True), _text(" text")
    ]}}]
    assert blocks_to_markdown(blocks) == "This is *italic* text\n"


def test_strikethrough_annotation():
    blocks = [{"type": "paragraph", "paragraph": {"rich_text": [
        _text("This is "), _text("deleted", strikethrough=True), _text(" text")
    ]}}]
    assert blocks_to_markdown(blocks) == "This is ~~deleted~~ text\n"


def test_code_annotation():
    blocks = [{"type": "paragraph", "paragraph": {"rich_text": [
        _text("Use "), _text("pip install", code=True), _text(" to install")
    ]}}]
    assert blocks_to_markdown(blocks) == "Use `pip install` to install\n"


def test_mixed_blocks():
    blocks = [
        {"type": "heading_1", "heading_1": {"rich_text": [_text("Title")]}},
        {"type": "paragraph", "paragraph": {"rich_text": [_text("Body")]}},
        {"type": "divider", "divider": {}},
    ]
    result = blocks_to_markdown(blocks)
    assert "# Title" in result
    assert "Body" in result
    assert "---" in result


def test_to_do_checked():
    blocks = [{"type": "to_do", "to_do": {
        "rich_text": [_text("Done task")], "checked": True
    }}]
    assert blocks_to_markdown(blocks) == "- [x] Done task\n"


def test_to_do_unchecked():
    blocks = [{"type": "to_do", "to_do": {
        "rich_text": [_text("Pending task")], "checked": False
    }}]
    assert blocks_to_markdown(blocks) == "- [ ] Pending task\n"


def test_quote():
    blocks = [{"type": "quote", "quote": {"rich_text": [_text("A wise saying")]}}]
    assert blocks_to_markdown(blocks) == "> A wise saying\n"


def test_callout():
    blocks = [{"type": "callout", "callout": {"rich_text": [_text("Important note")]}}]
    assert blocks_to_markdown(blocks) == "> Important note\n"


def test_empty_paragraph():
    blocks = [{"type": "paragraph", "paragraph": {"rich_text": []}}]
    assert blocks_to_markdown(blocks) == "\n"


def test_unknown_block_type_skipped():
    blocks = [
        {"type": "unsupported_type", "unsupported_type": {}},
        {"type": "paragraph", "paragraph": {"rich_text": [_text("After unknown")]}},
    ]
    result = blocks_to_markdown(blocks)
    assert "After unknown" in result


def test_multiple_annotations_bold_italic():
    block = {
        "type": "text",
        "text": {"content": "bold and italic"},
        "annotations": {
            "bold": True, "italic": True, "strikethrough": False,
            "underline": False, "code": False, "color": "default"
        }
    }
    blocks = [{"type": "paragraph", "paragraph": {"rich_text": [block]}}]
    result = blocks_to_markdown(blocks)
    # Should wrap with both bold and italic markers
    assert "bold and italic" in result
    assert "**" in result
    assert "*" in result


def test_empty_blocks_list():
    assert blocks_to_markdown([]) == ""
