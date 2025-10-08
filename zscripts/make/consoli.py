# zscripts/make/consoli.py
import sys
from pathlib import Path

# Ensure the repository root is importable when executed directly.
script_dir = Path(__file__).resolve().parent
repo_root = script_dir.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from zscripts.operations import consolidate_default_directories  # noqa: E402


def main() -> None:
    results = consolidate_default_directories()
    print("Consolidation complete. Check the consoli_files directory for consolidated files.")
    for name, path in results.items():
        print(f"  - {name}: {path}")


if __name__ == "__main__":
    main()
