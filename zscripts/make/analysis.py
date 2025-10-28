# zscripts/make/analysis.py
import sys
from pathlib import Path

# Ensure the repository root is importable when executed directly.
script_dir = Path(__file__).resolve().parent
repo_root = script_dir.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from zscripts.operations import analyse_build_directory  # noqa: E402


def main() -> None:
    written = analyse_build_directory()
    if not written:
        print("No Python files found in the build directory. Nothing to analyse.")
        return

    print("Extraction complete. Check the analysis logs directory for details.")
    for path in written:
        print(f"  - {path}")


if __name__ == "__main__":
    main()
