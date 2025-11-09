import importlib.metadata
import os
from collections import defaultdict
from typing import Dict, Set


def get_imports(file_path: str) -> Set[str]:
    """Extract imported top-level modules from a Python file."""
    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    imports: Set[str] = set()
    for line in lines:
        line = line.strip()
        if line.startswith("import "):
            imported = line.split("import ")[1]
            if "," in imported:
                imports.update([imp.strip() for imp in imported.split(",")])
            else:
                imports.add(imported)
        elif line.startswith("from "):
            imported = line.split(" ")[1]
            imports.add(imported)

    return imports


def get_installed_packages() -> Dict[str, str]:
    """Return a mapping of installed package name to version."""
    return {dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()}


def build_requirements(directory: str) -> None:
    """Build a requirements.txt file from Python files in the given directory."""
    all_imports: Dict[str, Set[str]] = defaultdict(set)
    installed_packages = get_installed_packages()

    for root, _dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                imports = get_imports(file_path)
                for imp in imports:
                    if imp in installed_packages:
                        all_imports[imp].add(installed_packages[imp])

    with open("requirements.txt", "w", encoding="utf-8") as req_file:
        for package, versions in all_imports.items():
            version = max(versions)  # Choose the highest version if multiple versions are found
            req_file.write(f"{package}=={version}\n")


# Use the function
directory_path = "."  # Set the directory path here
build_requirements(directory_path)
