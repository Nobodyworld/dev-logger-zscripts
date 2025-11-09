import os
import re
from typing import List, Set

from helpers.utilities.paths import org_path


def find_python_files(root_dir: str) -> List[str]:
    """Recursively find all Python files in the directory."""
    python_files: List[str] = []
    for root, _dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    return python_files


def extract_imports(file_path: str) -> Set[str]:
    """Extract import statements from a Python file."""
    with open(file_path, "r", encoding="utf-8") as file:
        contents = file.read()

    # Regular expression patterns for finding imports
    import_patterns = [r"^import (\S+)", r"^from (\S+) import"]

    imports: Set[str] = set()
    for pattern in import_patterns:
        for match in re.finditer(pattern, contents, re.MULTILINE):
            imports.add(match.group(1).split(".")[0])

    return imports


def main() -> None:
    root_dir = str(org_path("2_Stage", "l_blem"))
    all_imports: Set[str] = set()

    for python_file in find_python_files(root_dir):
        imports = extract_imports(python_file)
        all_imports.update(imports)

    # Write unique imports to a file
    with open("dependencies.txt", "w", encoding="utf-8") as file:
        for imp in sorted(all_imports):
            file.write(f"{imp}\n")

    print("Dependencies have been written to dependencies.txt")


if __name__ == "__main__":
    main()
