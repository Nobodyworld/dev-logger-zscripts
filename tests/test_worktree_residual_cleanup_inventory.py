from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from scripts import worktree_residual_cleanup as cleanup


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_inventory_is_non_mutating_and_hashes_raw_crlf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "owned"
    root = parent / "residual"
    repo = tmp_path / "repo"
    root.mkdir(parents=True)
    repo.mkdir()
    content = b"line1\r\nline2\r\n"
    path = root / "file.txt"
    path.write_bytes(content)
    before = path.read_bytes()
    monkeypatch.setattr(cleanup, "registered_worktrees", lambda _repo: set())

    payload = cleanup.build_inventory(str(root), repo=str(repo), owned_parent=str(parent))

    assert payload["approval"]["approved"] is False
    assert payload["entries"] == [
        {
            "path": "file.txt",
            "kind": "file",
            "size": len(content),
            "sha256": _sha(content),
            "target_sha256": None,
        }
    ]
    assert path.read_bytes() == before


def test_inventory_records_empty_directory(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "empty").mkdir(parents=True)

    assert cleanup.scan_entries(str(root)) == [
        cleanup.EntryRecord(path="empty", kind="directory")
    ]


def test_inventory_does_not_follow_internal_external_or_broken_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    marker = outside / "secret.txt"
    marker.write_text("secret", encoding="utf-8")
    (root / "inside.txt").write_text("inside", encoding="utf-8")
    try:
        (root / "internal").symlink_to(root / "inside.txt")
        (root / "external").symlink_to(outside, target_is_directory=True)
        (root / "broken").symlink_to(root / "missing")
    except OSError:
        pytest.skip("host cannot create symlinks")

    records = cleanup.scan_entries(str(root))

    assert {record.path for record in records} == {
        "broken",
        "external",
        "inside.txt",
        "internal",
    }
    assert all(record.kind == "reparse" for record in records if record.path != "inside.txt")
    assert marker.read_text(encoding="utf-8") == "secret"


def test_inventory_supports_long_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = tmp_path / "owned"
    root = parent / "residual"
    repo = tmp_path / "repo"
    current = root
    for index in range(9):
        current = current / (f"segment-{index}-" + "x" * 24)
    current.mkdir(parents=True)
    leaf = current / "payload.txt"
    leaf.write_text("long-path", encoding="utf-8")
    repo.mkdir()
    monkeypatch.setattr(cleanup, "registered_worktrees", lambda _repo: set())

    payload = cleanup.build_inventory(str(root), repo=str(repo), owned_parent=str(parent))

    assert any(entry["path"].endswith("payload.txt") for entry in payload["entries"])
    assert leaf.read_text(encoding="utf-8") == "long-path"


def test_protected_overlap_is_rejected(tmp_path: Path) -> None:
    parent = tmp_path / "owned"
    root = parent / "residual"
    protected_child = root / "protected"

    with pytest.raises(cleanup.CleanupError, match="overlaps"):
        cleanup._assert_no_overlap(str(root), str(parent), [str(protected_child)])
    with pytest.raises(cleanup.CleanupError, match="overlaps"):
        cleanup._assert_no_overlap(str(protected_child), str(parent), [str(root)])


def test_registered_worktree_parser_uses_porcelain_z(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    worktree = tmp_path / "worktree"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "fixture@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Fixture"], check=True)
    (repo / "file.txt").write_text("fixture", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "file.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b", "fixture-worktree", str(worktree)], check=True)

    registered = cleanup.registered_worktrees(str(repo))

    assert cleanup._canonical(str(repo)) in registered
    assert cleanup._canonical(str(worktree)) in registered


@pytest.mark.skipif(os.name != "nt", reason="Windows junction fixture")
def test_windows_junction_is_recorded_without_traversal(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    junction = root / "junction"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        pytest.skip(f"junction creation unavailable: {result.stderr or result.stdout}")

    records = cleanup.scan_entries(str(root))

    assert len(records) == 1
    assert records[0].path == "junction"
    assert records[0].kind == "reparse"
    assert marker.read_text(encoding="utf-8") == "keep"
