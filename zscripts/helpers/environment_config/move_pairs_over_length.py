import os
import shutil
from typing import Final

from helpers.utilities.paths import org_path


def check_file_length(file_path: str, max_length: int) -> bool:
    """Return True if the file's text length exceeds max_length characters."""
    with open(file_path, "r", encoding="utf-8") as file:
        return len(file.read()) > max_length


def move_files_over_max_length(
    after_folder: str, before_folder: str, dest_folder: str, max_length: int
) -> None:
    """Move before/after HTML pairs to dest_folder if either exceeds max_length."""
    for after_file in os.listdir(after_folder):
        after_file_path = os.path.join(after_folder, after_file)
        before_file = after_file.replace("_after.html", "_before.html")
        before_file_path = os.path.join(before_folder, before_file)

        if os.path.exists(before_file_path) and (
            check_file_length(after_file_path, max_length) or check_file_length(before_file_path, max_length)
        ):
            shutil.move(after_file_path, os.path.join(dest_folder, after_file))
            shutil.move(before_file_path, os.path.join(dest_folder, before_file))


AFTER_FOLDER: Final[str] = str(org_path("project_user", "projects", "format_ai", "data", "after_mst"))
BEFORE_FOLDER: Final[str] = str(org_path("project_user", "projects", "format_ai", "data", "before_mst"))
DEST_FOLDER: Final[str] = str(
    org_path("project_user", "projects", "format_ai", "data", "exceeded_max_length")
)
MAX_LENGTH: Final[int] = 6000

move_files_over_max_length(AFTER_FOLDER, BEFORE_FOLDER, DEST_FOLDER, MAX_LENGTH)
