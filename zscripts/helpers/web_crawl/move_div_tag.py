import os
from typing import Dict, Optional

from bs4 import BeautifulSoup
from helpers.utilities.paths import org_path


def remove_tags(folder_path: str, tag_name: str, attrs: Optional[Dict[str, str]] = None) -> None:
    # Get a list of all files in the folder
    files = os.listdir(folder_path)

    for file in files:
        if file.endswith(".html"):
            file_path = os.path.join(folder_path, file)

            # Read the HTML file with the correct encoding
            with open(file_path, "r", encoding="utf-8") as f:
                html = f.read()

            # Parse the HTML using BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Remove tags matching the specified tag_name and attrs
            for tag in soup.find_all(tag_name, attrs=attrs):
                tag.extract()

            # Save the modified HTML back to the file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(str(soup))

            print(f"Removed {tag_name} tags from {file}")


# Specify the folder path
folder_path = str(org_path("project_user", "projects", "format_ai", "data", "after_mst"))

# Specify the tags and attributes to remove
tags_to_remove = [
    {"tag_name": "div", "attrs": {"style": "text-align: center;"}},
    {
        "tag_name": "div",
        "attrs": {"class": "separator", "style": "clear: both; text-align: center;"},
    },
    {"tag_name": "div", "attrs": {"style": "text-align: center;", "class": "separator"}},
]

# Call the function to remove the specified tags
for tag in tags_to_remove:
    remove_tags(folder_path, tag["tag_name"], tag["attrs"])
