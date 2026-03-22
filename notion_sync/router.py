import os


def route_file(file_path):
    basename = os.path.basename(file_path)
    if basename == "MEMORY.md":
        return None
    if "/claude-sessions/" in file_path and basename.endswith(".md"):
        return {"type": "session", "target": "sessions", "file_path": file_path}
    if "/memory/" in file_path and basename.endswith(".md"):
        return {"type": "memory", "target": "memory", "file_path": file_path}
    if basename == "BOARD.md":
        return {"type": "board", "target": "board", "file_path": file_path}
    if basename == "CLAUDE.md" and "/.claude/" in file_path:
        return {"type": "claude_md", "target": "claude_md_parent", "file_path": file_path}
    return None
