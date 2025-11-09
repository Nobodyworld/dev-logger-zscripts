import argparse
import re
from pathlib import Path
from typing import Dict, Set


def extract_imports(file_path: Path) -> Set[str]:
    """Extract import/module names from a Python source file."""
    content = file_path.read_text(encoding="utf-8")
    return set(re.findall(r"^\s*(?:import|from)\s+([\w\.]+)", content, re.MULTILINE))


def analyse_imports(directory: Path) -> Dict[str, Set[str]]:
    """Analyze all .py files under a directory and map script -> imports."""
    results: Dict[str, Set[str]] = {}
    for path in directory.rglob("*.py"):
        results[path.name] = extract_imports(path)
    return results


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for imports report."""
    parser = argparse.ArgumentParser(
        description="List import statements used by Python scripts in a directory."
    )
    parser.add_argument("directory", type=Path, help="Root directory containing Python scripts.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    directory = args.directory.expanduser().resolve()
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    imports_map = analyse_imports(directory)
    for script, imports in sorted(imports_map.items()):
        print(f"Script: {script}")
        for module in sorted(imports):
            print(f" - {module}")
        print()

    print("Import analysis complete.")


if __name__ == "__main__":
    main()
