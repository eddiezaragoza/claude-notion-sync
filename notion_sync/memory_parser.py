import os
import re


def parse_memory_file(file_path):
    with open(file_path, "r") as f:
        content = f.read()
    name = os.path.basename(file_path).replace(".md", "")
    mem_type = "unknown"
    description = ""
    body = content
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if fm_match:
        frontmatter = fm_match.group(1)
        body = fm_match.group(2).strip()
        for line in frontmatter.split("\n"):
            if line.startswith("name:"):
                name = line[5:].strip()
            elif line.startswith("type:"):
                mem_type = line[5:].strip()
            elif line.startswith("description:"):
                description = line[12:].strip()
    return {
        "name": name,
        "type": mem_type,
        "description": description,
        "body": body,
        "source_file": os.path.basename(file_path),
    }
