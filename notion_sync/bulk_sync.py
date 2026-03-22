import os
import glob
import re
import logging
from datetime import datetime, timezone
from notion_sync.state import SyncState
from notion_sync.config import STATE_FILE
from notion_sync.sync_push import push_session, push_memory, push_board, push_claude_md

logger = logging.getLogger("notion_sync")

def run_bulk_sync(config, client, limiter):
    state = SyncState(STATE_FILE)
    paths = config["watched_paths"]
    files_to_sync = []

    # 1. Memory files (small, fast)
    for f in sorted(glob.glob(os.path.join(paths["memory_dir"], "*.md"))):
        if os.path.basename(f) != "MEMORY.md":
            files_to_sync.append(("memory", f))

    # 2. Board
    files_to_sync.append(("board", paths["board_file"]))

    # 3. CLAUDE.md
    files_to_sync.append(("claude_md", paths["claude_md_file"]))

    # 4. Sessions (largest, last) -- only files matching YYYY-MM-DD- pattern
    session_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}-")
    for f in sorted(glob.glob(os.path.join(paths["sessions_dir"], "*.md"))):
        if session_pattern.match(os.path.basename(f)):
            files_to_sync.append(("session", f))

    total = len(files_to_sync)
    print(f"Bulk sync: {total} files to process")
    synced = skipped = failed = 0

    for idx, (file_type, file_path) in enumerate(files_to_sync, 1):
        basename = os.path.basename(file_path)
        state_key = _state_key(file_type, basename)
        if state.get(state_key) is not None:
            skipped += 1
            print(f"[{idx}/{total}] Skipping {basename} (already synced)")
            continue
        print(f"[{idx}/{total}] Syncing {basename}...")
        try:
            result = _sync_file(file_type, file_path, config, client, limiter)
            if result and result.get("page_id"):
                now = datetime.now(timezone.utc).isoformat()
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc).isoformat()
                state.set(state_key, result["page_id"], now, mtime)
            synced += 1
        except Exception as e:
            logger.error(f"Bulk sync failed for {file_path}: {e}")
            print(f"  FAILED: {e}")
            failed += 1

    print(f"\nBulk sync complete: {synced} synced, {skipped} skipped, {failed} failed")

def _state_key(file_type, basename):
    if file_type == "session": return f"claude-sessions/{basename}"
    elif file_type == "memory": return f"memory/{basename}"
    elif file_type == "board": return "BOARD.md"
    elif file_type == "claude_md": return "CLAUDE.md"
    return basename

def _sync_file(file_type, file_path, config, client, limiter):
    if file_type == "session":
        return push_session(client, limiter, config["databases"]["sessions"], file_path)
    elif file_type == "memory":
        return push_memory(client, limiter, config["databases"]["memory"], file_path)
    elif file_type == "board":
        return push_board(client, limiter, config["databases"]["board"], file_path)
    elif file_type == "claude_md":
        return push_claude_md(client, limiter, config["pages"]["claude_md_parent"], file_path)
    return None
