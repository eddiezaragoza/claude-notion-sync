#!/usr/bin/env bash
# notion-sync-watcher.sh -- Filesystem watcher for Notion sync
# Uses inotifywait for native Linux paths, polling for /mnt/ (WSL Windows filesystem)
# WSL's drvfs doesn't generate reliable inotify events, so we poll those paths instead.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYNC_SCRIPT="$SCRIPT_DIR/notion-sync.py"
CONFIG_FILE="$SCRIPT_DIR/notion-sync-config.json"
PID_FILE="/tmp/notion-sync-watcher.pid"
DEBOUNCE_DIR="/tmp/notion-sync-debounce"
POLL_STATE_DIR="/tmp/notion-sync-poll-state"

DEBOUNCE_SECONDS=60
POLL_INTERVAL=30  # seconds between polls for /mnt/ paths

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

mkdir -p "$DEBOUNCE_DIR" "$POLL_STATE_DIR"
echo $$ > "$PID_FILE"
trap "rm -f $PID_FILE; exit" INT TERM EXIT

echo "Notion sync watcher started (PID $$)"

is_wsl_path() {
    [[ "$1" == /mnt/* ]]
}

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

# --- Polling for WSL /mnt/ paths (inotifywait unreliable on drvfs) ---

poll_directory() {
    local dir="$1"
    local filter_fn="$2"  # "sessions" or "memory"

    while true; do
        sleep "$POLL_INTERVAL"
        for filepath in "$dir"/*.md; do
            [ -f "$filepath" ] || continue
            local basename=$(basename "$filepath")

            if [ "$filter_fn" = "memory" ] && [ "$basename" = "MEMORY.md" ]; then
                continue
            fi

            local hash=$(echo -n "$filepath" | md5sum | cut -d' ' -f1)
            local state_file="$POLL_STATE_DIR/$hash"
            local current_mtime=$(stat -c %Y "$filepath" 2>/dev/null)

            if [ -f "$state_file" ]; then
                local last_mtime=$(cat "$state_file")
                if [ "$current_mtime" != "$last_mtime" ]; then
                    echo "$current_mtime" > "$state_file"
                    schedule_sync "$filepath"
                fi
            else
                echo "$current_mtime" > "$state_file"
            fi
        done
    done
}

poll_file() {
    local filepath="$1"
    local hash=$(echo -n "$filepath" | md5sum | cut -d' ' -f1)
    local state_file="$POLL_STATE_DIR/$hash"

    if [ -f "$filepath" ]; then
        stat -c %Y "$filepath" > "$state_file"
    fi

    while true; do
        sleep "$POLL_INTERVAL"
        [ -f "$filepath" ] || continue
        local current_mtime=$(stat -c %Y "$filepath" 2>/dev/null)
        local last_mtime=$(cat "$state_file" 2>/dev/null)
        if [ "$current_mtime" != "$last_mtime" ]; then
            echo "$current_mtime" > "$state_file"
            schedule_sync "$filepath"
        fi
    done
}

# --- Start watchers based on path type ---

# Sessions directory
if is_wsl_path "$SESSIONS_DIR"; then
    echo "  Sessions (polling every ${POLL_INTERVAL}s): $SESSIONS_DIR"
    poll_directory "$SESSIONS_DIR" "sessions" &
else
    echo "  Sessions (inotify): $SESSIONS_DIR"
    inotifywait -m -r \
        --event close_write --event moved_to \
        --include '\.md$' \
        "$SESSIONS_DIR" \
        2>/dev/null | while read -r dir event filename; do
        schedule_sync "${dir}${filename}"
    done &
fi

# Memory directory
if is_wsl_path "$MEMORY_DIR"; then
    echo "  Memory (polling every ${POLL_INTERVAL}s): $MEMORY_DIR"
    poll_directory "$MEMORY_DIR" "memory" &
else
    echo "  Memory (inotify): $MEMORY_DIR"
    inotifywait -m -r \
        --event close_write --event moved_to \
        --include '\.md$' \
        "$MEMORY_DIR" \
        2>/dev/null | while read -r dir event filename; do
        filepath="${dir}${filename}"
        [ "$(basename "$filepath")" != "MEMORY.md" ] && schedule_sync "$filepath"
    done &
fi

# Board file
if is_wsl_path "$BOARD_FILE"; then
    echo "  Board (polling every ${POLL_INTERVAL}s): $BOARD_FILE"
    poll_file "$BOARD_FILE" &
else
    echo "  Board (inotify): $BOARD_FILE"
    inotifywait -m \
        --event close_write --event moved_to \
        "$(dirname "$BOARD_FILE")" \
        2>/dev/null | while read -r dir event filename; do
        [ "${dir}${filename}" = "$BOARD_FILE" ] && schedule_sync "$BOARD_FILE"
    done &
fi

# CLAUDE.md
if is_wsl_path "$CLAUDE_MD"; then
    echo "  CLAUDE.md (polling every ${POLL_INTERVAL}s): $CLAUDE_MD"
    poll_file "$CLAUDE_MD" &
else
    echo "  CLAUDE.md (inotify): $CLAUDE_MD"
    inotifywait -m \
        --event close_write --event moved_to \
        "$(dirname "$CLAUDE_MD")" \
        2>/dev/null | while read -r dir event filename; do
        [ "${dir}${filename}" = "$CLAUDE_MD" ] && schedule_sync "$CLAUDE_MD"
    done &
fi

wait
