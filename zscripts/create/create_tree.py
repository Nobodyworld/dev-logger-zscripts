import sys
from pathlib import Path

# Ensure the repository root is importable when executed directly.
script_dir = Path(__file__).resolve().parent
repo_root = script_dir.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from zscripts.operations import create_tree_snapshot  # noqa: E402


def main() -> None:
    destination = create_tree_snapshot()
    print(f"Directory tree written to {destination}")


if __name__ == "__main__":
    main()
