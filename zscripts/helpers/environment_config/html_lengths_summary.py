import os
from typing import List

from helpers.utilities.paths import org_path


def get_html_lengths(folder_path: str) -> List[int]:
    """Return lengths (in characters) of all .html files in a folder."""
    lengths: List[int] = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path) and filename.endswith(".html"):
            with open(file_path, "r", encoding="utf-8") as file:
                html_content = file.read()
                lengths.append(len(html_content))
    return lengths


after_folder_path = str(org_path("project_user", "projects", "format_ai", "data", "after_mst"))
before_folder_path = str(org_path("project_user", "projects", "format_ai", "data", "before_mst"))

after_lengths = get_html_lengths(after_folder_path)
before_lengths = get_html_lengths(before_folder_path)

print("After HTML Files:")
print("Min Length:", min(after_lengths))
print("Max Length:", max(after_lengths))

print("\nBefore HTML Files:")
print("Min Length:", min(before_lengths))
print("Max Length:", max(before_lengths))
