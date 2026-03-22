from notion_sync.board_parser import parse_board, compute_stable_id


def test_compute_stable_id():
    sid = compute_stable_id("Calabrio", "CPQ-to-RCA Product Migration")
    assert len(sid) == 12
    assert sid == compute_stable_id("Calabrio", "CPQ-to-RCA Product Migration")
    assert sid != compute_stable_id("Informativ", "CPQ-to-RCA Product Migration")


def test_parse_board_extracts_tasks(sample_board_content, tmp_path):
    f = tmp_path / "BOARD.md"
    f.write_text(sample_board_content)
    tasks = parse_board(str(f))
    in_progress = [t for t in tasks if t["status"] == "In Progress"]
    backlog = [t for t in tasks if t["status"] == "Backlog"]
    completed = [t for t in tasks if t["status"] == "Completed"]
    assert len(in_progress) == 1
    assert in_progress[0]["project"] == "Calabrio"
    assert "CPQ-to-RCA" in in_progress[0]["task"]
    assert len(backlog) == 2
    assert len(completed) == 2


def test_parse_board_completed_has_session_link(sample_board_content, tmp_path):
    f = tmp_path / "BOARD.md"
    f.write_text(sample_board_content)
    tasks = parse_board(str(f))
    completed = [t for t in tasks if t["status"] == "Completed"]
    linked = [t for t in completed if t.get("session_link")]
    assert len(linked) >= 1


def test_parse_board_stable_ids(sample_board_content, tmp_path):
    f = tmp_path / "BOARD.md"
    f.write_text(sample_board_content)
    tasks = parse_board(str(f))
    ids = [t["stable_id"] for t in tasks]
    assert len(ids) == len(set(ids))
