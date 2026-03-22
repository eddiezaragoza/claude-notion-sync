import os
import json
from datetime import datetime, timezone

def get_sync_status(state_path, queue_path, conflicts_path):
    # Check conflicts first
    if os.path.exists(conflicts_path):
        with open(conflicts_path, "r") as f:
            content = f.read()
        conflict_count = content.count("## Conflict:")
        if conflict_count > 0:
            return f"Notion sync: {conflict_count} conflicts detected -- review notion-sync-conflicts.md"
    # Check retry queue
    if os.path.exists(queue_path):
        try:
            with open(queue_path, "r") as f:
                queue = json.load(f)
            if isinstance(queue, list):
                pending = [i for i in queue if i.get("failure_count", 0) < 5]
                if pending:
                    return f"Notion sync: {len(pending)} files pending retry"
        except (json.JSONDecodeError, KeyError):
            pass
    # Check last sync time
    if os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                state = json.load(f)
            if state:
                latest = max((e.get("last_synced_utc", "") for e in state.values()), default="")
                if latest:
                    last_dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    minutes = int((now - last_dt).total_seconds() / 60)
                    if minutes < 60:
                        return f"Notion sync: healthy, last sync {minutes} min ago"
                    else:
                        return f"Notion sync: healthy, last sync {minutes // 60}h ago"
        except (json.JSONDecodeError, KeyError):
            pass
    return "Notion sync: no sync history found"
