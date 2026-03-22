import hashlib
import re
import os


def compute_stable_id(project, task_description):
    raw = f"{project}:{task_description}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def parse_board(file_path):
    with open(file_path, "r") as f:
        content = f.read()
    tasks = []
    current_project = None
    current_status = None
    for line in content.split("\n"):
        stripped = line.strip()
        proj_match = re.match(r"^## (.+)$", stripped)
        if proj_match:
            current_project = proj_match.group(1).strip()
            current_status = None
            continue
        status_match = re.match(r"^### (In Progress|Backlog|Blocked|Completed|Cancelled)$", stripped)
        if status_match:
            current_status = status_match.group(1)
            continue
        if not current_project or not current_status:
            continue
        # Active tasks: numbered
        active_match = re.match(r"^\d+\.\s+(.+?)\s*\*\((\d{4}-\d{2}-\d{2})\)\*\s*$", stripped)
        if active_match and current_status in ("In Progress", "Backlog", "Blocked"):
            task_desc = active_match.group(1).strip()
            clean_desc = re.sub(r"^[^\w]*", "", task_desc).strip()
            tasks.append({
                "stable_id": compute_stable_id(current_project, clean_desc),
                "task": task_desc,
                "project": current_project,
                "status": current_status,
                "added": active_match.group(2),
                "session_link": None,
            })
            continue
        # Completed/Cancelled
        done_match = re.match(
            r"^-\s+~~(.+?)~~\s+\*\((completed|cancelled)\s+(\d{4}-\d{2}-\d{2})\)\*"
            r"(?:\s*(?:->|-->|->|→)\s*`(.+?)`)?",
            stripped,
        )
        if done_match and current_status in ("Completed", "Cancelled"):
            task_desc = done_match.group(1).strip()
            tasks.append({
                "stable_id": compute_stable_id(current_project, task_desc),
                "task": task_desc,
                "project": current_project,
                "status": current_status,
                "added": done_match.group(3),
                "session_link": done_match.group(4),
            })
    return tasks
