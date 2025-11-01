# zscripts/utils.py
from __future__ import annotations

import fnmatch
import os
import re
from collections.abc import Collection, Mapping, MutableMapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO, Union, cast

LogDestination = Union[Path, str, os.PathLike[str], TextIO]


@contextmanager
def _open_text_destination(destination: LogDestination) -> Iterator[TextIO]:
    if hasattr(destination, "write"):
        yield cast(TextIO, destination)
        return

    path = Path(destination)
    with open(path, "w", encoding="utf-8") as handle:
        yield handle


def load_gitignore_patterns(root_path: Path) -> list[str]:
    """Load ignore patterns derived from ``root_path / .gitignore``."""

    gitignore_path = root_path / ".gitignore"
    patterns = [
        "*.pyc",
        "__pycache__/",
        ".DS_Store",
        "*.sqlite3",
        "db.sqlite3",
        "/staticfiles/",
        "/media/",
        "error.dev.log",
        "error.base.log",
        "error.test.log",
        "error.prod.log",
        "logs",
        "logs/",
        "zscripts",
        "zscripts/",
        "static/",
        "staticfiles/",
        "migrations/",
        "migrations",
        "node_modules/",
        "yarn-error.log",
        "yarn-debug.log",
        "yarn.lock",
        "package-lock.json",
        "package.json",
        "zscripts/",
        "zscripts",
        "zbuild",
        "zbuild/",
    ]
    if gitignore_path.is_file():
        with open(gitignore_path, "r", encoding="utf-8") as file:
            for line in file:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith("#"):
                    patterns.append(stripped_line)
    return patterns


def file_matches_any_pattern(file_path: Path, patterns: Sequence[str]) -> bool:
    """Return ``True`` when ``file_path`` matches any glob ``patterns`` entry."""

    normalized_path = file_path.as_posix()
    if file_path.is_dir():
        normalized_path += "/"

    for pattern in patterns:
        if fnmatch.fnmatch(normalized_path, pattern):
            return True
    return False

def create_app_logs(
    root_dir: Path,
    log_dir: Path,
    file_types: Collection[str],
    ignore_patterns: Sequence[str],
) -> None:
    """Generate per-application log bundles under ``log_dir``."""

    for app_dir in [d for d in root_dir.iterdir() if d.is_dir()]:
        if file_matches_any_pattern(app_dir, ignore_patterns):
            continue

        log_file_name = f"{app_dir.name}.txt"
        log_file_path = log_dir / log_file_name

        with open(log_file_path, "w", encoding="utf-8") as log_file:
            for root, dirs, files in os.walk(app_dir):
                dirs[:] = [d for d in dirs if not file_matches_any_pattern(Path(root) / d, ignore_patterns)]
                files = [
                    f
                    for f in files
                    if Path(f).suffix in file_types
                    and not file_matches_any_pattern(Path(root) / f, ignore_patterns)
                ]

                if files:
                    relative_root = Path(root).relative_to(root_dir)
                    print(f"{relative_root}/", file=log_file)
                    for file in sorted(files):
                        file_path = Path(root) / file
                        print(f"    {file}", file=log_file)
                        with open(file_path, "r", encoding="utf-8") as content_file:
                            content = content_file.read().strip()
                            print(content, file=log_file)
                            print("\n---\n", file=log_file)


def consolidate_files(
    root_dir: Path,
    log_file_path: LogDestination,
    file_types: Collection[str],
    ignore_patterns: Sequence[str],
) -> None:
    """Consolidate files into a single bundle respecting ``file_types`` filters."""

    with _open_text_destination(log_file_path) as log_file:
        for root, dirs, files in os.walk(root_dir):
            # Skip the 'zscripts' directory
            if "zscripts" in Path(root).parts:
                continue
            dirs[:] = [d for d in dirs if not file_matches_any_pattern(Path(root) / d, ignore_patterns)]
            for file in files:
                file_path = Path(root) / file
                if Path(file).suffix in file_types and not file_matches_any_pattern(file_path, ignore_patterns):
                    relative_path = file_path.relative_to(root_dir)
                    log_file.write(f"\n\n# File: {relative_path}\n")
                    with open(file_path, "r", encoding="utf-8") as content_file:
                        content = content_file.read()
                        log_file.write(content)
                        log_file.write("\n" + ("." * 3) + "\n")


def create_filtered_tree(
    start_path: Path,
    log_file_path: LogDestination,
    file_types: Collection[str] | None = None,
    ignore_patterns: Sequence[str] | None = None,
) -> None:
    """Emit a filtered directory tree with optional inline file contents."""

    if file_types is None:
        file_types = {".py", ".html", ".js", ".css"}
    if ignore_patterns is None:
        ignore_patterns = []

    with _open_text_destination(log_file_path) as log_file:
        for root, dirs, files in os.walk(start_path, topdown=True):
            dirs[:] = [d for d in dirs if not file_matches_any_pattern(Path(root) / d, ignore_patterns)]
            files = [
                f
                for f in files
                if Path(f).suffix in file_types and not file_matches_any_pattern(Path(root) / f, ignore_patterns)
            ]

            if files:
                relative_root = Path(root).relative_to(start_path)
                print(f"{relative_root}/", file=log_file)
                for file in sorted(files):
                    file_path = Path(root) / file
                    print(f"    {file}", file=log_file)
                    with open(file_path, "r", encoding="utf-8") as content_file:
                        content = content_file.read()
                        print(content, file=log_file)
                        print(("." * 3), file=log_file)


def process_file(file_path: Path, file_type_key: str, content_dict: MutableMapping[str, str]) -> None:
    """Append ``file_path`` contents to ``content_dict[file_type_key]``."""

    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
    content_dict[file_type_key] += f"\n\n# File: {file_path.relative_to(file_path.parent.parent)}\n{content}"

def write_files(content_dict: Mapping[str, str], dest_dir: Path) -> None:
    """Write aggregated ``content_dict`` payloads into ``dest_dir``."""

    for key, content in content_dict.items():
        dest_file_path = os.path.join(dest_dir, f"{key}.txt")
        with open(dest_file_path, "w", encoding="utf-8") as file:
            file.write(content)
        print(f"Written content to {dest_file_path}")

def extract_definitions(file_path: Path, analysis_dir: Path) -> None:
    """Write a summary of definitions discovered in ``file_path`` to ``analysis_dir``."""

    base_name = file_path.name
    analysis_file_name = base_name.replace(".py", ".txt")
    analysis_file_path = analysis_dir / analysis_file_name

    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    classes = re.findall(r"^class (\w+)", content, re.MULTILINE)
    functions = re.findall(r"^def (\w+)", content, re.MULTILINE)

    with open(analysis_file_path, "w", encoding="utf-8") as analysis_file:
        if classes:
            analysis_file.write("Classes:\n")
            analysis_file.writelines(f"{cls}\n" for cls in classes)
        if functions:
            analysis_file.write("\nFunctions:\n")
            analysis_file.writelines(f"{func}\n" for func in functions)

    print(f"Analysis for {base_name} written to {analysis_file_name}")

