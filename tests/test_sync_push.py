import pytest
from unittest.mock import MagicMock, call
from notion_sync.sync_push import push_session, push_memory, push_board, push_claude_md


@pytest.fixture
def mock_notion():
    client = MagicMock()
    # Default: empty query results, successful creates
    client.databases.query.return_value = {"results": [], "has_more": False}
    client.pages.create.return_value = {"id": "new-page-id"}
    client.pages.update.return_value = {"id": "existing-page-id"}
    client.blocks.children.list.return_value = {"results": [], "has_more": False}
    client.blocks.children.append.return_value = {}
    client.blocks.delete.return_value = {}
    return client


@pytest.fixture
def mock_limiter():
    """A limiter that passes through calls without throttling."""
    limiter = MagicMock()
    limiter.wait.return_value = None

    def passthrough(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    limiter.call_with_retry.side_effect = passthrough
    return limiter


# ---------------------------------------------------------------------------
# push_session
# ---------------------------------------------------------------------------

class TestPushSession:
    def test_creates_new_session_page(self, mock_notion, mock_limiter, tmp_path, sample_session_content):
        f = tmp_path / "2026-03-20-informativ-fix.md"
        f.write_text(sample_session_content)
        result = push_session(mock_notion, mock_limiter, "db-sess-id", str(f))
        assert result["page_id"] == "new-page-id"
        assert result["action"] == "created"
        mock_notion.pages.create.assert_called_once()

    def test_updates_existing_session_page(self, mock_notion, mock_limiter, tmp_path, sample_session_content):
        mock_notion.databases.query.return_value = {
            "results": [{"id": "existing-page-id"}], "has_more": False
        }
        mock_notion.blocks.children.list.return_value = {
            "results": [{"id": "block-1"}, {"id": "block-2"}], "has_more": False
        }
        f = tmp_path / "2026-03-20-informativ-fix.md"
        f.write_text(sample_session_content)
        result = push_session(mock_notion, mock_limiter, "db-sess-id", str(f))
        assert result["page_id"] == "existing-page-id"
        assert result["action"] == "updated"
        assert mock_notion.blocks.delete.call_count == 2

    def test_create_page_has_title_property(self, mock_notion, mock_limiter, tmp_path, sample_session_content):
        f = tmp_path / "2026-03-20-informativ-fix.md"
        f.write_text(sample_session_content)
        push_session(mock_notion, mock_limiter, "db-sess-id", str(f))
        create_kwargs = mock_notion.pages.create.call_args[1]
        assert "Title" in create_kwargs["properties"]

    def test_query_uses_title_filter(self, mock_notion, mock_limiter, tmp_path, sample_session_content):
        f = tmp_path / "2026-03-20-informativ-fix.md"
        f.write_text(sample_session_content)
        push_session(mock_notion, mock_limiter, "db-sess-id", str(f))
        query_kwargs = mock_notion.databases.query.call_args[1]
        assert query_kwargs["filter"]["property"] == "Title"

    def test_blocks_appended_on_create(self, mock_notion, mock_limiter, tmp_path, sample_session_content):
        f = tmp_path / "2026-03-20-informativ-fix.md"
        f.write_text(sample_session_content)
        push_session(mock_notion, mock_limiter, "db-sess-id", str(f))
        mock_notion.blocks.children.append.assert_called()

    def test_pagination_query(self, mock_notion, mock_limiter, tmp_path, sample_session_content):
        """If has_more is True on first query, it should follow cursor."""
        mock_notion.databases.query.side_effect = [
            {"results": [], "has_more": True, "next_cursor": "cursor-1"},
            {"results": [], "has_more": False},
        ]
        f = tmp_path / "2026-03-20-informativ-fix.md"
        f.write_text(sample_session_content)
        push_session(mock_notion, mock_limiter, "db-sess-id", str(f))
        assert mock_notion.databases.query.call_count == 2
        second_call_kwargs = mock_notion.databases.query.call_args_list[1][1]
        assert second_call_kwargs["start_cursor"] == "cursor-1"

    def test_blocks_deleted_paginated(self, mock_notion, mock_limiter, tmp_path, sample_session_content):
        """Block deletion should paginate if has_more is True."""
        mock_notion.databases.query.return_value = {
            "results": [{"id": "existing-page-id"}], "has_more": False
        }
        mock_notion.blocks.children.list.side_effect = [
            {"results": [{"id": "block-1"}], "has_more": True, "next_cursor": "cur-blk"},
            {"results": [{"id": "block-2"}], "has_more": False},
        ]
        f = tmp_path / "2026-03-20-informativ-fix.md"
        f.write_text(sample_session_content)
        result = push_session(mock_notion, mock_limiter, "db-sess-id", str(f))
        assert mock_notion.blocks.delete.call_count == 2
        assert result["action"] == "updated"


# ---------------------------------------------------------------------------
# push_memory
# ---------------------------------------------------------------------------

class TestPushMemory:
    def test_creates_new_memory_page(self, mock_notion, mock_limiter, tmp_path, sample_memory_content):
        f = tmp_path / "feedback_ghost.md"
        f.write_text(sample_memory_content)
        result = push_memory(mock_notion, mock_limiter, "db-mem-id", str(f))
        assert result["page_id"] == "new-page-id"
        assert result["action"] == "created"

    def test_updates_existing_memory_page(self, mock_notion, mock_limiter, tmp_path, sample_memory_content):
        mock_notion.databases.query.return_value = {
            "results": [{"id": "existing-mem-page"}], "has_more": False
        }
        mock_notion.blocks.children.list.return_value = {"results": [], "has_more": False}
        f = tmp_path / "feedback_ghost.md"
        f.write_text(sample_memory_content)
        result = push_memory(mock_notion, mock_limiter, "db-mem-id", str(f))
        assert result["page_id"] == "existing-mem-page"
        assert result["action"] == "updated"

    def test_create_uses_name_property(self, mock_notion, mock_limiter, tmp_path, sample_memory_content):
        f = tmp_path / "feedback_ghost.md"
        f.write_text(sample_memory_content)
        push_memory(mock_notion, mock_limiter, "db-mem-id", str(f))
        create_kwargs = mock_notion.pages.create.call_args[1]
        assert "Name" in create_kwargs["properties"]

    def test_create_has_type_and_description(self, mock_notion, mock_limiter, tmp_path, sample_memory_content):
        f = tmp_path / "feedback_ghost.md"
        f.write_text(sample_memory_content)
        push_memory(mock_notion, mock_limiter, "db-mem-id", str(f))
        create_kwargs = mock_notion.pages.create.call_args[1]
        props = create_kwargs["properties"]
        assert "Type" in props
        assert "Description" in props
        assert "Source File" in props

    def test_query_uses_source_file_filter(self, mock_notion, mock_limiter, tmp_path, sample_memory_content):
        f = tmp_path / "feedback_ghost.md"
        f.write_text(sample_memory_content)
        push_memory(mock_notion, mock_limiter, "db-mem-id", str(f))
        query_kwargs = mock_notion.databases.query.call_args[1]
        assert query_kwargs["filter"]["property"] == "Source File"


# ---------------------------------------------------------------------------
# push_board
# ---------------------------------------------------------------------------

class TestPushBoard:
    def test_syncs_board_tasks(self, mock_notion, mock_limiter, tmp_path, sample_board_content):
        f = tmp_path / "BOARD.md"
        f.write_text(sample_board_content)
        result = push_board(mock_notion, mock_limiter, "db-board-id", str(f))
        assert result["tasks_synced"] > 0
        assert "page_id" in result

    def test_page_id_is_synthetic(self, mock_notion, mock_limiter, tmp_path, sample_board_content):
        f = tmp_path / "BOARD.md"
        f.write_text(sample_board_content)
        result = push_board(mock_notion, mock_limiter, "db-board-id", str(f))
        assert result["page_id"] == "board-db-board-id"

    def test_creates_new_task_page(self, mock_notion, mock_limiter, tmp_path, sample_board_content):
        f = tmp_path / "BOARD.md"
        f.write_text(sample_board_content)
        push_board(mock_notion, mock_limiter, "db-board-id", str(f))
        # At least one pages.create call should have happened
        mock_notion.pages.create.assert_called()

    def test_updates_existing_task_page(self, mock_notion, mock_limiter, tmp_path, sample_board_content):
        """When a task's stable_id already exists, update it instead of creating."""
        mock_notion.databases.query.return_value = {
            "results": [{"id": "existing-task-page"}], "has_more": False
        }
        mock_notion.blocks.children.list.return_value = {"results": [], "has_more": False}
        f = tmp_path / "BOARD.md"
        f.write_text(sample_board_content)
        result = push_board(mock_notion, mock_limiter, "db-board-id", str(f))
        # All tasks found existing -- no new pages created
        mock_notion.pages.create.assert_not_called()
        assert result["tasks_synced"] > 0

    def test_task_page_has_stable_id_property(self, mock_notion, mock_limiter, tmp_path, sample_board_content):
        f = tmp_path / "BOARD.md"
        f.write_text(sample_board_content)
        push_board(mock_notion, mock_limiter, "db-board-id", str(f))
        create_kwargs = mock_notion.pages.create.call_args[1]
        assert "Stable ID" in create_kwargs["properties"]

    def test_task_page_has_task_title(self, mock_notion, mock_limiter, tmp_path, sample_board_content):
        f = tmp_path / "BOARD.md"
        f.write_text(sample_board_content)
        push_board(mock_notion, mock_limiter, "db-board-id", str(f))
        create_kwargs = mock_notion.pages.create.call_args[1]
        assert "Task" in create_kwargs["properties"]

    def test_query_uses_stable_id_filter(self, mock_notion, mock_limiter, tmp_path, sample_board_content):
        f = tmp_path / "BOARD.md"
        f.write_text(sample_board_content)
        push_board(mock_notion, mock_limiter, "db-board-id", str(f))
        # All queries should filter by Stable ID
        for c in mock_notion.databases.query.call_args_list:
            assert c[1]["filter"]["property"] == "Stable ID"


# ---------------------------------------------------------------------------
# push_claude_md
# ---------------------------------------------------------------------------

class TestPushClaudeMd:
    def test_returns_sections_synced(self, mock_notion, mock_limiter, tmp_path, sample_claude_md_content):
        mock_notion.blocks.children.list.return_value = {"results": [], "has_more": False}
        f = tmp_path / "CLAUDE.md"
        f.write_text(sample_claude_md_content)
        result = push_claude_md(mock_notion, mock_limiter, "parent-page-id", str(f))
        assert result["sections_synced"] > 0

    def test_page_id_is_synthetic(self, mock_notion, mock_limiter, tmp_path, sample_claude_md_content):
        mock_notion.blocks.children.list.return_value = {"results": [], "has_more": False}
        f = tmp_path / "CLAUDE.md"
        f.write_text(sample_claude_md_content)
        result = push_claude_md(mock_notion, mock_limiter, "parent-page-id", str(f))
        assert result["page_id"] == "claude-md-parent-page-id"

    def test_creates_subpage_for_new_section(self, mock_notion, mock_limiter, tmp_path, sample_claude_md_content):
        # No existing child pages
        mock_notion.blocks.children.list.return_value = {"results": [], "has_more": False}
        f = tmp_path / "CLAUDE.md"
        f.write_text(sample_claude_md_content)
        push_claude_md(mock_notion, mock_limiter, "parent-page-id", str(f))
        mock_notion.pages.create.assert_called()

    def test_updates_existing_subpage(self, mock_notion, mock_limiter, tmp_path, sample_claude_md_content):
        """If a child page with matching title already exists, update content."""
        # sample has 3 sections: Salesforce Knowledge Base, Screenshots, Communication Style
        existing_pages = [
            {
                "type": "child_page",
                "id": "existing-sub-1",
                "child_page": {"title": "Salesforce Knowledge Base"},
            },
        ]
        mock_notion.blocks.children.list.return_value = {
            "results": existing_pages, "has_more": False
        }
        mock_notion.blocks.children.append.return_value = {}
        f = tmp_path / "CLAUDE.md"
        f.write_text(sample_claude_md_content)
        result = push_claude_md(mock_notion, mock_limiter, "parent-page-id", str(f))
        # At least the non-existing sections get created
        assert result["sections_synced"] == 3

    def test_sections_synced_count_matches_parsed(self, mock_notion, mock_limiter, tmp_path, sample_claude_md_content):
        mock_notion.blocks.children.list.return_value = {"results": [], "has_more": False}
        f = tmp_path / "CLAUDE.md"
        f.write_text(sample_claude_md_content)
        result = push_claude_md(mock_notion, mock_limiter, "parent-page-id", str(f))
        # sample_claude_md_content has 3 top-level # headings
        assert result["sections_synced"] == 3
