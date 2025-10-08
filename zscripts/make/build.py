# zscripts/make/build.py
import sys
from pathlib import Path

# Ensure the repository root is importable when executed directly.
script_dir = Path(__file__).resolve().parent
repo_root = script_dir.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from zscripts.config import BUILD_DIR, WORK_DIR  # noqa: E402
from zscripts.operations import convert_work_directory  # noqa: E402


def main() -> None:
    written_files = convert_work_directory()
    if not written_files:
        print(f"No files to process in {WORK_DIR}. Ensure the directory exists and contains the necessary files.")
        return

    print("Converted and moved the following files:")
    for path in written_files:
        print(f"  - {path}")
    print(f"All files have been processed and are located in '{BUILD_DIR}'.")


if __name__ == "__main__":
    main()
