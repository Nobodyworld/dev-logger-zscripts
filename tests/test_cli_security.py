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


def test_ensure_writable_path_dry_run_respects_permissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "nested" / "output.txt"

    def fake_access(path: str | Path, mode: int) -> bool:  # pragma: no cover - helper
        if Path(path) == tmp_path:
            return False
        return True

    monkeypatch.setattr("zscripts.utils.os.access", fake_access)

    with pytest.raises(PermissionError) as excinfo:
        ensure_writable_path(target, create_parents=False)

    assert tmp_path.as_posix() in str(excinfo.value)
    assert not (tmp_path / "nested").exists()


def test_ensure_writable_path_allowed_root_blocks_without_creating(
    tmp_path: Path,
) -> None:
    allowed_root = tmp_path / "safe"
    allowed_root.mkdir()
    escape_target = allowed_root / ".." / "evil" / "output.txt"

    with pytest.raises(RuntimeError) as excinfo:
        ensure_writable_path(escape_target, allowed_root=allowed_root)

    assert "escapes the allowed root" in str(excinfo.value)
    assert not (tmp_path / "evil").exists()


def test_ensure_writable_path_rejects_file_allowed_root(tmp_path: Path) -> None:
    allowed_root = tmp_path / "config.json"
    allowed_root.write_text("{}", encoding="utf-8")
    target = tmp_path / "logs" / "output.txt"

    with pytest.raises(NotADirectoryError) as excinfo:
        ensure_writable_path(target, allowed_root=allowed_root)

    assert allowed_root.as_posix() in str(excinfo.value)


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
    assert "is a file" in captured.err


def test_collect_errors_when_output_dir_parent_is_file(
    tmp_path: Path, sample_project_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("content", encoding="utf-8")

    exit_code = cli.main(
        [
            "collect",
            "--types",
            "python",
            "--project-root",
            str(sample_project_path),
            "--output-dir",
            str(blocked),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Allowed root" in captured.err
    assert "is not a directory" in captured.err


def test_collect_dry_run_errors_when_output_dir_parent_is_file(
    tmp_path: Path, sample_project_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("content", encoding="utf-8")

    exit_code = cli.main(
        [
            "collect",
            "--types",
            "python",
            "--project-root",
            str(sample_project_path),
            "--output-dir",
            str(blocked),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Allowed root" in captured.err
    assert "is not a directory" in captured.err


def test_collect_errors_when_output_dir_not_writable(
    tmp_path: Path,
    sample_project_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = tmp_path / "logs"
    blocked.mkdir()

    def fake_access(path: str | Path, mode: int) -> bool:  # pragma: no cover - helper
        if Path(path) == blocked:
            return False
        return True

    monkeypatch.setattr("zscripts.utils.os.access", fake_access)

    exit_code = cli.main(
        [
            "collect",
            "--types",
            "python",
            "--project-root",
            str(sample_project_path),
            "--output-dir",
            str(blocked),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    error_lines = [line for line in captured.err.splitlines() if line.startswith("error:")]
    assert error_lines
    assert error_lines[0].startswith("error: Output directory is not writable")


def test_collect_dry_run_errors_when_output_dir_not_writable(
    tmp_path: Path,
    sample_project_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = tmp_path / "logs"
    blocked.mkdir()

    def fake_access(path: str | Path, mode: int) -> bool:  # pragma: no cover - helper
        if Path(path) == blocked:
            return False
        return True

    monkeypatch.setattr("zscripts.utils.os.access", fake_access)

    exit_code = cli.main(
        [
            "collect",
            "--types",
            "python",
            "--project-root",
            str(sample_project_path),
            "--output-dir",
            str(blocked),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    error_lines = [line for line in captured.err.splitlines() if line.startswith("error:")]
    assert error_lines
    assert error_lines[0].startswith("error: Output directory is not writable")


def test_consolidate_dry_run_errors_when_parent_is_file(
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
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Cannot create parent directory for output path" in captured.err


def test_consolidate_errors_when_output_dir_not_writable(
    tmp_path: Path,
    sample_project_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = tmp_path / "logs"
    blocked.mkdir()
    target = blocked / "output.txt"

    def fake_access(path: str | Path, mode: int) -> bool:  # pragma: no cover - helper
        if Path(path) == blocked:
            return False
        return True

    monkeypatch.setattr("zscripts.utils.os.access", fake_access)

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
    assert exit_code == 3
    error_lines = [line for line in captured.err.splitlines() if line.startswith("error:")]
    assert error_lines
    assert error_lines[0].startswith("error: Output directory is not writable")


def test_consolidate_dry_run_errors_when_output_dir_not_writable(
    tmp_path: Path,
    sample_project_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = tmp_path / "logs"
    blocked.mkdir()
    target = blocked / "output.txt"

    def fake_access(path: str | Path, mode: int) -> bool:  # pragma: no cover - helper
        if Path(path) == blocked:
            return False
        return True

    monkeypatch.setattr("zscripts.utils.os.access", fake_access)

    exit_code = cli.main(
        [
            "consolidate",
            "--types",
            "python",
            "--project-root",
            str(sample_project_path),
            "--output",
            str(target),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    error_lines = [line for line in captured.err.splitlines() if line.startswith("error:")]
    assert error_lines
    assert error_lines[0].startswith("error: Output directory is not writable")


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


def test_tree_dry_run_errors_when_output_is_directory(
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
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Output path resolves to a directory" in captured.err


def test_tree_errors_when_output_dir_not_writable(
    tmp_path: Path,
    sample_project_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = tmp_path / "logs"
    blocked.mkdir()

    def fake_access(path: str | Path, mode: int) -> bool:  # pragma: no cover - helper
        if Path(path) == blocked:
            return False
        return True

    monkeypatch.setattr("zscripts.utils.os.access", fake_access)

    exit_code = cli.main(
        [
            "tree",
            "--project-root",
            str(sample_project_path),
            "--output-dir",
            str(blocked),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    first_line = captured.err.splitlines()[0]
    assert first_line.startswith("error: Output directory is not writable")


def test_tree_dry_run_errors_when_output_dir_not_writable(
    tmp_path: Path,
    sample_project_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = tmp_path / "logs"
    blocked.mkdir()

    def fake_access(path: str | Path, mode: int) -> bool:  # pragma: no cover - helper
        if Path(path) == blocked:
            return False
        return True

    monkeypatch.setattr("zscripts.utils.os.access", fake_access)

    exit_code = cli.main(
        [
            "tree",
            "--project-root",
            str(sample_project_path),
            "--output-dir",
            str(blocked),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    first_line = captured.err.splitlines()[0]
    assert first_line.startswith("error: Output directory is not writable")
