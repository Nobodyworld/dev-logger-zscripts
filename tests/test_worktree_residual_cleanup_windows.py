from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts import worktree_residual_cleanup as cleanup

pytestmark = pytest.mark.skipif(os.name != "nt", reason="native Windows cleanup fixture")


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
        "exists": True,
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
            "note": "native Windows junction fixture",
        },
        "preservation": {"ref": "refs/heads/preserved", "head": "a" * 40},
    }


def test_apply_removes_junction_itself_without_traversing_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "owned"
    root = parent / "residual"
    outside = tmp_path / "outside"
    repo = tmp_path / "repo"
    root.mkdir(parents=True)
    outside.mkdir()
    repo.mkdir()
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

    manifest = _approved_manifest(root, repo, parent, cleanup.scan_entries(str(root)))
    monkeypatch.setattr(cleanup, "_verify_preservation", lambda _manifest: None)
    monkeypatch.setattr(cleanup, "registered_worktrees", lambda _repo: set())

    assert cleanup.apply_manifest(manifest) == "removed"
    assert not root.exists()
    assert marker.read_text(encoding="utf-8") == "keep"
