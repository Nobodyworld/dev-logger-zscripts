import os
import shutil

from helpers.utilities.paths import org_path


def move_files_to_original_folders(folder_path: str, before_folder: str, after_folder: str) -> None:
    """Move *_before.html and *_after.html files back to their respective folders."""
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if filename.endswith(".html"):
            if "_before" in filename:
                shutil.move(file_path, os.path.join(before_folder, filename))
            elif "_after" in filename:
                shutil.move(file_path, os.path.join(after_folder, filename))


# Specify the folder paths via org_path
exceeded_folder = str(org_path("project_user", "projects", "format_ai", "data", "exceeded_max_length"))
before_folder = str(org_path("project_user", "projects", "format_ai", "data", "before_mst"))
after_folder = str(org_path("project_user", "projects", "format_ai", "data", "after_mst"))

# Move files to their original folders
move_files_to_original_folders(exceeded_folder, before_folder, after_folder)
