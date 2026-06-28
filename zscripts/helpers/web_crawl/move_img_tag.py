import os

from bs4 import BeautifulSoup
from helpers.utilities.paths import org_path


def remove_img_tags(folder_path: str) -> None:
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

            # Remove img tags from the HTML
            for img in soup.find_all("img"):
                img.extract()

            # Save the modified HTML back to the file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(str(soup))

            print(f"Removed img tags from {file}")


# Specify the folder path via org_path
folder_path = str(org_path("project_user", "projects", "format_ai", "data", "before_mst"))

# Call the function to remove img tags
remove_img_tags(folder_path)
