"""Validate a commit-message file using the repository's deterministic convention."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Sequence

APPROVED_TYPES: tuple[str, ...] = (
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
)

_TYPE_PATTERN = "|".join(APPROVED_TYPES)
CONVENTIONAL_HEADER = re.compile(
    rf"^(?P<type>{_TYPE_PATTERN})(?:\((?P<scope>[a-z0-9][a-z0-9._/-]*)\))?"
    r"(?P<breaking>!)?: (?P<subject>\S.*)$"
)
GENERATED_PREFIXES = (
    "Merge ",
    'Revert "',
    'Reapply "',
    "fixup! ",
    "squash! ",
    "amend! ",
)


def _meaningful_lines(message: str) -> list[str]:
    return [line.rstrip() for line in message.splitlines() if not line.lstrip().startswith("#")]


def validate_message(message: str) -> list[str]:
    """Return actionable validation errors; an empty list means valid."""
    lines = _meaningful_lines(message)
    while lines and not lines[0]:
        lines.pop(0)
    if not lines:
        return ["Commit message is empty after comments are removed."]

    header = lines[0]
    if header.startswith(GENERATED_PREFIXES):
        return []
    match = CONVENTIONAL_HEADER.fullmatch(header)
    if match is None:
        return [
            "The first line must use '<type>(optional-scope)!: subject'.",
            f"Approved types: {', '.join(APPROVED_TYPES)}.",
            "Examples: 'feat(parser): add JSONL support' and 'fix!: remove unsafe fallback'.",
        ]
    if match.group("subject").endswith("."):
        return ["The commit subject must not end with a period."]
    return []


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message_file", type=Path)
    args = parser.parse_args(argv)
    try:
        message = args.message_file.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Unable to read commit-message file {args.message_file}: {exc}", file=sys.stderr)
        return 2
    errors = validate_message(message)
    if not errors:
        return 0
    print("Invalid commit message:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
