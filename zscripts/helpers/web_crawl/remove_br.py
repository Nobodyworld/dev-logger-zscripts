import os

from bs4 import BeautifulSoup
from helpers.utilities.paths import org_path

directory = str(org_path("project_user", "projects", "format_ai", "data", "after_mst"))


def remove_breaks(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove <p><br/></p> and <br/>
    for match in soup.findAll("p"):
        if match.contents == ["<br/>"]:
            match.decompose()

    for match in soup.findAll("br"):
        match.decompose()

    return str(soup)


for filename in os.listdir(directory):
    if filename.endswith(".html"):
        file_path = os.path.join(directory, filename)
        with open(file_path, "r", encoding="utf-8") as file:
            html_content = file.read()

        cleaned_content = remove_breaks(html_content)

        with open(file_path, "w", encoding="utf-8") as file:
            file.write(cleaned_content)
