#!/usr/bin/env bash
# notion-sync-watcher.sh -- Filesystem watcher for Notion sync

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYNC_SCRIPT="$SCRIPT_DIR/notion-sync.py"
CONFIG_FILE="$SCRIPT_DIR/notion-sync-config.json"
PID_FILE="/tmp/notion-sync-watcher.pid"
DEBOUNCE_DIR="/tmp/notion-sync-debounce"

DEBOUNCE_SECONDS=60

# Read paths from config
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    echo "Run notion-sync-setup.py first."
    exit 1
fi

SESSIONS_DIR=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['watched_paths']['sessions_dir'])")
MEMORY_DIR=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['watched_paths']['memory_dir'])")
BOARD_FILE=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['watched_paths']['board_file'])")
CLAUDE_MD=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['watched_paths']['claude_md_file'])")

# Check if already running
if [ -f "$PID_FILE" ]; then
    existing_pid=$(cat "$PID_FILE")
    if kill -0 "$existing_pid" 2>/dev/null; then
        echo "Watcher already running (PID $existing_pid)"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

if ! command -v inotifywait &>/dev/null; then
    echo "ERROR: inotifywait not found. Install: sudo apt-get install inotify-tools"
    exit 1
fi

mkdir -p "$DEBOUNCE_DIR"
echo $$ > "$PID_FILE"
trap "rm -f $PID_FILE; exit" INT TERM EXIT

echo "Notion sync watcher started (PID $$)"

schedule_sync() {
    local filepath="$1"
    local hash=$(echo -n "$filepath" | md5sum | cut -d' ' -f1)
    local marker="$DEBOUNCE_DIR/$hash"
    echo "$filepath" > "$marker"
    (
        sleep "$DEBOUNCE_SECONDS"
        if mv "$marker" "$marker.processing" 2>/dev/null; then
            stored_path=$(cat "$marker.processing")
            rm -f "$marker.processing"
            python3 "$SYNC_SCRIPT" "$stored_path" &
        fi
    ) &
}

# Watch directories recursively (sessions and memory)
inotifywait -m -r \
    --event close_write --event moved_to \
    --include '\.md$' \
    "$SESSIONS_DIR" "$MEMORY_DIR" \
    2>/dev/null | while read -r dir event filename; do
    filepath="${dir}${filename}"
    case "$filepath" in
        "$SESSIONS_DIR"/*.md) schedule_sync "$filepath" ;;
        "$MEMORY_DIR"/*.md)
            [ "$filename" != "MEMORY.md" ] && schedule_sync "$filepath" ;;
    esac
done &

# Watch parent dirs of individual files (no recursion), filter by name
inotifywait -m \
    --event close_write --event moved_to \
    "$(dirname "$BOARD_FILE")" "$(dirname "$CLAUDE_MD")" \
    2>/dev/null | while read -r dir event filename; do
    filepath="${dir}${filename}"
    if [ "$filepath" = "$BOARD_FILE" ] || [ "$filepath" = "$CLAUDE_MD" ]; then
        schedule_sync "$filepath"
    fi
done &

wait
