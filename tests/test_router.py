from notion_sync.router import route_file


def test_route_session():
    result = route_file("/home/user/projects/claude-sessions/2026-03-20-fix.md")
    assert result["type"] == "session"


def test_route_memory():
    result = route_file("/home/user/.claude/projects/-home-user-projects/memory/feedback_test.md")
    assert result["type"] == "memory"


def test_route_memory_index_skipped():
    assert route_file("/home/user/.claude/projects/-home-user-projects/memory/MEMORY.md") is None


def test_route_board():
    result = route_file("/home/user/projects/BOARD.md")
    assert result["type"] == "board"


def test_route_claude_md():
    result = route_file("/home/user/.claude/CLAUDE.md")
    assert result["type"] == "claude_md"


def test_route_unknown():
    assert route_file("/home/user/projects/some-project/main.py") is None
