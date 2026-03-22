import re

# Default project map -- customize via project_map in notion-sync-config.json
DEFAULT_PROJECT_MAP = {
    "general": "General",
}

_custom_project_map = None


def set_project_map(project_map):
    """Set a custom project map from config. Call once at startup."""
    global _custom_project_map
    _custom_project_map = project_map


def _get_project_map():
    if _custom_project_map:
        merged = dict(DEFAULT_PROJECT_MAP)
        merged.update(_custom_project_map)
        return merged
    return DEFAULT_PROJECT_MAP


def parse_session_filename(filename):
    name = filename.replace(".md", "")
    date_match = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)$", name)
    if not date_match:
        return {"date": None, "project": "General", "title": name}
    date_str = date_match.group(1)
    rest = date_match.group(2)
    project_map = _get_project_map()
    project = "General"
    for prefix, proj_name in sorted(project_map.items(), key=lambda x: -len(x[0])):
        if rest.startswith(prefix):
            project = proj_name
            break
    return {"date": date_str, "project": project, "title": name}
