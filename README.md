# claude-notion-sync

Two-way sync between Claude Code's knowledge files and a Notion workspace. Your session history, memory, task board, and instructions become browsable, shareable, and accessible from Claude web/mobile.

<!-- Add screenshot here: ![Claude Brain in Notion](docs/screenshot.png) -->

## Why

Claude Code builds up a rich knowledge layer over time -- session logs, memory files, task boards, behavioral instructions. But that knowledge is locked in local files:

- **Claude web/mobile** starts fresh every conversation with zero context
- **Teammates** can't browse your session history without terminal access
- **If your terminal crashes**, context is preserved locally but not accessible from other devices

claude-notion-sync bridges this gap. Your Notion workspace becomes a live mirror of everything Claude Code knows, and Claude web can read it.

## Features

- **Real-time sync** -- filesystem watcher pushes changes to Notion within 60 seconds
- **Startup sweep** -- pulls Notion changes back to local files when a new session starts
- **Directional sync rules** -- sessions push-only, memory two-way, board/CLAUDE.md push-only
- **Conflict detection** -- when both local and Notion change, keeps local and logs the conflict
- **Rate limiting** -- 2.5 req/sec with 429 exponential backoff (Notion caps at 3/sec)
- **Block chunking** -- handles files larger than Notion's 100-block-per-request limit
- **Retry queue** -- failed syncs are retried automatically on the next run
- **Health check** -- one-line status at session start
- **Bulk sync** -- initial load of all files with progress output and resume support
- **Auto-detection** -- setup script finds your Claude Code directories automatically

## Quick Start

### 1. Create a Notion Integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Create a new internal integration
3. Copy the integration token

### 2. Create a Parent Page

1. Create a page in Notion (e.g., "Claude Brain")
2. Share it with your integration (... menu > Connections > add your integration)
3. Copy the page ID from the URL (the 32-char hex at the end)

### 3. Clone and Install

```bash
git clone https://github.com/eddiezaragoza/claude-notion-sync.git
cd claude-notion-sync
pip install -r requirements.txt
sudo apt-get install -y inotify-tools  # Linux only
```

### 4. Run Setup

```bash
export NOTION_API_TOKEN=your-token-here
python3 notion-sync-setup.py <parent-page-id>
```

The setup script will:
- Auto-detect your Claude Code directories
- Create 3 Notion databases (Sessions, Memory, Board)
- Create 2 Notion pages (CLAUDE.md, HTML Docs Catalog)
- Save all IDs to `notion-sync-config.json`

### 5. Initial Sync

```bash
python3 notion-sync.py --bulk
```

This pushes all existing files to Notion. Takes ~10-20 minutes depending on file count.

### 6. Start the Watcher

```bash
./notion-sync-watcher.sh
```

From now on, every file write syncs to Notion automatically.

### 7. Auto-Start on Session Start (Recommended)

Add this to your Claude Code `~/.claude/settings.json` under `hooks.SessionStart`:

```json
{
  "hooks": [
    {
      "type": "command",
      "command": "cd /path/to/claude-notion-sync && python3 notion-sync.py --sweep 2>/dev/null || true",
      "timeout": 30000,
      "async": true,
      "statusMessage": "Syncing with Notion..."
    }
  ]
}
```

This ensures the watcher is running and pulls any Notion changes at the start of every session.

### 8. Connect Claude Web (The Bridge)

This is where it all comes together. Claude web can read AND write your Notion workspace, giving it the same context as Claude Code.

1. Go to [claude.ai](https://claude.ai)
2. Connect Notion in Settings > Integrations (if not already connected)
3. Create a new **Project** (e.g., "My Second Brain")
4. Add a description like: `My portable brain -- connected to Notion. Has full context on my work, session history, preferences, and active tasks from Claude Code.`
5. Paste the following into the project **Instructions**:

```
You have access to my Notion workspace via the Notion connector. USE IT.

## Before Answering Questions About My Work

Always search Notion first for context. I have three databases:

- **Sessions** -- search for past work, case numbers, projects, technical discoveries
- **Memory** -- my preferences, patterns, workflows
- **Board** -- current tasks and their status across all projects

If I ask "what did we do about X" or "how did we handle Y", the answer is almost certainly in Sessions.

## Writing to Notion

When I ask you to remember something, save a finding, or log a decision, write it to the correct Notion database:

### To save a new memory:
Create a page in the **Memory** database with these properties:
- **Name** (title): descriptive name
- **Type** (select): user, feedback, project, or reference
- **Description** (rich text): one-line summary
- **Source File** (rich text): use format `type_short-name.md` (e.g., `feedback_prefer-polling.md`)

Page body: the memory content. For feedback type, structure as: rule, **Why:** reason, **How to apply:** guidance.

### To save a new session note:
Create a page in the **Sessions** database with:
- **Title**: `YYYY-MM-DD-project-short-topic`
- **Date**: today's date
- **Project** (select): the relevant project name

Page body: Summary, What We Discussed, Key Decisions, Open Items sections.

## Important Notes
- This Notion workspace syncs with Claude Code. Anything you write here will be pulled into Claude Code on the next session start.
- Do NOT delete or overwrite existing entries -- only create new ones or add to existing ones.
- When searching, try multiple queries if the first one does not find results.
```

Now every conversation in that project has full access to your Claude Code knowledge, and anything it writes flows back to Claude Code automatically.

## CLI Reference

```bash
# Sync a single file
python3 notion-sync.py /path/to/session-file.md

# Initial bulk sync (with progress)
python3 notion-sync.py --bulk

# Startup sweep (pull from Notion + start watcher)
python3 notion-sync.py --sweep

# Check sync health
python3 notion-sync.py --health
```

## How It Works

```
Claude Code (local)                  Notion                     Claude Web/Mobile
+-----------------+                +------------------+         +------------------+
| Session logs    |--fs-watcher--->| Sessions DB      |<------->| Read & write     |
| Memory files    |--fs-watcher--->| Memory DB        |         | via Notion MCP   |
| BOARD.md        |--fs-watcher--->| Board DB         |         | integration      |
| CLAUDE.md       |--fs-watcher--->| CLAUDE.md pages  |         +------------------+
|                 |                | HTML Docs Catalog|
|                 |<--startup-pull-| (newer entries)  |
+-----------------+                +------------------+
```

### Sync Direction Rules

| Content | Local -> Notion | Notion -> Local | Why |
|---|---|---|---|
| Sessions | Always | New entries only | Sessions are append-only. Claude Code is authoritative. |
| Memory | Always | Yes (two-way) | Both Claude Code and Claude web can create/update. |
| Board | Always | No (read-only) | Board is managed by Claude Code. |
| CLAUDE.md | Always | No (read-only) | Master config lives locally. |

### Conflict Resolution

When both local and Notion change a memory file since the last sync:
- Local version is kept (source of truth)
- Both versions are logged to `notion-sync-conflicts.md`
- Conflict is surfaced at next session start

## Configuration

After setup, `notion-sync-config.json` contains:

```json
{
  "notion_token_env_var": "NOTION_API_TOKEN",
  "databases": {
    "sessions": "database-id",
    "memory": "database-id",
    "board": "database-id"
  },
  "pages": {
    "claude_md_parent": "page-id",
    "html_docs_catalog": "page-id"
  },
  "watched_paths": {
    "sessions_dir": "/path/to/claude-sessions",
    "memory_dir": "/path/to/memory",
    "board_file": "/path/to/BOARD.md",
    "claude_md_file": "/path/to/CLAUDE.md"
  },
  "project_map": {
    "my-project": "My Project",
    "another": "Another Project"
  }
}
```

The `project_map` maps session filename prefixes to display names in Notion. For example, a session named `2026-03-20-my-project-fix-bug.md` gets tagged with project "My Project".

## Claude Web Bridge

The real payoff: connect Notion to Claude web via [Claude.ai's integrations panel](https://claude.ai), and Claude web can read your full session history, memory, and board from any device.

Ask Claude web: "Check my Notion sessions for the bug fix we did last week" -- and it knows.

## Requirements

- Python 3.8+
- `notion-client==2.2.1` (v3 removed `databases.query` -- do not upgrade)
- `inotify-tools` (Linux, for filesystem watcher)
- Notion API integration token (free)

## License

MIT -- see [LICENSE](LICENSE)
