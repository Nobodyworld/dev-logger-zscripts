import os
import re

from bs4 import BeautifulSoup

from helpers.utilities.paths import org_path


def compare_files(before_folder: str, after_folder: str, output_file: str) -> None:
    """Write after-filenames where 'conclusion' appears but not in corresponding before file."""
    # Get a list of all files in the folder
    before_files = os.listdir(before_folder)
    after_files = os.listdir(after_folder)

    # Open the output file for writing
    with open(output_file, "w", encoding="utf-8") as out:

        # Iterate over each file in the before folder
        for before_file in before_files:
            if before_file.endswith(".html"):

                # Construct the matching file name in the after folder
                after_file = before_file.replace("_before", "_after")

                # Check if the after file exists
                if after_file in after_files:

                    # Read and parse the before file
                    with open(os.path.join(before_folder, before_file), "r", encoding="utf-8") as f:
                        before_html = f.read()
                    before_soup = BeautifulSoup(before_html, "html.parser")
                    before_text = before_soup.get_text()
                    # TODO - add global path function
                    before_words = re.findall(r"\bconclusion\b", before_text, re.IGNORECASE)

                    # Read and parse the after file
                    with open(os.path.join(after_folder, after_file), "r", encoding="utf-8") as f:
                        after_html = f.read()
                    after_soup = BeautifulSoup(after_html, "html.parser")
                    after_text = after_soup.get_text()
                    # TODO - add global path function
                    after_words = re.findall(r"\bconclusion\b", after_text, re.IGNORECASE)

                    # Check if 'conclusion' is present in the after file but not in the before file
                    if len(after_words) > 0 and len(before_words) == 0:
                        out.write(after_file + "\n")
                        print(
                            "'Conclusion' found in",
                            after_file,
                            "but not in corresponding before file",
                        )


# Specify the folder paths and output file
before_folder = str(org_path("project_user", "projects", "format_ai", "data", "before_mst"))
after_folder = str(org_path("project_user", "projects", "format_ai", "data", "after_mst"))
output_file = str(org_path("project_user", "projects", "format_ai", "data", "diff_files.txt"))

# Call the function to compare files
compare_files(before_folder, after_folder, output_file)
