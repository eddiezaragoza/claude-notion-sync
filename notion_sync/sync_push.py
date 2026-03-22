"""
sync_push.py -- Core sync logic: read a local file, convert it, push to Notion.

All Notion API calls are made through limiter.call_with_retry() to honour
rate-limit backoff.  Never call the SDK directly.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from notion_sync.md_to_notion import markdown_to_blocks, chunk_blocks
from notion_sync.session_parser import parse_session_filename
from notion_sync.memory_parser import parse_memory_file
from notion_sync.board_parser import parse_board
from notion_sync.claude_md_parser import parse_claude_md

logger = logging.getLogger("notion_sync")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _query_all(client, limiter, database_id, filter_obj=None):
    """Query a Notion database with pagination, returns all matching results."""
    all_results = []
    has_more = True
    start_cursor = None
    while has_more:
        kwargs = {"database_id": database_id}
        if filter_obj:
            kwargs["filter"] = filter_obj
        if start_cursor:
            kwargs["start_cursor"] = start_cursor
        response = limiter.call_with_retry(client.databases.query, **kwargs)
        all_results.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")
    return all_results


def _delete_page_blocks(client, limiter, page_id):
    """Delete all block children of a page, with pagination."""
    has_more = True
    start_cursor = None
    while has_more:
        kwargs = {"block_id": page_id}
        if start_cursor:
            kwargs["start_cursor"] = start_cursor
        blocks = limiter.call_with_retry(client.blocks.children.list, **kwargs)
        for block in blocks.get("results", []):
            limiter.call_with_retry(client.blocks.delete, block_id=block["id"])
        has_more = blocks.get("has_more", False)
        start_cursor = blocks.get("next_cursor")


def _append_blocks(client, limiter, page_id, blocks):
    """Append blocks to a page in chunks of 100."""
    for chunk in chunk_blocks(blocks):
        limiter.call_with_retry(
            client.blocks.children.append,
            block_id=page_id,
            children=chunk,
        )


def _title_property(text: str) -> dict[str, Any]:
    """Build a Notion title rich-text property value."""
    return {"title": [{"type": "text", "text": {"content": text}}]}


def _rich_text_property(text: str) -> dict[str, Any]:
    """Build a Notion rich-text property value."""
    return {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}


def _select_property(value: str) -> dict[str, Any]:
    return {"select": {"name": value}}


# ---------------------------------------------------------------------------
# push_session
# ---------------------------------------------------------------------------

def push_session(client, limiter, database_id: str, file_path: str) -> dict[str, Any]:
    """Upsert a session markdown file into the Sessions Notion database.

    Title property in Notion is "Title" (capital T).
    """
    basename = os.path.basename(file_path)
    parsed = parse_session_filename(basename)
    title = parsed["title"]

    with open(file_path, "r", encoding="utf-8") as fh:
        content = fh.read()

    blocks = markdown_to_blocks(content)

    # Check if page already exists (filter by Title)
    filter_obj = {
        "property": "Title",
        "title": {"equals": title},
    }
    existing = _query_all(client, limiter, database_id, filter_obj=filter_obj)

    if existing:
        page_id = existing[0]["id"]
        _delete_page_blocks(client, limiter, page_id)
        _append_blocks(client, limiter, page_id, blocks)
        return {"page_id": page_id, "action": "updated"}
    else:
        properties: dict[str, Any] = {
            "Title": _title_property(title),
        }
        if parsed.get("date"):
            properties["Date"] = {"date": {"start": parsed["date"]}}
        if parsed.get("project"):
            properties["Project"] = _select_property(parsed["project"])

        new_page = limiter.call_with_retry(
            client.pages.create,
            parent={"type": "database_id", "database_id": database_id},
            properties=properties,
        )
        page_id = new_page["id"]
        _append_blocks(client, limiter, page_id, blocks)
        return {"page_id": page_id, "action": "created"}


# ---------------------------------------------------------------------------
# push_memory
# ---------------------------------------------------------------------------

def push_memory(client, limiter, database_id: str, file_path: str) -> dict[str, Any]:
    """Upsert a memory markdown file into the Memory Notion database.

    Title property in Notion is "Name".
    Lookup key is "Source File" property.
    """
    parsed = parse_memory_file(file_path)

    blocks = markdown_to_blocks(parsed["body"])

    # Check by Source File (stable key -- filename doesn't change)
    filter_obj = {
        "property": "Source File",
        "rich_text": {"equals": parsed["source_file"]},
    }
    existing = _query_all(client, limiter, database_id, filter_obj=filter_obj)

    if existing:
        page_id = existing[0]["id"]
        _delete_page_blocks(client, limiter, page_id)
        # Update properties too
        limiter.call_with_retry(
            client.pages.update,
            page_id=page_id,
            properties={
                "Name": _title_property(parsed["name"]),
                "Type": _select_property(parsed["type"]) if parsed["type"] else _rich_text_property(""),
                "Description": _rich_text_property(parsed["description"]),
                "Source File": _rich_text_property(parsed["source_file"]),
            },
        )
        _append_blocks(client, limiter, page_id, blocks)
        return {"page_id": page_id, "action": "updated"}
    else:
        new_page = limiter.call_with_retry(
            client.pages.create,
            parent={"type": "database_id", "database_id": database_id},
            properties={
                "Name": _title_property(parsed["name"]),
                "Type": _select_property(parsed["type"]) if parsed["type"] else _rich_text_property(""),
                "Description": _rich_text_property(parsed["description"]),
                "Source File": _rich_text_property(parsed["source_file"]),
            },
        )
        page_id = new_page["id"]
        _append_blocks(client, limiter, page_id, blocks)
        return {"page_id": page_id, "action": "created"}


# ---------------------------------------------------------------------------
# push_board
# ---------------------------------------------------------------------------

def push_board(client, limiter, database_id: str, file_path: str) -> dict[str, Any]:
    """Upsert all board tasks into the Board Notion database.

    Each task is identified by its "Stable ID" property (12-char SHA-256 prefix).
    Returns a synthetic page_id for state tracking.
    """
    tasks = parse_board(file_path)
    synced = 0

    for task in tasks:
        stable_id = task["stable_id"]

        filter_obj = {
            "property": "Stable ID",
            "rich_text": {"equals": stable_id},
        }
        existing = _query_all(client, limiter, database_id, filter_obj=filter_obj)

        properties: dict[str, Any] = {
            "Task": _title_property(task["task"]),
            "Stable ID": _rich_text_property(stable_id),
            "Project": _select_property(task["project"]),
            "Status": _select_property(task["status"]),
            "Added": {"date": {"start": task["added"]}} if task.get("added") else None,
        }
        # Remove None values
        properties = {k: v for k, v in properties.items() if v is not None}

        if task.get("session_link"):
            properties["Session Link"] = _rich_text_property(task["session_link"])

        if existing:
            page_id = existing[0]["id"]
            _delete_page_blocks(client, limiter, page_id)
            limiter.call_with_retry(
                client.pages.update,
                page_id=page_id,
                properties=properties,
            )
        else:
            limiter.call_with_retry(
                client.pages.create,
                parent={"type": "database_id", "database_id": database_id},
                properties=properties,
            )

        synced += 1

    return {
        "tasks_synced": synced,
        "page_id": f"board-{database_id}",
    }


# ---------------------------------------------------------------------------
# push_claude_md
# ---------------------------------------------------------------------------

def push_claude_md(client, limiter, parent_page_id: str, file_path: str) -> dict[str, Any]:
    """Upsert CLAUDE.md sections as child subpages under parent_page_id.

    Each top-level # heading becomes one child page.  Existing pages are
    matched by title and updated in place; new sections get new pages.
    Returns a synthetic page_id for state tracking.
    """
    with open(file_path, "r", encoding="utf-8") as fh:
        content = fh.read()

    sections = parse_claude_md(content)

    # List existing child pages of the parent
    existing_pages: dict[str, str] = {}  # title -> page_id
    has_more = True
    start_cursor = None
    while has_more:
        kwargs: dict[str, Any] = {"block_id": parent_page_id}
        if start_cursor:
            kwargs["start_cursor"] = start_cursor
        response = limiter.call_with_retry(client.blocks.children.list, **kwargs)
        for block in response.get("results", []):
            if block.get("type") == "child_page":
                title = block["child_page"].get("title", "")
                existing_pages[title] = block["id"]
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    synced = 0
    for section in sections:
        heading = section["heading"]
        body = section["body"]
        blocks = markdown_to_blocks(body) if body else []

        if heading in existing_pages:
            page_id = existing_pages[heading]
            _delete_page_blocks(client, limiter, page_id)
            if blocks:
                _append_blocks(client, limiter, page_id, blocks)
        else:
            new_page = limiter.call_with_retry(
                client.pages.create,
                parent={"type": "page_id", "page_id": parent_page_id},
                properties={
                    "title": _title_property(heading),
                },
            )
            page_id = new_page["id"]
            if blocks:
                _append_blocks(client, limiter, page_id, blocks)

        synced += 1

    return {
        "sections_synced": synced,
        "page_id": f"claude-md-{parent_page_id}",
    }
