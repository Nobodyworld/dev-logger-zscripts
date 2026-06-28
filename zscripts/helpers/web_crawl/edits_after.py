import os

from bs4 import BeautifulSoup, Comment
from helpers.utilities.paths import org_path

directory = str(org_path("project_user", "projects", "format_ai", "data", "after_mst"))


def process_html(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove comments
    for comment in soup.findAll(text=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Process tags
    lines = []
    for tag in soup.recursiveChildGenerator():
        if tag.name:
            # TODO - add global path function
            if str(tag) == "<p><br/></p>":
                lines[-1] += str(tag)
            else:
                lines.append(str(tag))

    return "\n".join(lines)


for filename in os.listdir(directory):
    if filename.endswith(".html"):
        file_path = os.path.join(directory, filename)
        with open(file_path, "r", encoding="utf-8") as file:
            html_content = file.read()

        processed_content = process_html(html_content)

        with open(file_path, "w", encoding="utf-8") as file:
            file.write(processed_content)
