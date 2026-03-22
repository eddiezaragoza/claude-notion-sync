#!/usr/bin/env python3
"""
One-time Notion workspace setup.

Usage:
  export NOTION_API_TOKEN=your-token
  python3 notion-sync-setup.py <parent-page-id>

The parent page ID is the 32-char hex from the Notion page URL.
Auto-detects Claude Code directory structure for watched paths.
"""
import sys
import os
import json
import glob
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from notion_client import Client
from notion_sync.config import DEFAULT_CONFIG_PATH


def auto_detect_paths():
    """Auto-detect Claude Code directory structure."""
    paths = {
        "sessions_dir": "",
        "memory_dir": "",
        "board_file": "",
        "claude_md_file": ""
    }

    home = os.path.expanduser("~")
    claude_home = os.path.join(home, ".claude")

    # Find CLAUDE.md
    claude_md = os.path.join(claude_home, "CLAUDE.md")
    if os.path.exists(claude_md):
        paths["claude_md_file"] = claude_md

    # Find memory dir (look for MEMORY.md under ~/.claude/projects/)
    projects_dir = os.path.join(claude_home, "projects")
    if os.path.isdir(projects_dir):
        for root, dirs, files in os.walk(projects_dir):
            if "MEMORY.md" in files and "memory" in root:
                paths["memory_dir"] = root
                break

    # Find sessions dir (look for YYYY-MM-DD-*.md files)
    session_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.md$")
    common_session_dirs = [
        os.path.join(home, "claude-sessions"),
        os.path.join(home, "projects", "claude-sessions"),
        "/mnt/c/projects/claude-sessions",
    ]
    # Also check parent of CWD
    cwd = os.getcwd()
    common_session_dirs.append(os.path.join(os.path.dirname(cwd), "claude-sessions"))
    common_session_dirs.append(os.path.join(cwd, "claude-sessions"))

    for d in common_session_dirs:
        if os.path.isdir(d):
            files = os.listdir(d)
            if any(session_pattern.match(f) for f in files):
                paths["sessions_dir"] = d
                break

    # Find BOARD.md (check CWD, parent of CWD, home)
    for d in [cwd, os.path.dirname(cwd), home]:
        board = os.path.join(d, "BOARD.md")
        if os.path.exists(board):
            paths["board_file"] = board
            break

    return paths


def confirm_paths(paths):
    """Show detected paths and let user confirm or override."""
    print("Detected paths:")
    fields = [
        ("sessions_dir", "Sessions directory"),
        ("memory_dir", "Memory directory"),
        ("board_file", "Board file (BOARD.md)"),
        ("claude_md_file", "CLAUDE.md file"),
    ]
    for key, label in fields:
        val = paths.get(key, "")
        if val:
            print(f"  {label}: {val}")
        else:
            print(f"  {label}: NOT FOUND")

    print()
    response = input("Use these paths? [Y/n] ").strip().lower()
    if response in ("n", "no"):
        for key, label in fields:
            current = paths.get(key, "")
            new_val = input(f"  {label} [{current}]: ").strip()
            if new_val:
                paths[key] = new_val
    return paths


def create_sessions_db(client, parent_page_id):
    print("Creating Sessions database...")
    db = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"text": {"content": "Sessions"}}],
        properties={
            "Title": {"title": {}},
            "Date": {"date": {}},
            "Project": {"select": {"options": []}},
            "Status": {"select": {"options": [
                {"name": "In progress"}, {"name": "Completed"}
            ]}},
            "Tags": {"multi_select": {"options": []}},
        }
    )
    db_id = db["id"]
    # Properties may not be created during create -- update to ensure they exist
    client.databases.update(
        database_id=db_id,
        properties={
            "Date": {"date": {}},
            "Project": {"select": {"options": []}},
            "Status": {"select": {"options": [
                {"name": "In progress"}, {"name": "Completed"}
            ]}},
            "Tags": {"multi_select": {"options": []}},
        }
    )
    print(f"  Created: {db_id}")
    return db_id


def create_memory_db(client, parent_page_id):
    print("Creating Memory database...")
    db = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"text": {"content": "Memory"}}],
        properties={
            "Name": {"title": {}},
            "Type": {"select": {"options": [
                {"name": "user"}, {"name": "feedback"},
                {"name": "project"}, {"name": "reference"}, {"name": "unknown"}
            ]}},
            "Description": {"rich_text": {}},
            "Source File": {"rich_text": {}},
        }
    )
    db_id = db["id"]
    client.databases.update(
        database_id=db_id,
        properties={
            "Type": {"select": {"options": [
                {"name": "user"}, {"name": "feedback"},
                {"name": "project"}, {"name": "reference"}, {"name": "unknown"}
            ]}},
            "Description": {"rich_text": {}},
            "Source File": {"rich_text": {}},
        }
    )
    print(f"  Created: {db_id}")
    return db_id


def create_board_db(client, parent_page_id):
    print("Creating Board database...")
    db = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"text": {"content": "Board"}}],
        properties={
            "Task": {"title": {}},
            "Stable ID": {"rich_text": {}},
            "Project": {"select": {"options": []}},
            "Status": {"select": {"options": [
                {"name": "In Progress"}, {"name": "Backlog"}, {"name": "Blocked"},
                {"name": "Completed"}, {"name": "Cancelled"}
            ]}},
            "Added": {"date": {}},
            "Session Link": {"rich_text": {}},
        }
    )
    db_id = db["id"]
    client.databases.update(
        database_id=db_id,
        properties={
            "Stable ID": {"rich_text": {}},
            "Project": {"select": {"options": []}},
            "Status": {"select": {"options": [
                {"name": "In Progress"}, {"name": "Backlog"}, {"name": "Blocked"},
                {"name": "Completed"}, {"name": "Cancelled"}
            ]}},
            "Added": {"date": {}},
            "Session Link": {"rich_text": {}},
        }
    )
    # Rename title property to "Task"
    for name, prop in client.databases.retrieve(db_id)["properties"].items():
        if prop["type"] == "title" and name != "Task":
            client.databases.update(
                database_id=db_id,
                properties={name: {"name": "Task", "title": {}}}
            )
            break
    print(f"  Created: {db_id}")
    return db_id


def create_claude_md_page(client, parent_page_id):
    print("Creating CLAUDE.md parent page...")
    page = client.pages.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        properties={"title": {"title": [{"text": {"content": "CLAUDE.md"}}]}},
        children=[{
            "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {
                "content": "Auto-synced sections from CLAUDE.md. Each subpage is one section."
            }}]}
        }]
    )
    print(f"  Created: {page['id']}")
    return page["id"]


def create_html_catalog_page(client, parent_page_id):
    print("Creating HTML Docs Catalog page...")
    page = client.pages.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        properties={"title": {"title": [{"text": {"content": "HTML Docs Catalog"}}]}},
        children=[{
            "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {
                "content": "Links to generated HTML documents. Add entries manually or via sync."
            }}]}
        }]
    )
    print(f"  Created: {page['id']}")
    return page["id"]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nTo find your parent page ID:")
        print("  1. Create a page in Notion (e.g., 'Claude Brain')")
        print("  2. Share it with your integration (... menu > Connections)")
        print("  3. Copy the URL -- it looks like: notion.so/Your-Page-<32-char-hex>")
        print("  4. The 32-char hex at the end is the page ID")
        sys.exit(1)

    parent_page_id = sys.argv[1].replace("-", "")
    token = os.environ.get("NOTION_API_TOKEN")
    if not token:
        print("ERROR: Set NOTION_API_TOKEN first")
        print("  export NOTION_API_TOKEN=your-integration-token")
        sys.exit(1)

    client = Client(auth=token)
    print(f"\nSetting up Notion workspace under page {parent_page_id}...\n")

    # Auto-detect paths
    paths = auto_detect_paths()
    paths = confirm_paths(paths)

    sessions_id = create_sessions_db(client, parent_page_id)
    memory_id = create_memory_db(client, parent_page_id)
    board_id = create_board_db(client, parent_page_id)
    claude_md_id = create_claude_md_page(client, parent_page_id)
    html_catalog_id = create_html_catalog_page(client, parent_page_id)

    config = {
        "notion_token_env_var": "NOTION_API_TOKEN",
        "databases": {
            "sessions": sessions_id,
            "memory": memory_id,
            "board": board_id
        },
        "pages": {
            "claude_md_parent": claude_md_id,
            "html_docs_catalog": html_catalog_id
        },
        "watched_paths": paths,
        "project_map": {}
    }

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notion-sync-config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\nConfig saved to {config_path}")
    print("\nSetup complete! Next steps:")
    print("  1. (Optional) Edit notion-sync-config.json to add project_map entries")
    print("  2. Run bulk sync:  python3 notion-sync.py --bulk")
    print("  3. Start watcher:  ./notion-sync-watcher.sh")
    print("  4. Add to Claude Code SessionStart hook for auto-start (see README)")

if __name__ == "__main__":
    main()
