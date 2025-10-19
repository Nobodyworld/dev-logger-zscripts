from __future__ import annotations

from pathlib import Path

import pytest

from zscripts import cli


def test_ensure_output_path_rejects_non_writable_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "nested" / "output.txt"
    parent = target.parent
    parent.mkdir()

    def fake_access(path: str | Path, mode: int) -> bool:  # pragma: no cover - simple helper
        if Path(path) == parent:
            return False
        return True

    monkeypatch.setattr(cli.os, "access", fake_access)

    with pytest.raises(PermissionError) as excinfo:
        cli._ensure_output_path(target)

    assert parent.as_posix() in str(excinfo.value)


def test_ensure_output_path_rejects_directory_target(tmp_path: Path) -> None:
    target_dir = tmp_path / "logs"
    target_dir.mkdir()

    with pytest.raises(IsADirectoryError):
        cli._ensure_output_path(target_dir)


def test_ensure_output_path_allows_existing_writable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "existing.txt"
    target.write_text("hello", encoding="utf-8")

    monkeypatch.setattr(cli.os, "access", lambda path, mode: True)

    cli._ensure_output_path(target)

    assert target.exists()
