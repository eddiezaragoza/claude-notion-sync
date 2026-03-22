import json
import pytest
from notion_sync.state import SyncState, RetryQueue


class TestSyncState:
    def test_load_empty_state(self, tmp_path):
        state = SyncState(str(tmp_path / "state.json"))
        assert state.entries == {}

    def test_set_and_get_entry(self, tmp_path):
        state = SyncState(str(tmp_path / "state.json"))
        state.set("sessions/file.md", "page-123", "2026-03-20T18:00:00Z")
        entry = state.get("sessions/file.md")
        assert entry["notion_page_id"] == "page-123"
        assert entry["last_synced_utc"] == "2026-03-20T18:00:00Z"

    def test_save_and_reload(self, tmp_path):
        path = str(tmp_path / "state.json")
        state = SyncState(path)
        state.set("file.md", "page-456", "2026-03-20T19:00:00Z")
        state.save()
        state2 = SyncState(path)
        entry = state2.get("file.md")
        assert entry["notion_page_id"] == "page-456"

    def test_get_nonexistent_returns_none(self, tmp_path):
        state = SyncState(str(tmp_path / "state.json"))
        assert state.get("nonexistent.md") is None


class TestRetryQueue:
    def test_add_to_queue(self, tmp_path):
        queue = RetryQueue(str(tmp_path / "queue.json"))
        queue.add("/path/to/file.md", "Connection timeout")
        items = queue.get_pending()
        assert len(items) == 1
        assert items[0]["file_path"] == "/path/to/file.md"
        assert items[0]["error"] == "Connection timeout"
        assert items[0]["failure_count"] == 1

    def test_increment_failure_count(self, tmp_path):
        queue = RetryQueue(str(tmp_path / "queue.json"))
        queue.add("/path/file.md", "Error 1")
        queue.add("/path/file.md", "Error 2")
        items = queue.get_pending()
        assert len(items) == 1
        assert items[0]["failure_count"] == 2

    def test_remove_from_queue(self, tmp_path):
        queue = RetryQueue(str(tmp_path / "queue.json"))
        queue.add("/path/file.md", "Error")
        queue.remove("/path/file.md")
        assert queue.get_pending() == []

    def test_max_failures_excluded_from_pending(self, tmp_path):
        queue = RetryQueue(str(tmp_path / "queue.json"), max_failures=3)
        for i in range(3):
            queue.add("/path/file.md", f"Error {i}")
        assert queue.get_pending() == []
        assert len(queue.get_exhausted()) == 1

    def test_save_and_reload(self, tmp_path):
        path = str(tmp_path / "queue.json")
        queue = RetryQueue(path)
        queue.add("/path/file.md", "Error")
        queue.save()
        queue2 = RetryQueue(path)
        assert len(queue2.get_pending()) == 1
