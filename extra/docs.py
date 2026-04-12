import subprocess
import re
from pathlib import Path


result = subprocess.run(
    ["pydoc-markdown"],
    check=True,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
print("pydoc-markdown output:")
print(result.stdout)

a = re.compile(r"<a id=.+></a>")


new_line = []
skip = False
ignore = False
current_level = 0
next_level = 0
for line in result.stdout.split("\n"):
    if line.startswith("```"):
        skip = not skip
    if not skip:
        if line.startswith("# "):
            next_level = 1
            if line.startswith("# clovers.typing"):
                ignore = True
            elif line.startswith("# clovers."):
                line = f"# {line[10:]}"
                ignore = False
            else:
                ignore = True
        if ignore:
            continue
        if a.match(line):
            continue
        if line.startswith("## "):
            next_level = 2
        elif line.startswith("### "):
            next_level = 3
        elif line.startswith("#### "):
            next_level = 3
            line = line[1:]
        if line.endswith(" Objects"):
            line = line[:-8]
        if next_level == 3 and current_level == 1:
            new_line.append("## Module Attributes")
            new_line.append("\n")
            new_line.append("文件级属性")
            new_line.append("\n")
        current_level = next_level
    new_line.append(line)

Path("document.md").write_text("\n".join(new_line), encoding="utf8")
