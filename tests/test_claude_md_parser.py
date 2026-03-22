from notion_sync.claude_md_parser import parse_claude_md


def test_parse_sections(sample_claude_md_content):
    sections = parse_claude_md(sample_claude_md_content)
    assert len(sections) == 3
    assert sections[0]["heading"] == "Salesforce Knowledge Base"
    assert sections[1]["heading"] == "Screenshots"
    assert sections[2]["heading"] == "Communication Style"


def test_section_content(sample_claude_md_content):
    sections = parse_claude_md(sample_claude_md_content)
    assert "Salesforce documentation" in sections[0]["body"]
    assert "Screenpresso" in sections[1]["body"]
