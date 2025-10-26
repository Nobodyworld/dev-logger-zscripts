"""Bump the project version and print git tagging instructions."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for <3.11
    import tomli as tomllib  # type: ignore[no-redef]

PYPROJECT_PATH = Path("pyproject.toml")
VERSION_PATTERN = re.compile(r"^version\s*=\s*\"(?P<version>\d+\.\d+\.\d+)\"\s*$", re.MULTILINE)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bump",
        choices=["major", "minor", "patch"],
        default="patch",
        help="Semantic version component to increment (default: patch).",
    )
    parser.add_argument(
        "--tag",
        action="store_true",
        help="Create a git tag after bumping the version.",
    )
    return parser.parse_args(argv)


def load_version() -> str:
    payload = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    return str(payload["project"]["version"])


def write_version(current: str, new_version: str) -> None:
    contents = PYPROJECT_PATH.read_text(encoding="utf-8")
    updated = VERSION_PATTERN.sub(f'version = "{new_version}"', contents)
    if contents == updated:
        raise RuntimeError("Failed to update version string in pyproject.toml")
    PYPROJECT_PATH.write_text(updated, encoding="utf-8")


def bump_version(version: str, bump: str) -> str:
    major, minor, patch = [int(piece) for piece in version.split(".")]
    if bump == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def create_git_tag(version: str) -> None:
    tag_name = f"v{version}"
    subprocess.check_call(["git", "tag", tag_name])
    print(f"Created git tag {tag_name}. Push with: git push origin {tag_name}")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    current = load_version()
    new_version = bump_version(current, args.bump)
    write_version(current, new_version)
    print(f"Version bumped from {current} to {new_version}.")
    print("Update CHANGELOG.md and RELEASE_NOTES.md before committing.")
    if args.tag:
        create_git_tag(new_version)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
