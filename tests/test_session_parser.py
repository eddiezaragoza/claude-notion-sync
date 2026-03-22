from notion_sync.session_parser import parse_session_filename, set_project_map


def test_parse_standard_filename():
    set_project_map({"my-project": "My Project"})
    result = parse_session_filename("2026-03-20-my-project-fix-bug.md")
    assert result["date"] == "2026-03-20"
    assert result["project"] == "My Project"
    assert result["title"] == "2026-03-20-my-project-fix-bug"


def test_parse_general_fallback():
    set_project_map({})
    result = parse_session_filename("2026-03-20-general-research.md")
    assert result["project"] == "General"


def test_parse_unknown_project_defaults_to_general():
    set_project_map({"known": "Known Project"})
    result = parse_session_filename("2026-03-20-unknown-something.md")
    assert result["project"] == "General"


def test_parse_no_date():
    result = parse_session_filename("random-notes.md")
    assert result["date"] is None
    assert result["project"] == "General"


def test_parse_longest_prefix_wins():
    set_project_map({"app": "App", "app-server": "App Server"})
    result = parse_session_filename("2026-03-20-app-server-deploy.md")
    assert result["project"] == "App Server"
