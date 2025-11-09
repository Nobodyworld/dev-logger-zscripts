import os

from helpers.utilities.paths import org_path


def compare_directories(src_dir: str, target_dir: str) -> None:
    """Compare file stems between two directories and print differences.

    Treats files with a trailing underscore segment (e.g., name_123.jpg) as the same stem.
    """
    src_files = {os.path.splitext(file)[0].rsplit("_", 1)[0] for file in os.listdir(src_dir)}
    target_files = {os.path.splitext(file)[0].rsplit("_", 1)[0] for file in os.listdir(target_dir)}

    in_src_not_target = src_files - target_files
    if in_src_not_target:
        print(f"Files in '{src_dir}' but not in '{target_dir}':")
        for filename in in_src_not_target:
            print(filename)
    else:
        print(f"All files in '{src_dir}' are also in '{target_dir}'.")

    in_target_not_src = target_files - src_files
    if in_target_not_src:
        print(f"\nFiles in '{target_dir}' but not in '{src_dir}':")
        for filename in in_target_not_src:
            print(filename)
    else:
        print(f"\nAll files in '{target_dir}' are also in '{src_dir}'.")


source_folder = str(org_path("project_user", "projects", "format_ai", "data", "before_mst"))
target_folder = str(org_path("project_user", "projects", "format_ai", "data", "after_mst"))

compare_directories(source_folder, target_folder)
