import re


def parse_claude_md(content):
    sections = []
    current_heading = None
    current_lines = []
    for line in content.split("\n"):
        heading_match = re.match(r"^# (.+)$", line)
        if heading_match:
            if current_heading is not None:
                sections.append({
                    "heading": current_heading,
                    "body": "\n".join(current_lines).strip(),
                })
            current_heading = heading_match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading is not None:
        sections.append({
            "heading": current_heading,
            "body": "\n".join(current_lines).strip(),
        })
    return sections
