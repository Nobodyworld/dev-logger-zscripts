from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from zscripts.infrastructure.repository_discovery import RepositoryDiscovery


def _git_root(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    (root / "package").mkdir()
    (root / "package" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    return root


def test_resolve_scope_reports_nested_git_root_without_discovery(tmp_path: Path) -> None:
    root = _git_root(tmp_path)
    nested = root / "package"
    discovery = RepositoryDiscovery()

    scope = discovery.resolve_scope(nested)

    assert scope.presentation_version == "1"
    assert scope.resolved_input_path == str(nested.resolve())
    assert scope.analysis_root == str(root.resolve())
    assert scope.git_root_detected is True
    assert scope.confirmation_required is True
    assert scope.reason == "enclosing-git-root"


def test_resolve_scope_keeps_same_root_and_non_git_one_action(tmp_path: Path) -> None:
    root = _git_root(tmp_path)
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()
    discovery = RepositoryDiscovery()

    same_root = discovery.resolve_scope(root)
    non_git = discovery.resolve_scope(ordinary)

    assert (same_root.analysis_root, same_root.git_root_detected, same_root.confirmation_required) == (
        str(root.resolve()),
        True,
        False,
    )
    assert same_root.reason == "same-directory"
    assert (non_git.analysis_root, non_git.git_root_detected, non_git.confirmation_required) == (
        str(ordinary.resolve()),
        False,
        False,
    )
    assert non_git.reason == "non-git-directory"


def test_resolve_scope_recognizes_git_file_and_canonical_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "linked-worktree"
    nested = root / "src" / "feature"
    nested.mkdir(parents=True)
    (root / ".git").write_text("gitdir: /private/worktrees/example\n", encoding="utf-8")
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(nested, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable on this platform.")
    monkeypatch.chdir(tmp_path)

    scope = RepositoryDiscovery().resolve_scope(Path("alias/../alias"))

    assert scope.resolved_input_path == str(nested.resolve())
    assert scope.analysis_root == str(root.resolve())
    assert scope.reason == "enclosing-git-root"
    assert scope.confirmation_required is True


def test_resolve_scope_rejects_missing_and_non_directory_paths(tmp_path: Path) -> None:
    file_path = tmp_path / "file.py"
    file_path.write_text("VALUE = 1\n", encoding="utf-8")
    discovery = RepositoryDiscovery()

    with pytest.raises(ValueError, match="Repository path"):
        discovery.resolve_scope(tmp_path / "missing")
    with pytest.raises(ValueError, match="Repository path"):
        discovery.resolve_scope(file_path)


def test_resolve_scope_does_not_enumerate_or_read_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _git_root(tmp_path)
    nested = root / "package"
    discovery = RepositoryDiscovery()

    monkeypatch.setattr(discovery, "_git_candidates", lambda _: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(discovery, "_walk_candidates", lambda _: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        discovery, "_load_gitignore_patterns", lambda _: (_ for _ in ()).throw(AssertionError())
    )
    monkeypatch.setattr(Path, "read_bytes", lambda _: (_ for _ in ()).throw(AssertionError()))

    scope = discovery.resolve_scope(nested)

    assert scope.analysis_root == str(root.resolve())


def test_discover_reuses_scope_analysis_root(tmp_path: Path) -> None:
    root = _git_root(tmp_path)
    nested = root / "package"
    discovery = RepositoryDiscovery()

    scope = discovery.resolve_scope(nested)
    result = discovery.discover(nested)

    assert result.repository.canonical_path == scope.analysis_root
    assert result.repository.git_root == scope.analysis_root
    assert {item.record.relative_path for item in result.files} == {"package/module.py"}


@pytest.mark.skipif(os.name == "nt", reason="Windows home expansion follows profile configuration.")
def test_resolve_scope_expands_home_directory() -> None:
    scope = RepositoryDiscovery().resolve_scope(Path("~"))

    assert scope.resolved_input_path == str(Path.home().resolve())
