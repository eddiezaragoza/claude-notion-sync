import os
import json
import logging
from datetime import datetime, timezone
from notion_sync.state import SyncState
from notion_sync.notion_to_md import blocks_to_markdown

logger = logging.getLogger("notion_sync")


def check_for_new_memories(client, limiter, database_id, state_path, memory_dir):
    """Check Notion Memory DB for entries newer than local state.
    Returns list of dicts with keys: page_id, source_file, notion_edited, action
    Actions: 'pull_new', 'pull_update', 'conflict'
    """
    state = SyncState(state_path)
    new_items = []
    # Query all memory entries with pagination
    all_results = []
    has_more = True
    start_cursor = None
    while has_more:
        kwargs = {"database_id": database_id}
        if start_cursor:
            kwargs["start_cursor"] = start_cursor
        response = limiter.call_with_retry(client.databases.query, **kwargs)
        all_results.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    for page in all_results:
        props = page["properties"]
        source_file = ""
        if props.get("Source File", {}).get("rich_text"):
            source_file = props["Source File"]["rich_text"][0]["text"]["content"]
        if not source_file:
            continue

        state_key = f"memory/{source_file}"
        local_path = os.path.join(memory_dir, source_file)
        entry = state.get(state_key)
        notion_edited = page.get("last_edited_time", "")

        # New: exists in Notion but not locally and not in state
        if not os.path.exists(local_path) and entry is None:
            new_items.append({"page_id": page["id"], "source_file": source_file,
                            "notion_edited": notion_edited, "action": "pull_new"})
            continue

        # Updated: Notion is newer than last sync
        if entry and notion_edited > entry.get("last_synced_utc", ""):
            local_mtime = entry.get("local_mtime_utc", "")
            if local_mtime and local_mtime > entry.get("last_synced_utc", ""):
                new_items.append({"page_id": page["id"], "source_file": source_file,
                                "notion_edited": notion_edited, "action": "conflict"})
            else:
                new_items.append({"page_id": page["id"], "source_file": source_file,
                                "notion_edited": notion_edited, "action": "pull_update"})
    return new_items


def check_for_new_sessions(client, limiter, database_id, state_path, sessions_dir):
    """Check for sessions that exist in Notion but not locally (created by Claude web)."""
    state = SyncState(state_path)
    new_items = []
    all_results = []
    has_more = True
    start_cursor = None
    while has_more:
        kwargs = {"database_id": database_id}
        if start_cursor:
            kwargs["start_cursor"] = start_cursor
        response = limiter.call_with_retry(client.databases.query, **kwargs)
        all_results.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    for page in all_results:
        props = page["properties"]
        # Title property uses Notion's internal "title" key in response
        title_prop = None
        for prop_name, prop_val in props.items():
            if prop_val.get("type") == "title":
                title_prop = prop_val
                break
        if not title_prop or not title_prop.get("title"):
            continue
        title = title_prop["title"][0]["text"]["content"]
        filename = f"{title}.md"
        local_path = os.path.join(sessions_dir, filename)
        state_key = f"claude-sessions/{filename}"
        if not os.path.exists(local_path) and state.get(state_key) is None:
            new_items.append({"page_id": page["id"], "filename": filename, "action": "pull_new"})
    return new_items


def pull_page_content(client, limiter, page_id):
    """Fetch ALL blocks from a Notion page (with pagination) and convert to markdown."""
    all_blocks = []
    has_more = True
    start_cursor = None
    while has_more:
        kwargs = {"block_id": page_id}
        if start_cursor:
            kwargs["start_cursor"] = start_cursor
        response = limiter.call_with_retry(client.blocks.children.list, **kwargs)
        all_blocks.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")
    return blocks_to_markdown(all_blocks)


def log_conflict(conflicts_path, source_file, local_content, notion_content):
    """Append a conflict entry with FULL content (no truncation)."""
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = f"\n## Conflict: {source_file} ({timestamp})\n\n"
    entry += "### Local version:\n```\n" + local_content + "\n```\n\n"
    entry += "### Notion version:\n```\n" + notion_content + "\n```\n\n"
    with open(conflicts_path, "a") as f:
        f.write(entry)
