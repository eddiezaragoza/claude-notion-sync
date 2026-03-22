import json
import pytest
from unittest.mock import MagicMock
from notion_sync.sync_pull import check_for_new_memories, check_for_new_sessions
from notion_sync.health_check import get_sync_status

@pytest.fixture
def mock_notion():
    return MagicMock()

@pytest.fixture
def mock_limiter():
    limiter = MagicMock()
    def passthrough(fn, *args, **kwargs):
        return fn(*args, **kwargs)
    limiter.call_with_retry.side_effect = passthrough
    return limiter

def test_detects_new_memory_in_notion(mock_notion, mock_limiter, tmp_path):
    mock_notion.databases.query.return_value = {
        "results": [{"id": "page-new", "last_edited_time": "2026-03-22T10:00:00.000Z",
            "properties": {
                "title": {"title": [{"text": {"content": "New Memory"}}], "type": "title"},
                "Type": {"select": {"name": "feedback"}, "type": "select"},
                "Source File": {"rich_text": [{"text": {"content": "new_memory.md"}}], "type": "rich_text"},
                "Description": {"rich_text": [{"text": {"content": "A new memory"}}], "type": "rich_text"},
            }}],
        "has_more": False
    }
    state_path = str(tmp_path / "state.json")
    memory_dir = str(tmp_path / "memory")
    (tmp_path / "memory").mkdir()
    new_items = check_for_new_memories(mock_notion, mock_limiter, "db-mem-id", state_path, memory_dir)
    assert len(new_items) == 1
    assert new_items[0]["source_file"] == "new_memory.md"
    assert new_items[0]["action"] == "pull_new"

def test_skips_already_synced_memory(mock_notion, mock_limiter, tmp_path):
    mock_notion.databases.query.return_value = {
        "results": [{"id": "page-existing", "last_edited_time": "2026-03-20T10:00:00.000Z",
            "properties": {
                "title": {"title": [{"text": {"content": "Existing"}}], "type": "title"},
                "Source File": {"rich_text": [{"text": {"content": "existing.md"}}], "type": "rich_text"},
                "Type": {"select": {"name": "feedback"}, "type": "select"},
                "Description": {"rich_text": [{"text": {"content": "desc"}}], "type": "rich_text"},
            }}],
        "has_more": False
    }
    state_path = str(tmp_path / "state.json")
    (tmp_path / "state.json").write_text(json.dumps({
        "memory/existing.md": {"notion_page_id": "page-existing",
            "last_synced_utc": "2026-03-21T10:00:00Z", "local_mtime_utc": "2026-03-20T10:00:00Z"}
    }))
    memory_dir = str(tmp_path / "memory")
    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "existing.md").write_text("content")
    new_items = check_for_new_memories(mock_notion, mock_limiter, "db-mem-id", state_path, memory_dir)
    assert len(new_items) == 0

def test_detects_conflict_when_both_changed(mock_notion, mock_limiter, tmp_path):
    mock_notion.databases.query.return_value = {
        "results": [{"id": "page-conflict", "last_edited_time": "2026-03-22T12:00:00.000Z",
            "properties": {
                "title": {"title": [{"text": {"content": "Conflicted"}}], "type": "title"},
                "Type": {"select": {"name": "feedback"}, "type": "select"},
                "Source File": {"rich_text": [{"text": {"content": "conflict.md"}}], "type": "rich_text"},
                "Description": {"rich_text": [{"text": {"content": "desc"}}], "type": "rich_text"},
            }}],
        "has_more": False
    }
    state_path = str(tmp_path / "state.json")
    (tmp_path / "state.json").write_text(json.dumps({
        "memory/conflict.md": {"notion_page_id": "page-conflict",
            "last_synced_utc": "2026-03-21T10:00:00Z", "local_mtime_utc": "2026-03-22T11:00:00Z"}
    }))
    memory_dir = str(tmp_path / "memory")
    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "conflict.md").write_text("local version")
    items = check_for_new_memories(mock_notion, mock_limiter, "db-mem-id", state_path, memory_dir)
    assert len(items) == 1
    assert items[0]["action"] == "conflict"

def test_detects_notion_only_update(mock_notion, mock_limiter, tmp_path):
    mock_notion.databases.query.return_value = {
        "results": [{"id": "page-updated", "last_edited_time": "2026-03-22T12:00:00.000Z",
            "properties": {
                "title": {"title": [{"text": {"content": "Updated"}}], "type": "title"},
                "Type": {"select": {"name": "feedback"}, "type": "select"},
                "Source File": {"rich_text": [{"text": {"content": "updated.md"}}], "type": "rich_text"},
                "Description": {"rich_text": [{"text": {"content": "desc"}}], "type": "rich_text"},
            }}],
        "has_more": False
    }
    state_path = str(tmp_path / "state.json")
    (tmp_path / "state.json").write_text(json.dumps({
        "memory/updated.md": {"notion_page_id": "page-updated",
            "last_synced_utc": "2026-03-21T10:00:00Z", "local_mtime_utc": "2026-03-20T10:00:00Z"}
    }))
    memory_dir = str(tmp_path / "memory")
    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "updated.md").write_text("old local")
    items = check_for_new_memories(mock_notion, mock_limiter, "db-mem-id", state_path, memory_dir)
    assert len(items) == 1
    assert items[0]["action"] == "pull_update"

class TestHealthCheck:
    def test_healthy_status(self, tmp_path):
        state_path = str(tmp_path / "state.json")
        (tmp_path / "state.json").write_text(json.dumps({
            "file.md": {"last_synced_utc": "2026-03-22T10:00:00Z"}
        }))
        status = get_sync_status(state_path, str(tmp_path / "q.json"), str(tmp_path / "c.md"))
        assert "healthy" in status

    def test_pending_retry_status(self, tmp_path):
        queue_path = str(tmp_path / "queue.json")
        (tmp_path / "queue.json").write_text(json.dumps([
            {"file_path": "a.md", "failure_count": 1},
            {"file_path": "b.md", "failure_count": 2}
        ]))
        status = get_sync_status(str(tmp_path / "s.json"), queue_path, str(tmp_path / "c.md"))
        assert "2 files pending" in status

    def test_conflicts_status(self, tmp_path):
        conflicts_path = str(tmp_path / "conflicts.md")
        (tmp_path / "conflicts.md").write_text("## Conflict: a.md\nsome\n## Conflict: b.md\nmore")
        status = get_sync_status(str(tmp_path / "s.json"), str(tmp_path / "q.json"), conflicts_path)
        assert "conflict" in status.lower()
