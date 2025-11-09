import os

from helpers.utilities.paths import org_path


def print_directory_structure(rootdir: str) -> None:
    """Print the directory structure of the given root directory."""
    for subdir, _dirs, files in os.walk(rootdir):
        level = subdir.replace(rootdir, "").count(os.sep)
        indent = " " * 4 * level
        print(f"{indent}{os.path.basename(subdir)}/")
        subindent = " " * 4 * (level + 1)
        for file in files:
            print(f"{subindent}{file}")


# Use the organization storage root as the base
rootdir = str(org_path())
print_directory_structure(rootdir)
