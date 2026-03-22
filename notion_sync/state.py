import json
import os
import fcntl
import tempfile
from datetime import datetime, timezone


def _atomic_write(path, data):
    dir_name = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.rename(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _locked_read(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class SyncState:
    def __init__(self, path):
        self.path = path
        self.entries = _locked_read(path)

    def get(self, file_key):
        return self.entries.get(file_key)

    def set(self, file_key, notion_page_id, last_synced_utc, local_mtime_utc=None):
        self.entries[file_key] = {
            "notion_page_id": notion_page_id,
            "last_synced_utc": last_synced_utc,
            "local_mtime_utc": local_mtime_utc or datetime.now(timezone.utc).isoformat()
        }
        self.save()

    def save(self):
        _atomic_write(self.path, self.entries)


class RetryQueue:
    def __init__(self, path, max_failures=5):
        self.path = path
        self.max_failures = max_failures
        raw = _locked_read(path)
        if isinstance(raw, dict):
            self._items = list(raw.values()) if raw else []
        elif isinstance(raw, list):
            self._items = raw
        else:
            self._items = []

    def add(self, file_path, error):
        for item in self._items:
            if item["file_path"] == file_path:
                item["failure_count"] += 1
                item["error"] = error
                item["last_attempt_utc"] = datetime.now(timezone.utc).isoformat()
                self.save()
                return
        self._items.append({
            "file_path": file_path,
            "error": error,
            "failure_count": 1,
            "first_attempt_utc": datetime.now(timezone.utc).isoformat(),
            "last_attempt_utc": datetime.now(timezone.utc).isoformat()
        })
        self.save()

    def remove(self, file_path):
        self._items = [i for i in self._items if i["file_path"] != file_path]
        self.save()

    def get_pending(self):
        return [i for i in self._items if i["failure_count"] < self.max_failures]

    def get_exhausted(self):
        return [i for i in self._items if i["failure_count"] >= self.max_failures]

    def save(self):
        _atomic_write(self.path, self._items)
