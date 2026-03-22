import pytest
from notion_sync.md_to_notion import markdown_to_blocks, chunk_blocks


class TestMarkdownToBlocks:
    def test_heading_1(self):
        blocks = markdown_to_blocks("# Title")
        assert len(blocks) == 1
        assert blocks[0]["type"] == "heading_1"
        assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Title"

    def test_heading_2(self):
        blocks = markdown_to_blocks("## Subtitle")
        assert blocks[0]["type"] == "heading_2"

    def test_heading_3(self):
        blocks = markdown_to_blocks("### Section")
        assert blocks[0]["type"] == "heading_3"

    def test_paragraph(self):
        blocks = markdown_to_blocks("Hello world")
        assert blocks[0]["type"] == "paragraph"
        assert blocks[0]["paragraph"]["rich_text"][0]["text"]["content"] == "Hello world"

    def test_bullet_list(self):
        blocks = markdown_to_blocks("- Item one\n- Item two")
        assert len(blocks) == 2
        assert blocks[0]["type"] == "bulleted_list_item"

    def test_numbered_list(self):
        blocks = markdown_to_blocks("1. First\n2. Second")
        assert len(blocks) == 2
        assert blocks[0]["type"] == "numbered_list_item"

    def test_code_block(self):
        md = "```python\nprint('hello')\n```"
        blocks = markdown_to_blocks(md)
        assert blocks[0]["type"] == "code"
        assert blocks[0]["code"]["language"] == "python"
        assert "print('hello')" in blocks[0]["code"]["rich_text"][0]["text"]["content"]

    def test_code_block_no_language(self):
        md = "```\nsome code\n```"
        blocks = markdown_to_blocks(md)
        assert blocks[0]["code"]["language"] == "plain text"

    def test_horizontal_rule(self):
        blocks = markdown_to_blocks("---")
        assert blocks[0]["type"] == "divider"

    def test_bold_text(self):
        blocks = markdown_to_blocks("This is **bold** text")
        rich_text = blocks[0]["paragraph"]["rich_text"]
        bold_segment = [r for r in rich_text if r.get("annotations", {}).get("bold")]
        assert len(bold_segment) == 1
        assert bold_segment[0]["text"]["content"] == "bold"

    def test_empty_lines_skipped(self):
        blocks = markdown_to_blocks("Line 1\n\n\nLine 2")
        assert len(blocks) == 2

    def test_table_rendered_as_code(self):
        md = "| Col1 | Col2 |\n|---|---|\n| A | B |"
        blocks = markdown_to_blocks(md)
        assert blocks[0]["type"] == "code"

    def test_strikethrough(self):
        blocks = markdown_to_blocks("This is ~~deleted~~ text")
        rich_text = blocks[0]["paragraph"]["rich_text"]
        struck = [r for r in rich_text if r.get("annotations", {}).get("strikethrough")]
        assert len(struck) == 1

    def test_inline_code(self):
        blocks = markdown_to_blocks("Use `pip install` to install")
        rich_text = blocks[0]["paragraph"]["rich_text"]
        code_segments = [r for r in rich_text if r.get("annotations", {}).get("code")]
        assert len(code_segments) == 1
        assert code_segments[0]["text"]["content"] == "pip install"

    def test_italic_text(self):
        blocks = markdown_to_blocks("This is *italic* text")
        rich_text = blocks[0]["paragraph"]["rich_text"]
        italic_segment = [r for r in rich_text if r.get("annotations", {}).get("italic")]
        assert len(italic_segment) == 1
        assert italic_segment[0]["text"]["content"] == "italic"

    def test_rich_text_truncated_at_2000(self):
        long_text = "x" * 2500
        blocks = markdown_to_blocks(long_text)
        content = blocks[0]["paragraph"]["rich_text"][0]["text"]["content"]
        assert len(content) <= 2000

    def test_heading_strips_leading_trailing_spaces(self):
        blocks = markdown_to_blocks("#  Spaced Title  ")
        assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Spaced Title"

    def test_bullet_list_content(self):
        blocks = markdown_to_blocks("- Hello there")
        assert blocks[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "Hello there"

    def test_numbered_list_content(self):
        blocks = markdown_to_blocks("1. First item")
        assert blocks[0]["numbered_list_item"]["rich_text"][0]["text"]["content"] == "First item"

    def test_mixed_content(self):
        md = "# Title\n\nSome paragraph\n\n- bullet one\n- bullet two\n\n---"
        blocks = markdown_to_blocks(md)
        types = [b["type"] for b in blocks]
        assert types == ["heading_1", "paragraph", "bulleted_list_item", "bulleted_list_item", "divider"]

    def test_code_block_multiline(self):
        md = "```javascript\nconst x = 1;\nconst y = 2;\n```"
        blocks = markdown_to_blocks(md)
        assert blocks[0]["type"] == "code"
        assert blocks[0]["code"]["language"] == "javascript"
        content = blocks[0]["code"]["rich_text"][0]["text"]["content"]
        assert "const x = 1;" in content
        assert "const y = 2;" in content


class TestChunkBlocks:
    def test_chunk_small_list(self):
        blocks = [{"type": "paragraph"}] * 50
        chunks = chunk_blocks(blocks, max_size=100)
        assert len(chunks) == 1
        assert len(chunks[0]) == 50

    def test_chunk_large_list(self):
        blocks = [{"type": "paragraph"}] * 250
        chunks = chunk_blocks(blocks, max_size=100)
        assert len(chunks) == 3
        assert len(chunks[0]) == 100
        assert len(chunks[2]) == 50

    def test_chunk_exact_boundary(self):
        blocks = [{"type": "paragraph"}] * 200
        chunks = chunk_blocks(blocks, max_size=100)
        assert len(chunks) == 2

    def test_chunk_empty_list(self):
        chunks = chunk_blocks([], max_size=100)
        assert chunks == []

    def test_chunk_default_max_size(self):
        blocks = [{"type": "paragraph"}] * 150
        chunks = chunk_blocks(blocks)
        assert len(chunks) == 2
        assert len(chunks[0]) == 100
        assert len(chunks[1]) == 50

    def test_chunk_preserves_order(self):
        blocks = [{"type": "paragraph", "n": i} for i in range(5)]
        chunks = chunk_blocks(blocks, max_size=3)
        flat = [b for chunk in chunks for b in chunk]
        assert [b["n"] for b in flat] == list(range(5))
