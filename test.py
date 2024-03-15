import os
from pathlib import Path


def calculate_relative_path(file1, file2):
    relative_path = os.path.relpath(file1, os.path.dirname(file2))
    return relative_path


# 示例
file1 = "/path/to/your1/file1.txt"
file2 = "/path/to/your2/file2.txt"

relative_path = calculate_relative_path(file1, file2)

print(Path(relative_path).parts)
