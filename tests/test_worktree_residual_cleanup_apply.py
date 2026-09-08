from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts import worktree_residual_cleanup as cleanup


def _approved_manifest(
    root: Path,
    repo: Path,
    parent: Path,
    entries: list[cleanup.EntryRecord],
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "root": str(root),
        "owned_parent": str(parent),
        "repo": str(repo),
        "protected_roots": [],
        "exists": root.exists(),
        "registered_worktree": False,
        "limits": {"max_entries": 200_000, "max_file_bytes": 1024 * 1024 * 1024},
        "entries": [
            {
                "path": entry.path,
                "kind": entry.kind,
                "size": entry.size,
                "sha256": entry.sha256,
                "target_sha256": entry.target_sha256,
            }
            for entry in entries
        ],
        "approval": {
            "approved": True,
            "created_by_current_slice": True,
            "inactive_confirmed": True,
            "note": "fixture-owned residual",
        },
        "preservation": {"ref": "refs/heads/preserved", "head": "a" * 40},
    }


def _bypass_external_git_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cleanup, "_verify_preservation", lambda _manifest: None)
    monkeypatch.setattr(cleanup, "registered_worktrees", lambda _repo: set())


def test_same_size_changed_content_is_rejected_before_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "owned"
    root = parent / "residual"
    repo = tmp_path / "repo"
    root.mkdir(parents=True)
    repo.mkdir()
    path = root / "file.bin"
    path.write_bytes(b"abcd")
    manifest = _approved_manifest(root, repo, parent, cleanup.scan_entries(str(root)))
    path.write_bytes(b"wxyz")
    _bypass_external_git_gates(monkeypatch)

    with pytest.raises(cleanup.CleanupError, match="do not exactly match"):
        cleanup.apply_manifest(manifest)

    assert path.read_bytes() == b"wxyz"


def test_unknown_file_is_rejected_without_deleting_known_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "owned"
    root = parent / "residual"
    repo = tmp_path / "repo"
    root.mkdir(parents=True)
    repo.mkdir()
    known = root / "known.txt"
    known.write_text("known", encoding="utf-8")
    manifest = _approved_manifest(root, repo, parent, cleanup.scan_entries(str(root)))
    unknown = root / "unknown.txt"
    unknown.write_text("unknown", encoding="utf-8")
    _bypass_external_git_gates(monkeypatch)

    with pytest.raises(cleanup.CleanupError, match="do not exactly match"):
        cleanup.apply_manifest(manifest)

    assert known.exists()
    assert unknown.exists()


def test_still_registered_root_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = tmp_path / "owned"
    root = parent / "residual"
    repo = tmp_path / "repo"
    root.mkdir(parents=True)
    repo.mkdir()
    manifest = _approved_manifest(root, repo, parent, [])
    monkeypatch.setattr(cleanup, "_verify_preservation", lambda _manifest: None)
    monkeypatch.setattr(cleanup, "registered_worktrees", lambda _repo: {cleanup._canonical(str(root))})

    with pytest.raises(cleanup.CleanupError, match="still registered"):
        cleanup.apply_manifest(manifest)

    assert root.exists()


def test_unapproved_or_unowned_manifest_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "owned"
    root = parent / "residual"
    repo = tmp_path / "repo"
    root.mkdir(parents=True)
    repo.mkdir()
    manifest = _approved_manifest(root, repo, parent, [])
    _bypass_external_git_gates(monkeypatch)

    manifest["approval"]["approved"] = False
    with pytest.raises(cleanup.CleanupError, match="not been explicitly approved"):
        cleanup.apply_manifest(manifest)

    manifest["approval"]["approved"] = True
    manifest["approval"]["created_by_current_slice"] = False
    with pytest.raises(cleanup.CleanupError, match="ownership"):
        cleanup.apply_manifest(manifest)


def test_already_absent_root_is_idempotent_after_safety_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "owned"
    root = parent / "residual"
    repo = tmp_path / "repo"
    parent.mkdir()
    repo.mkdir()
    manifest = _approved_manifest(root, repo, parent, [])
    manifest["exists"] = False
    _bypass_external_git_gates(monkeypatch)

    assert cleanup.apply_manifest(manifest) == "already-absent"


def test_empty_existing_root_can_be_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = tmp_path / "owned"
    root = parent / "residual"
    repo = tmp_path / "repo"
    root.mkdir(parents=True)
    repo.mkdir()
    manifest = _approved_manifest(root, repo, parent, [])
    _bypass_external_git_gates(monkeypatch)

    assert cleanup.apply_manifest(manifest) == "removed"
    assert not root.exists()


def test_apply_removes_exact_entries_without_following_external_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "owned"
    root = parent / "residual"
    repo = tmp_path / "repo"
    nested = root / "nested"
    nested.mkdir(parents=True)
    repo.mkdir()
    (root / "one.txt").write_text("one", encoding="utf-8")
    (nested / "two.txt").write_text("two", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    try:
        (root / "outside-link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("host cannot create symlinks")
    manifest = _approved_manifest(root, repo, parent, cleanup.scan_entries(str(root)))
    _bypass_external_git_gates(monkeypatch)

    assert cleanup.apply_manifest(manifest) == "removed"
    assert not root.exists()
    assert marker.read_text(encoding="utf-8") == "keep"


def test_partial_removal_failure_stops_and_leaves_residue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "owned"
    root = parent / "residual"
    repo = tmp_path / "repo"
    root.mkdir(parents=True)
    repo.mkdir()
    first = root / "a.txt"
    second = root / "b.txt"
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    manifest = _approved_manifest(root, repo, parent, cleanup.scan_entries(str(root)))
    _bypass_external_git_gates(monkeypatch)
    real_unlink = os.unlink

    def block_second(path: str) -> None:
        if str(path).endswith("b.txt"):
            raise PermissionError("fixture lock")
        real_unlink(path)

    monkeypatch.setattr(os, "unlink", block_second)
    with pytest.raises(cleanup.CleanupError, match="Removal stopped"):
        cleanup.apply_manifest(manifest)

    assert not first.exists()
    assert second.exists()
    assert root.exists()
    assert cleanup.scan_entries(str(root))[0].path == "b.txt"


def test_manifest_with_git_metadata_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "owned"
    root = parent / "residual"
    repo = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    repo.mkdir()
    manifest = _approved_manifest(root, repo, parent, cleanup.scan_entries(str(root)))
    _bypass_external_git_gates(monkeypatch)

    with pytest.raises(cleanup.CleanupError, match=".git metadata"):
        cleanup.apply_manifest(manifest)

    assert (root / ".git").exists()


def test_preservation_ref_must_match_exact_head(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "fixture@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Fixture"], check=True)
    (repo / "file.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "file.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "-C", str(repo), "branch", "preserved"], check=True)
    manifest = {"repo": str(repo), "preservation": {"ref": "refs/heads/preserved", "head": head}}

    cleanup._verify_preservation(manifest)
    manifest["preservation"]["head"] = "0" * 40
    with pytest.raises(cleanup.CleanupError, match="mismatch"):
        cleanup._verify_preservation(manifest)
