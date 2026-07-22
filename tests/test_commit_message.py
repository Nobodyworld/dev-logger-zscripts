from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.validate_commit_message import validate_message


@pytest.mark.parametrize(
    "message",
    [
        "feat: add JSONL parsing",
        "fix(parser): handle an empty stream",
        "feat(api)!: remove the legacy field\n\nBREAKING CHANGE: use the new field",
        "revert: restore stable parsing",
        'Merge branch "main" into feature',
        'Revert "feat: add JSONL parsing"',
        "squash! feat: add JSONL parsing",
        "# template comment\n\nchore: refresh contributor docs\n",
    ],
)
def test_valid_commit_messages_are_accepted(message: str) -> None:
    assert validate_message(message) == []


@pytest.mark.parametrize(
    "message",
    [
        "",
        "Add JSONL parsing",
        "feature: add JSONL parsing",
        "feat(): add JSONL parsing",
        "feat(Parser): add JSONL parsing",
        "feat: add JSONL parsing.",
        "feat:",
    ],
)
def test_invalid_commit_messages_are_rejected(message: str) -> None:
    assert validate_message(message)


def test_commit_message_cli_reports_actionable_error(tmp_path: Path) -> None:
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text("not conventional\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "scripts/validate_commit_message.py", str(message_file)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Approved types" in result.stderr
    assert "feat(parser): add JSONL support" in result.stderr
