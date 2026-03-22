from notion_sync.memory_parser import parse_memory_file


def test_parse_frontmatter(sample_memory_content, tmp_path):
    f = tmp_path / "test.md"
    f.write_text(sample_memory_content)
    result = parse_memory_file(str(f))
    assert result["name"] == "Ghost Codeword"
    assert result["type"] == "feedback"
    assert "start Ghost Writer server" in result["description"]
    assert "When Eddie's prompt" in result["body"]


def test_parse_no_frontmatter(tmp_path):
    f = tmp_path / "plain.md"
    f.write_text("Just some content")
    result = parse_memory_file(str(f))
    assert result["name"] == "plain"
    assert result["type"] == "unknown"
    assert result["body"] == "Just some content"
