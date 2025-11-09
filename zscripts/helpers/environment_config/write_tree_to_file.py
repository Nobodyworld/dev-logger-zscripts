import os

from helpers.utilities.paths import org_path


def print_directory_structure_to_file(startpath: str, output_file_path: str) -> None:
    with open(output_file_path, "w", encoding="utf-8") as file:
        for root, _dirs, files in os.walk(startpath):
            level = root.replace(startpath, "").count(os.sep)
            indent = " " * 4 * level
            file.write(f"{indent}{os.path.basename(root)}/\n")
            subindent = " " * 4 * (level + 1)
            for f in files:
                file.write(f"{subindent}{f}\n")


start_directory = str(org_path())
output_file = str(org_path("tree_file.txt"))
print_directory_structure_to_file(start_directory, output_file)
