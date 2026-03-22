import pytest
import os
import tempfile
import json


@pytest.fixture
def sample_session_content():
    return """# Session: Fix SmartPencil stale quantity
**Date:** 2026-03-20
**Project/Directory:** /home/user/projects/my-project

## Current State / Resume Point
- **Currently doing:** Case closed.
- **Blocked on:** Nothing

## What We Did
- Queried Case 00002868 from SCSProd
- Root cause: QLG Roll-Ups flow never clears SmartPencil qty

## Key Decisions
- Used Filter + Count + Decision + Clear pattern
"""


@pytest.fixture
def sample_memory_content():
    return """---
name: Ghost Codeword
description: When Eddie says "ghost", start Ghost Writer server
type: feedback
---

When Eddie's prompt is just `ghost`, immediately:

1. Start the Ghost Writer server
2. Start the Cloudflare tunnel
3. Tell Eddie to run audio capture

**Why:** Eddie needs a one-word launch sequence.

**How to apply:** Trigger on "ghost" as a standalone prompt.
"""


@pytest.fixture
def sample_board_content():
    return """# Project Board
*Last updated: 2026-03-22*


## Calabrio

### In Progress
1. CPQ-to-RCA Product Migration *(2026-02-24)*

### Backlog
2. Set up Consumption Schedules *(2026-02-25)*

---

### Completed
- ~~Test Tiger Team cross-sell email flow~~ *(completed 2026-02-26)* -> `2026-02-25-calabrio-cross-sell.md`

### Cancelled

---

## Informativ

### In Progress

### Backlog
3. Deploy consolidated CPQ Revenue flow to Prod *(2026-02-25)*

---

### Completed
- ~~Fix SmartPencil stale qty~~ *(completed 2026-03-20)* -> `2026-03-20-informativ-smartpencil-conga-fix.md`

### Cancelled
"""


@pytest.fixture
def sample_claude_md_content():
    return """# Salesforce Knowledge Base

When working on Salesforce tasks, always read from Salesforce documentation.

# Screenshots

Eddie's screenshots come from Screenpresso.

# Communication Style

Eddie appreciates the help and always means "please" and "thank you".
"""


@pytest.fixture
def tmp_config(tmp_path):
    config = {
        "notion_token_env_var": "NOTION_API_TOKEN",
        "databases": {
            "sessions": "db-sessions-id",
            "memory": "db-memory-id",
            "board": "db-board-id"
        },
        "pages": {
            "claude_md_parent": "page-claude-md-id",
            "html_docs_catalog": "page-html-catalog-id"
        },
        "watched_paths": {
            "sessions_dir": str(tmp_path / "sessions"),
            "memory_dir": str(tmp_path / "memory"),
            "board_file": str(tmp_path / "BOARD.md"),
            "claude_md_file": str(tmp_path / "CLAUDE.md")
        }
    }
    config_path = tmp_path / "notion-sync-config.json"
    config_path.write_text(json.dumps(config))
    return str(config_path)
