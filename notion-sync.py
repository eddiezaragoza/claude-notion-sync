#!/usr/bin/env python3
"""
Usage:
  python3 notion-sync.py <file_path>   # Sync a single file
  python3 notion-sync.py --bulk        # Initial bulk sync
  python3 notion-sync.py --sweep       # Startup sweep
  python3 notion-sync.py --health      # Health check
"""
import sys
import os
import logging
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from notion_client import Client
from notion_sync.config import load_config, get_notion_token, STATE_FILE, QUEUE_FILE, CONFLICTS_FILE, LOG_FILE
from notion_sync.rate_limiter import RateLimiter
from notion_sync.state import SyncState, RetryQueue
from notion_sync.router import route_file
from notion_sync.sync_push import push_session, push_memory, push_board, push_claude_md
from notion_sync.health_check import get_sync_status

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("notion_sync")


def _do_sync(file_path, config, client, limiter):
    """Execute sync for a single file. Returns result dict or None."""
    route = route_file(file_path)
    if route is None:
        return None
    sync_type = route["type"]
    if sync_type == "session":
        result = push_session(client, limiter, config["databases"]["sessions"], file_path)
        state_key = f"claude-sessions/{os.path.basename(file_path)}"
    elif sync_type == "memory":
        result = push_memory(client, limiter, config["databases"]["memory"], file_path)
        state_key = f"memory/{os.path.basename(file_path)}"
    elif sync_type == "board":
        result = push_board(client, limiter, config["databases"]["board"], file_path)
        state_key = "BOARD.md"
    elif sync_type == "claude_md":
        result = push_claude_md(client, limiter, config["pages"]["claude_md_parent"], file_path)
        state_key = "CLAUDE.md"
    else:
        return None

    if result and result.get("page_id"):
        state = SyncState(STATE_FILE)
        now = datetime.now(timezone.utc).isoformat()
        mtime = datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc).isoformat()
        state.set(state_key, result["page_id"], now, mtime)
    logger.info(f"Synced {file_path} -> {result}")
    return result


def sync_single_file(file_path, config, client, limiter):
    """Sync a single file, processing retry queue first."""
    queue = RetryQueue(QUEUE_FILE)
    for item in queue.get_pending():
        try:
            _do_sync(item["file_path"], config, client, limiter)
            queue.remove(item["file_path"])
        except Exception as e:
            logger.warning(f"Retry failed for {item['file_path']}: {e}")
    try:
        result = _do_sync(file_path, config, client, limiter)
        queue.remove(file_path)
        return result
    except Exception as e:
        logger.error(f"Sync failed for {file_path}: {e}")
        queue.add(file_path, str(e))
        return None


def run_sweep(config, client, limiter):
    """Full startup sweep: process queue, pull from Notion, start watcher."""
    from notion_sync.sync_pull import (check_for_new_memories, check_for_new_sessions,
                                        pull_page_content, log_conflict)
    state = SyncState(STATE_FILE)
    queue = RetryQueue(QUEUE_FILE)

    # 1. Process retry queue
    for item in queue.get_pending():
        try:
            _do_sync(item["file_path"], config, client, limiter)
            queue.remove(item["file_path"])
        except Exception as e:
            logger.warning(f"Retry failed: {item['file_path']}: {e}")

    # 2. Pull new/updated memories
    memory_dir = config["watched_paths"]["memory_dir"]
    new_memories = check_for_new_memories(client, limiter, config["databases"]["memory"], STATE_FILE, memory_dir)
    for item in new_memories:
        try:
            md_content = pull_page_content(client, limiter, item["page_id"])
            local_path = os.path.join(memory_dir, item["source_file"])
            if item["action"] == "conflict":
                local_content = ""
                if os.path.exists(local_path):
                    with open(local_path, "r") as f:
                        local_content = f.read()
                log_conflict(CONFLICTS_FILE, item["source_file"], local_content, md_content)
                logger.warning(f"Conflict: {item['source_file']} -- local kept")
                print(f"  CONFLICT: {item['source_file']} -- see notion-sync-conflicts.md")
            elif item["action"] in ("pull_new", "pull_update"):
                with open(local_path, "w") as f:
                    f.write(md_content)
                now = datetime.now(timezone.utc).isoformat()
                state.set(f"memory/{item['source_file']}", item["page_id"], now)
                print(f"  Pulled: {item['source_file']}")
        except Exception as e:
            logger.error(f"Pull failed for {item['source_file']}: {e}")

    # 3. Pull new sessions (never overwrite existing)
    sessions_dir = config["watched_paths"]["sessions_dir"]
    new_sessions = check_for_new_sessions(client, limiter, config["databases"]["sessions"], STATE_FILE, sessions_dir)
    for item in new_sessions:
        try:
            md_content = pull_page_content(client, limiter, item["page_id"])
            local_path = os.path.join(sessions_dir, item["filename"])
            with open(local_path, "w") as f:
                f.write(md_content)
            now = datetime.now(timezone.utc).isoformat()
            state.set(f"claude-sessions/{item['filename']}", item["page_id"], now)
            print(f"  Pulled new session: {item['filename']}")
        except Exception as e:
            logger.error(f"Pull failed for {item['filename']}: {e}")

    # 4. Start watcher if not running
    watcher_pid_file = "/tmp/notion-sync-watcher.pid"
    watcher_running = False
    if os.path.exists(watcher_pid_file):
        try:
            pid = int(open(watcher_pid_file).read().strip())
            os.kill(pid, 0)
            watcher_running = True
        except (ProcessLookupError, ValueError):
            pass
    if not watcher_running:
        watcher_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notion-sync-watcher.sh")
        if os.path.exists(watcher_script):
            import subprocess
            subprocess.Popen([watcher_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("Notion sync: watcher started")

    print(get_sync_status(STATE_FILE, QUEUE_FILE, CONFLICTS_FILE))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    arg = sys.argv[1]
    config = load_config()
    token = get_notion_token(config)
    client = Client(auth=token)
    limiter = RateLimiter()

    # Load custom project map if configured
    if config.get("project_map"):
        from notion_sync.session_parser import set_project_map
        set_project_map(config["project_map"])

    if arg == "--health":
        print(get_sync_status(STATE_FILE, QUEUE_FILE, CONFLICTS_FILE))
    elif arg == "--bulk":
        from notion_sync.bulk_sync import run_bulk_sync
        run_bulk_sync(config, client, limiter)
    elif arg == "--sweep":
        run_sweep(config, client, limiter)
    else:
        file_path = os.path.abspath(arg)
        sync_single_file(file_path, config, client, limiter)

if __name__ == "__main__":
    main()
