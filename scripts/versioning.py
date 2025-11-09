"""Small helpers for bumping versions and updating the changelog."""

from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"


def load_version() -> str:
    content = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version = "(?P<version>\d+\.\d+\.\d+)"', content, re.MULTILINE)
    if not match:  # pragma: no cover - configuration error
        raise ValueError("Unable to locate version in pyproject.toml")
    return match.group("version")


def write_version(new_version: str) -> None:
    content = PYPROJECT.read_text(encoding="utf-8")
    updated = re.sub(
        r'^(version = ")(?P<version>\d+\.\d+\.\d+)(")',
        rf"\1{new_version}\3",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    PYPROJECT.write_text(updated, encoding="utf-8")


def bump(part: str) -> str:
    major, minor, patch = (int(part_) for part_ in load_version().split("."))
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:  # pragma: no cover - argparse guards
        raise ValueError(f"Unknown bump part: {part}")
    new_version = f"{major}.{minor}.{patch}"
    write_version(new_version)
    return new_version


def add_changelog_entry(message: str, section: str) -> None:
    lines = CHANGELOG.read_text(encoding="utf-8").splitlines()
    try:
        unreleased_index = lines.index("## Unreleased")
    except ValueError as err:  # pragma: no cover - configuration error
        raise ValueError("CHANGELOG.md must contain a '## Unreleased' section") from err

    header = f"### {section.capitalize()}"
    section_index = None
    for idx in range(unreleased_index + 1, len(lines)):
        line = lines[idx]
        if line.startswith("## "):
            break
        if line.strip() == header:
            section_index = idx
            break

    if section_index is None:
        insert_at = unreleased_index + 1
        lines.insert(insert_at, header)
        section_index = insert_at
        lines.insert(section_index + 1, f"- {message}")
    else:
        insert_at = section_index + 1
        while insert_at < len(lines) and lines[insert_at].startswith("- "):
            insert_at += 1
        lines.insert(insert_at, f"- {message}")

    CHANGELOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def stamp_release(version: str) -> None:
    today = dt.date.today().isoformat()
    lines = CHANGELOG.read_text(encoding="utf-8").splitlines()
    try:
        unreleased_index = lines.index("## Unreleased")
    except ValueError as err:  # pragma: no cover - configuration error
        raise ValueError("CHANGELOG.md must contain a '## Unreleased' section") from err
    release_header = f"## v{version} - {today}"
    lines.insert(unreleased_index + 1, "")
    lines.insert(unreleased_index + 2, release_header)
    CHANGELOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    bump_parser = subparsers.add_parser("bump", help="Bump the semantic version")
    bump_parser.add_argument("part", choices=["major", "minor", "patch"])

    change_parser = subparsers.add_parser("changelog", help="Add an entry to the changelog")
    change_parser.add_argument("message", help="Bullet message to add under Unreleased")
    change_parser.add_argument(
        "--section",
        default="Added",
        choices=["Added", "Changed", "Fixed", "Removed"],
        help="Changelog subsection to target",
    )

    stamp_parser = subparsers.add_parser(
        "stamp", help="Create a dated release header from the Unreleased section"
    )
    stamp_parser.add_argument("version", help="Version string for the release header")

    args = parser.parse_args(argv)

    if args.command == "bump":
        new_version = bump(args.part)
        print(f"Version bumped to {new_version}")
        return 0
    if args.command == "changelog":
        add_changelog_entry(args.message, args.section)
        print(f"Added changelog entry under {args.section}")
        return 0
    if args.command == "stamp":
        stamp_release(args.version)
        print(f"Stamped changelog with v{args.version}")
        return 0
    return 1  # pragma: no cover - unreachable


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

