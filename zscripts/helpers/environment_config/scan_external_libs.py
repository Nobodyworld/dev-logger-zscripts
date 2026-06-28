import ast
import os
from typing import Set

from helpers.utilities.paths import org_path
from stdlib_list import stdlib_list

# Define the path to your scripts folder
scripts_folder = str(org_path("Core", "Command", "Scripts"))

# List of all Python standard libraries for Python 3.8 (or your current Python version)
standard_libs: Set[str] = set(stdlib_list("3.8"))

# Set to store names of external libraries
external_libs: Set[str] = set()


# Function to check if a module is an external library
def is_external_library(module_name: str) -> bool:
    return module_name not in standard_libs and "." not in module_name


# Function to process each Python file
def process_file(file_path: str) -> None:
    with open(file_path, "r", encoding="utf-8") as file:
        tree = ast.parse(file.read(), filename=file_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    if is_external_library(name.name.split(".")[0]):
                        external_libs.add(name.name)
            elif isinstance(node, ast.ImportFrom):
                if is_external_library(node.module.split(".")[0]):
                    external_libs.add(node.module)


# Scan the scripts folder and process each .py file
for root, _dirs, files in os.walk(scripts_folder):
    for file in files:
        if file.endswith(".py"):
            process_file(os.path.join(root, file))

# Write the external libraries to a file
with open("external_libs.txt", "w", encoding="utf-8") as output_file:
    for lib in sorted(external_libs):
        output_file.write(f"{lib}\n")

print("External libraries have been written to external_libs.txt")
