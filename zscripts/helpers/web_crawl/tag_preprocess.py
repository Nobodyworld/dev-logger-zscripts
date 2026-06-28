import os
from collections import defaultdict
from typing import Iterable, List, Tuple

from bs4 import BeautifulSoup
from helpers.utilities.paths import org_path


def load_html_files(folder_path: str) -> List[Tuple[str, str]]:
    files_content: List[Tuple[str, str]] = []
    for filename in os.listdir(folder_path):
        if filename.endswith(".html"):
            file_path = os.path.join(folder_path, filename)
            with open(file_path, "r", encoding="utf-8") as file:
                files_content.append((filename, file.read()))
    return files_content


def count_tags(html_files: Iterable[Tuple[str, str]]):
    tag_count = defaultdict(int)
    for _filename, html in html_files:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all():
            tag_count[tag.name] += 1
    return dict(tag_count)


def find_files_with_any_tags(
    html_files: Iterable[Tuple[str, str]], tags: Iterable[str]
) -> List[str]:
    files_with_tags: List[str] = []
    for filename, html in html_files:
        soup = BeautifulSoup(html, "html.parser")
        if any(soup.find(tag) for tag in tags):
            files_with_tags.append(filename)
    return files_with_tags


# TODO - add global path function
after_folder = str(org_path("project_user", "projects", "format_ai", "data", "after_mst"))
html_files = load_html_files(after_folder)

# Count tags
tag_counts = count_tags(html_files)
print(tag_counts)

# Find files with specific tags
tags_to_find = ["u", "b", "h"]
files_with_any_tags = find_files_with_any_tags(html_files, tags_to_find)
print(f"Files containing any of the tags {tags_to_find}: {files_with_any_tags}")
