# zscripts/utils.py
import fnmatch
from pathlib import Path
import os
import re
try:  # pragma: no cover - compatibility shim
    from .config import SKIP_DIRS, FILE_TYPES
except ImportError:  # pragma: no cover
    from config import SKIP_DIRS, FILE_TYPES  # type: ignore

def load_gitignore_patterns(root_path):
    """
    Loads patterns from the .gitignore file to ignore specific files and directories during operations.

    Args:
        root_path (Path): The root directory path where the .gitignore file is located.

    Returns:
        list: A list of patterns to ignore.
    """
    gitignore_path = root_path / '.gitignore'
    patterns = [
        '*.pyc', '__pycache__/', '.DS_Store', '*.sqlite3', 'db.sqlite3',
        '/staticfiles/', '/media/', 'error.dev.log', 'error.base.log', 
        'error.test.log', 'error.prod.log', 'logs', 'logs/', 'zscripts', 
        'zscripts/', 'static/', 'staticfiles/', 'migrations/', 'migrations', 
        'node_modules/', 'yarn-error.log', 'yarn-debug.log', 'yarn.lock', 
        'package-lock.json', 'package.json', 'zscripts/', 'zscripts', 'zbuild',
        'zbuild/'
    ]
    if gitignore_path.is_file():
        with open(gitignore_path, 'r', encoding='utf-8') as file:
            for line in file:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith('#'):
                    patterns.append(stripped_line)
    return patterns

def file_matches_any_pattern(file_path, patterns):
    """
    Checks if a file path matches any pattern in the provided patterns list.

    Args:
        file_path (Path): The file path to check.
        patterns (list): A list of patterns to match against.

    Returns:
        bool: True if the file path matches any pattern, False otherwise.
    """
    normalized_path = file_path.as_posix()
    if file_path.is_dir():
        normalized_path += '/'

    for pattern in patterns:
        if fnmatch.fnmatch(normalized_path, pattern):
            return True
    return False

def create_app_logs(root_dir, log_dir, file_types, ignore_patterns):
    """
    Creates logs for each app directory, including specific file types and ignoring certain patterns.

    Args:
        root_dir (Path): The root directory to scan for app directories.
        log_dir (Path): The directory to save the log files.
        file_types (set): A set of file extensions to include in the logs.
        ignore_patterns (list): A list of patterns to ignore.
    """
    for app_dir in [d for d in root_dir.iterdir() if d.is_dir()]:
        if file_matches_any_pattern(app_dir, ignore_patterns):
            continue

        log_file_name = f"{app_dir.name}.txt"
        log_file_path = log_dir / log_file_name

        with open(log_file_path, 'w', encoding='utf-8') as log_file:
            for root, dirs, files in os.walk(app_dir):
                dirs[:] = [d for d in dirs if not file_matches_any_pattern(Path(root) / d, ignore_patterns)]
                files = [f for f in files if Path(f).suffix in file_types and not file_matches_any_pattern(Path(root) / f, ignore_patterns)]

                if files:
                    relative_root = Path(root).relative_to(root_dir)
                    print(f"{relative_root}/", file=log_file)
                    for file in sorted(files):
                        file_path = Path(root) / file
                        print(f"    {file}", file=log_file)
                        with open(file_path, 'r', encoding='utf-8') as content_file:
                            content = content_file.read().strip()
                            print(content, file=log_file)
                            print("\n---\n", file=log_file)

def consolidate_files(root_dir, log_file_path, file_types, ignore_patterns):
    """
    Consolidates content of all specified file types from the root directory into a single log file.

    Args:
        root_dir (Path): The root directory to scan for files.
        log_file_path (Path): The file path to save the consolidated log.
        file_types (set): A set of file extensions to include in the log.
        ignore_patterns (list): A list of patterns to ignore.
    """
    with open(log_file_path, 'w', encoding='utf-8') as log_file:
        for root, dirs, files in os.walk(root_dir):
            # Skip the 'zscripts' directory
            if 'zscripts' in Path(root).parts:
                continue
            dirs[:] = [d for d in dirs if not file_matches_any_pattern(Path(root) / d, ignore_patterns)]
            for file in files:
                file_path = Path(root) / file
                if Path(file).suffix in file_types and not file_matches_any_pattern(file_path, ignore_patterns):
                    relative_path = file_path.relative_to(root_dir)
                    log_file.write(f"\n\n# File: {relative_path}\n")
                    with open(file_path, 'r', encoding='utf-8') as content_file:
                        content = content_file.read()
                        log_file.write(content)
                        log_file.write("\n" + ("." * 3) + "\n")


def create_filtered_tree(start_path, log_file_path, file_types=None, ignore_patterns=None):
    """
    Creates a directory tree structure and logs the content of specified file types, ignoring certain patterns.

    Args:
        start_path (Path): The starting directory path.
        log_file_path (Path): The file path to save the log.
        file_types (set, optional): A set of file extensions to include in the logs. Defaults to {'.py', '.html', '.js', '.css'}.
        ignore_patterns (list, optional): A list of patterns to ignore. Defaults to an empty list.
    """
    if file_types is None:
        file_types = {'.py', '.html', '.js', '.css'}
    if ignore_patterns is None:
        ignore_patterns = []

    with open(log_file_path, 'w') as log_file:
        for root, dirs, files in os.walk(start_path, topdown=True):
            dirs[:] = [d for d in dirs if not file_matches_any_pattern(Path(root) / d, ignore_patterns)]
            files = [f for f in files if Path(f).suffix in file_types and not file_matches_any_pattern(Path(root) / f, ignore_patterns)]

            if files:
                relative_root = Path(root).relative_to(start_path)
                print(f"{relative_root}/", file=log_file)
                for file in sorted(files):
                    file_path = Path(root) / file
                    print(f"    {file}", file=log_file)
                    with open(file_path, 'r', encoding='utf-8') as content_file:
                        content = content_file.read()
                        print(content, file=log_file)
                        print(("." * 3), file=log_file)

def process_file(file_path, file_type_key, content_dict):
    """
    Processes a file by reading its content and appending it to a dictionary under a specified key.

    Args:
        file_path (Path): The path of the file to process.
        file_type_key (str): The key representing the file type in the content dictionary.
        content_dict (dict): The dictionary to store file content.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    content_dict[file_type_key] += f"\n\n# File: {file_path.relative_to(file_path.parent.parent)}\n{content}"

def write_files(content_dict, dest_dir):
    """
    Writes the aggregated content from the dictionary to individual files in the specified directory.

    Args:
        content_dict (dict): The dictionary containing file content.
        dest_dir (Path): The destination directory to save the files.
    """
    for key, content in content_dict.items():
        dest_file_path = os.path.join(dest_dir, f"{key}.txt")
        with open(dest_file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"Written content to {dest_file_path}")

def extract_definitions(file_path, analysis_dir):
    """
    Extracts and writes class and function names from a given Python file to a log file.

    Args:
        file_path (Path): The path of the Python file to analyze.
        analysis_dir (Path): The directory to save the analysis logs.

    Notes:
        - This function reads the content of the file, uses regular expressions to find class and function definitions,
          and writes the extracted names to a corresponding text file in the analysis directory.
        - The resulting log file is named based on the original Python file name with a .txt extension.
    """
    base_name = file_path.name
    analysis_file_name = base_name.replace('.py', '.txt')
    analysis_file_path = analysis_dir / analysis_file_name

    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    classes = re.findall(r'^class (\w+)', content, re.MULTILINE)
    functions = re.findall(r'^def (\w+)', content, re.MULTILINE)

    with open(analysis_file_path, 'w', encoding='utf-8') as analysis_file:
        if classes:
            analysis_file.write("Classes:\n")
            analysis_file.writelines(f"{cls}\n" for cls in classes)
        if functions:
            analysis_file.write("\nFunctions:\n")
            analysis_file.writelines(f"{func}\n" for func in functions)

    print(f"Analysis for {base_name} written to {analysis_file_name}")

