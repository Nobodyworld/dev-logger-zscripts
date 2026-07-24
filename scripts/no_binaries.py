"""Detect files containing NUL bytes (binary markers)."""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IGNORE_DIRS = {
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".pytest-tmp",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "node_modules",
    "venv",
}
IGNORE_ROOT_DIRS = {"artifacts"}
IGNORE_FILES = {".coverage"}


def _should_skip_dir(root: str, dirpath: str) -> bool:
    """Return True when ``dirpath`` belongs to one of the ignored directories."""
    parts = dirpath.split(os.sep)
    if any(part in IGNORE_DIRS for part in parts):
        return True
    rel_parts = os.path.relpath(dirpath, root).split(os.sep)
    return rel_parts[0] in IGNORE_ROOT_DIRS


def _should_skip_file(filename: str) -> bool:
    """Return True when ``filename`` is a generated local artifact."""
    return filename in IGNORE_FILES


def find_binaries(root: str) -> list[str]:
    """Return a list of files under ``root`` containing NUL bytes."""
    binaries: list[str] = []
    for dirpath, _dirs, files in os.walk(root):
        if _should_skip_dir(root, dirpath):
            continue
        for filename in files:
            if _should_skip_file(filename):
                continue
            candidate = os.path.join(dirpath, filename)
            try:
                with open(candidate, "rb") as handle:
                    chunk = handle.read(8192)
            except OSError:
                # Skip unreadable files (e.g. permissions issues).
                continue
            if b"\x00" in chunk:
                binaries.append(os.path.relpath(candidate, root))
    return binaries


def main() -> None:
    binaries = find_binaries(ROOT)
    if binaries:
        print("Detected binary-like files (NUL bytes):")
        for path in binaries:
            print(" -", path)
        print(f"\nFound {len(binaries)} binary-like files.")
        sys.exit(2)
    print("No binary-like files detected.")


if __name__ == "__main__":
    main()
