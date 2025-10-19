from __future__ import annotations

from pathlib import Path

import pytest

from zscripts import cli
from zscripts.utils import ensure_writable_path


def test_ensure_writable_path_rejects_non_writable_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "nested" / "output.txt"
    parent = target.parent
    parent.mkdir()

    def fake_access(path: str | Path, mode: int) -> bool:  # pragma: no cover - simple helper
        if Path(path) == parent:
            return False
        return True

    monkeypatch.setattr(
        "zscripts.utils.os.access", fake_access,
    )

    with pytest.raises(PermissionError) as excinfo:
        ensure_writable_path(target)

    assert parent.as_posix() in str(excinfo.value)


def test_ensure_writable_path_rejects_directory_target(tmp_path: Path) -> None:
    target_dir = tmp_path / "logs"
    target_dir.mkdir()

    with pytest.raises(IsADirectoryError):
        ensure_writable_path(target_dir)


def test_ensure_writable_path_allows_existing_writable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "existing.txt"
    target.write_text("hello", encoding="utf-8")

    monkeypatch.setattr("zscripts.utils.os.access", lambda path, mode: True)

    ensure_writable_path(target)

    assert target.exists()


def test_consolidate_errors_when_parent_is_file(
    tmp_path: Path, sample_project_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    parent = tmp_path / "blocked"
    parent.write_text("content", encoding="utf-8")
    target = parent / "output.txt"

    exit_code = cli.main(
        [
            "consolidate",
            "--types",
            "python",
            "--project-root",
            str(sample_project_path),
            "--output",
            str(target),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Cannot create parent directory for output path" in captured.err


def test_tree_errors_when_output_is_directory(
    tmp_path: Path, sample_project_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target_dir = tmp_path / "logs"
    target_dir.mkdir()

    exit_code = cli.main(
        [
            "tree",
            "--project-root",
            str(sample_project_path),
            "--output",
            str(target_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Output path resolves to a directory" in captured.err
