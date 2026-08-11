from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

import pytest

from scripts import evaluate_repository_review as evaluation_harness
from scripts.evaluate_repository_review import (
    EVALUATION_OUTPUT_FORMAT_VERSION,
    INTEGRITY_MANIFEST_FORMAT_VERSION,
    IntegrityLimits,
    _build_integrity_manifest,
    _canonical_manifest_bytes,
    _integrity_manifests_equal,
    _validated_relative_path,
    evaluate_subjects,
    generate_public_fixtures,
    main,
)
from zscripts.domain.repository_review import ScanLimits

_ALLOWED_FINDING_FAMILIES = {
    "complexity",
    "coupling",
    "dependency-cycle",
    "documentation",
    "duplicate-name-candidate",
    "inheritance",
    "inheritance-cycle",
    "nesting",
    "orphan-candidate",
    "oversized",
    "parameters",
    "test-evidence-candidate",
}
_ALLOWED_SAMPLE_CLASSIFICATIONS = {
    "false-positive",
    "intentional-design",
    "unsupported-ambiguous",
    "useful-actionable",
    "valid-low-priority",
}
_ALLOWED_SAMPLE_SUBJECT_TYPES = {"cycle", "module", "symbol", "symbol-group"}
_REPORT_FAMILY_NAMES = {
    "Complexity": "complexity",
    "Coupling": "coupling",
    "Dependency cycle": "dependency-cycle",
    "Documentation": "documentation",
    "Duplicate name candidate": "duplicate-name-candidate",
    "Duplicate-name candidate": "duplicate-name-candidate",
    "Inheritance cycle": "inheritance-cycle",
    "Inheritance depth": "inheritance",
    "Nesting": "nesting",
    "Orphan candidate": "orphan-candidate",
    "Oversized": "oversized",
    "Parameters": "parameters",
    "Test-evidence candidate": "test-evidence-candidate",
}


def test_evaluation_is_sanitized_deterministic_and_bounded(tmp_path: Path) -> None:
    repository = tmp_path / "subject"
    repository.mkdir()
    (repository / "sample.py").write_text(
        "class Customer:\n    pass\n\ndef process(value: Customer) -> Customer:\n    return value\n",
        encoding="utf-8",
    )
    output = tmp_path / "external" / "result.json"
    payload = evaluate_subjects(
        (("public-sample", repository),),
        output_path=output,
        data_directory=tmp_path / "data",
        repeats=2,
        limits=ScanLimits(),
    )

    serialized = output.read_text(encoding="utf-8")
    subject = payload["subjects"][0]
    assert payload["format_version"] == EVALUATION_OUTPUT_FORMAT_VERSION == 2
    assert payload["integrity_manifest_format_version"] == INTEGRITY_MANIFEST_FORMAT_VERSION == 1
    assert str(repository.resolve()) not in serialized
    assert subject["label"] == "public-sample"
    assert subject["persistence"]["repeated_snapshot_identity_equal"] is True
    assert subject["persistence"]["repeated_canonical_bytes_equal"] is True
    assert subject["persistence"]["repository_bytes_unchanged"] is True
    assert subject["integrity"]["format_version"] == 1
    assert subject["integrity"]["mode"] == "filesystem"
    assert subject["integrity"]["complete"] is True
    assert subject["integrity"]["equal"] is True
    assert subject["integrity"]["inclusion_metadata_equal"] is True
    assert subject["integrity"]["failure_reason"] is None
    assert subject["integrity"]["limits"]["maximum_path_entries"] == 50_000
    assert subject["relationships"]["largest_bounded_graph"]["nodes"] <= 40
    assert subject["relationships"]["largest_bounded_graph"]["relationships"] <= 80
    assert subject["findings"]["bounded_review_sample_size"] <= 20
    assert subject["comparison"]["equal_snapshots"] is True
    assert subject["handoff"]["saved_reopened_integrity"] is True


def test_evaluation_respects_scan_limits_without_path_leakage(tmp_path: Path) -> None:
    repository = tmp_path / "bounded"
    repository.mkdir()
    for index in range(4):
        (repository / f"module_{index}.py").write_text(
            f"def item_{index}():\n    return {index}\n",
            encoding="utf-8",
        )
    output = tmp_path / "result.json"
    payload = evaluate_subjects(
        (("public-bounded", repository),),
        output_path=output,
        data_directory=tmp_path / "data",
        repeats=2,
        limits=ScanLimits(max_files=1),
    )

    scan = payload["subjects"][0]["scan"]
    assert scan["truncated"] is True
    assert scan["files_analyzed"] == 1
    assert str(repository.resolve()) not in json.dumps(payload)


@pytest.mark.parametrize("destination", ("output", "data"))
def test_evaluation_rejects_repository_internal_writes(
    tmp_path: Path,
    destination: str,
) -> None:
    repository = tmp_path / "subject"
    repository.mkdir()
    (repository / "sample.py").write_text("value = 1\n", encoding="utf-8")
    output = repository / "result.json" if destination == "output" else tmp_path / "result.json"
    data = repository / "data" if destination == "data" else tmp_path / "data"

    with pytest.raises(ValueError, match="outside every analyzed repository"):
        evaluate_subjects(
            (("public-sample", repository),),
            output_path=output,
            data_directory=data,
            repeats=2,
            limits=ScanLimits(),
        )
    assert not output.exists()


def test_public_fixture_generation_is_deterministic(tmp_path: Path) -> None:
    first = generate_public_fixtures(tmp_path / "first")
    second = generate_public_fixtures(tmp_path / "second")

    assert [label for label, _ in first] == [label for label, _ in second]
    assert _fixture_digest(first) == _fixture_digest(second)
    large = dict(first)["public-large"]
    assert (large / ".gitignore").read_text(encoding="utf-8") == "generated/\n"
    assert len(list((large / "generated").glob("*.py"))) == 200


def test_cli_requires_explicit_output_and_uses_anonymous_label(tmp_path: Path) -> None:
    repository = tmp_path / "subject"
    repository.mkdir()
    (repository / "sample.py").write_text("value = 1\n", encoding="utf-8")
    output = tmp_path / "result.json"

    result = main(
        [
            "evaluate",
            "--subject",
            f"public-sample={repository}",
            "--output",
            str(output),
            "--data-directory",
            str(tmp_path / "data"),
        ]
    )

    assert result == 0
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8"))["sanitized"] is True


def test_git_integrity_manifest_includes_public_bytes_and_excludes_local_state(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "git-subject"
    repository.mkdir()
    _git(repository, "init")
    (repository / ".gitignore").write_text("ignored/\ntracked-ignored.bin\n", encoding="utf-8")
    (repository / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    (repository / "tracked.bin").write_bytes(b"\x00\xff\x10")
    (repository / "tracked-ignored.bin").write_bytes(b"tracked despite ignore")
    _git(repository, "add", ".gitignore", "tracked.txt", "tracked.bin")
    _git(repository, "add", "-f", "tracked-ignored.bin")
    (repository / "untracked.txt").write_text("untracked\n", encoding="utf-8")
    ignored = repository / "ignored"
    ignored.mkdir()
    (ignored / "owner.txt").write_text("owner local\n", encoding="utf-8")
    environment = repository / ".venv"
    environment.mkdir()
    (environment / "unignored.bin").write_bytes(b"owner environment")

    baseline = _build_integrity_manifest(repository)
    included = {entry.relative_path for entry in baseline.entries}
    assert baseline.complete is True
    assert baseline.mode == "git"
    assert {
        ".gitignore",
        "tracked.txt",
        "tracked.bin",
        "tracked-ignored.bin",
        "untracked.txt",
    } <= included
    assert "ignored/owner.txt" not in included
    assert ".venv/unignored.bin" not in included
    assert baseline.exclusion_counts_dict()["gitignored"] >= 1
    assert baseline.exclusion_counts_dict()["default-environment-or-cache"] >= 1

    (repository / "tracked.bin").write_bytes(b"\x00\xff\x11")
    changed = _build_integrity_manifest(repository)
    assert changed.digest != baseline.digest
    (repository / "tracked.bin").write_bytes(b"\x00\xff\x10")
    assert _build_integrity_manifest(repository).digest == baseline.digest

    (ignored / "owner.txt").write_text("changed ignored bytes\n", encoding="utf-8")
    (environment / "unignored.bin").write_bytes(b"changed owner environment")
    assert _build_integrity_manifest(repository).digest == baseline.digest

    added = repository / "added.txt"
    added.write_text("new included file\n", encoding="utf-8")
    assert _build_integrity_manifest(repository).digest != baseline.digest
    added.unlink()
    assert _build_integrity_manifest(repository).digest == baseline.digest


def test_git_integrity_nested_input_uses_root_and_fixed_no_shell_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "git-subject"
    nested = repository / "nested" / "deeper"
    nested.mkdir(parents=True)
    _git(repository, "init")
    (repository / "root.txt").write_text("root\n", encoding="utf-8")
    _git(repository, "add", "root.txt")
    observed: list[tuple[list[str], bool]] = []
    original_popen = evaluation_harness.subprocess.Popen

    def recording_popen(command: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
        observed.append((command, bool(kwargs.get("shell"))))
        return original_popen(command, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(evaluation_harness.subprocess, "Popen", recording_popen)
    manifest = _build_integrity_manifest(nested)

    assert manifest.complete is True
    assert manifest.mode == "git"
    assert {entry.relative_path for entry in manifest.entries} == {"root.txt"}
    assert len(observed) == 2
    assert all(shell is False for _, shell in observed)
    assert all(command[0] == "git" and "ls-files" in command for command, _ in observed)
    assert all(str(repository.resolve()) in command for command, _ in observed)
    assert all("--cached" in command or "--ignored" in command for command, _ in observed)


@pytest.mark.skipif(
    os.name == "nt",
    reason="Windows lacks descriptor-relative readlink; the manifest fails closed instead",
)
def test_non_git_manifest_is_deterministic_binary_and_symlink_safe(tmp_path: Path) -> None:
    repository = tmp_path / "plain"
    repository.mkdir()
    (repository / "z.txt").write_text("last\n", encoding="utf-8")
    (repository / "a.bin").write_bytes(b"\x00\xfe\x80")
    cache = repository / ".pytest_cache"
    cache.mkdir()
    (cache / "not-read.bin").write_bytes(b"cache")
    generated = repository / "build"
    generated.mkdir()
    (generated / "not-read.bin").write_bytes(b"build")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside secret\n", encoding="utf-8")
    try:
        os.symlink(outside, repository / "outside-link")
        os.symlink(cache, repository / "directory-link", target_is_directory=True)
    except OSError:
        pytest.skip("This host does not permit test symlink creation.")

    first = _build_integrity_manifest(repository)
    second = _build_integrity_manifest(repository)
    entries = {entry.relative_path: entry for entry in first.entries}

    assert first.complete is True
    assert first.mode == "filesystem"
    assert first.digest == second.digest
    assert _canonical_manifest_bytes(first.mode, first.entries) == _canonical_manifest_bytes(
        second.mode, second.entries
    )
    assert list(entries) == sorted(entries, key=lambda item: item.encode("utf-8"))
    assert entries["a.bin"].entry_type == "regular"
    assert entries["outside-link"].entry_type == "symlink"
    assert (
        entries["outside-link"].content_digest
        == hashlib.sha256(os.readlink(repository / "outside-link").encode("utf-8")).hexdigest()
    )
    assert entries["directory-link"].entry_type == "symlink"
    assert all("\\" not in entry.relative_path for entry in first.entries)
    assert first.exclusion_counts_dict()["default-environment-or-cache"] == 2


@pytest.mark.skipif(
    os.name == "nt",
    reason="Windows lacks descriptor-relative readlink; the manifest fails closed instead",
)
def test_stable_nested_symlink_hashes_target_text_without_following(tmp_path: Path) -> None:
    repository = tmp_path / "plain"
    nested = repository / "nested"
    nested.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside secret\n", encoding="utf-8")
    link = nested / "link"
    link.symlink_to(outside)

    manifest = _build_integrity_manifest(repository)
    entries = {entry.relative_path: entry for entry in manifest.entries}

    assert manifest.complete is True
    assert entries["nested/link"].entry_type == "symlink"
    assert (
        entries["nested/link"].content_digest == hashlib.sha256(os.readlink(link).encode("utf-8")).hexdigest()
    )


def test_excluded_directories_are_pruned_without_opening_contents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "plain"
    repository.mkdir()
    (repository / ".gitignore").write_text("ignored-cache/\n", encoding="utf-8")
    (repository / "included.txt").write_text("included\n", encoding="utf-8")
    excluded_roots = [repository / ".venv", repository / "ignored-cache"]
    for excluded_root in excluded_roots:
        excluded_root.mkdir()
        for index in range(200):
            (excluded_root / f"owner-{index:03d}.bin").write_bytes(b"owner local")
    opened: list[Path] = []
    original_open = Path.open

    def recording_open(path: Path, *args: object, **kwargs: object):
        opened.append(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", recording_open)
    started = evaluation_harness.time.perf_counter()
    manifest = _build_integrity_manifest(repository)
    elapsed_ms = (evaluation_harness.time.perf_counter() - started) * 1_000

    assert manifest.complete is True
    assert {entry.relative_path for entry in manifest.entries} == {".gitignore", "included.txt"}
    assert not any(path.is_relative_to(excluded_root) for path in opened for excluded_root in excluded_roots)
    assert manifest.exclusion_counts_dict() == {
        "default-environment-or-cache": 1,
        "gitignored": 1,
    }
    assert elapsed_ms >= 0


def test_non_git_ignored_root_entries_obey_encountered_entry_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "plain"
    repository.mkdir()
    (repository / ".gitignore").write_text("ignored-*.bin\n", encoding="utf-8")
    for index in range(8):
        (repository / f"ignored-{index}.bin").write_bytes(b"owner local")
    opened: list[Path] = []

    original_open = evaluation_harness._open_regular_file_without_following

    def bounded_open(
        trusted_root: object,
        relative: str,
        metadata: os.stat_result,
    ) -> int:
        opened.append(repository / relative)
        return original_open(trusted_root, relative, metadata)  # type: ignore[arg-type]

    monkeypatch.setattr(evaluation_harness, "_open_regular_file_without_following", bounded_open)
    manifest = _build_integrity_manifest(
        repository,
        limits=IntegrityLimits(maximum_path_entries=5),
    )

    assert manifest.complete is False
    assert manifest.digest is None
    assert manifest.failure_reason == "maximum-path-entries-exceeded"
    assert opened == []


def test_non_git_default_excluded_entries_count_without_opening(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "plain"
    repository.mkdir()
    excluded_names = sorted(
        name for name in evaluation_harness.DEFAULT_EXCLUDED_DIRECTORIES if name != ".git"
    )[:4]
    for name in excluded_names:
        excluded = repository / name
        excluded.mkdir()
        (excluded / "not-opened.bin").write_bytes(b"owner local")
    opened: list[Path] = []
    original_open = evaluation_harness._open_regular_file_without_following

    def bounded_open(
        trusted_root: object,
        relative: str,
        metadata: os.stat_result,
    ) -> int:
        opened.append(repository / relative)
        return original_open(trusted_root, relative, metadata)  # type: ignore[arg-type]

    monkeypatch.setattr(evaluation_harness, "_open_regular_file_without_following", bounded_open)
    manifest = _build_integrity_manifest(
        repository,
        limits=IntegrityLimits(maximum_path_entries=3),
    )

    assert manifest.complete is False
    assert manifest.failure_reason == "maximum-path-entries-exceeded"
    assert opened == []


def test_empty_directories_do_not_create_manifest_entries(tmp_path: Path) -> None:
    repository = tmp_path / "plain"
    repository.mkdir()
    (repository / "empty").mkdir()

    manifest = _build_integrity_manifest(repository)

    assert manifest.complete is True
    assert manifest.entries == ()


def test_ancestor_symlink_replacement_before_regular_open_fails_without_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "plain"
    nested = repository / "dir"
    nested.mkdir(parents=True)
    (nested / "file.py").write_text("inside\n", encoding="utf-8")
    external = tmp_path / "external"
    external.mkdir()
    (external / "file.py").write_text("outside secret\n", encoding="utf-8")
    original_open = evaluation_harness._open_regular_file_without_following
    digest_calls = 0
    original_digest = evaluation_harness._stream_digest

    def replacing_open(
        trusted_root: object,
        relative: str,
        metadata: os.stat_result,
    ) -> int:
        if relative == "dir/file.py" and not nested.is_symlink():
            backup = repository / "dir-backup"
            nested.rename(backup)
            try:
                nested.symlink_to(external, target_is_directory=True)
            except OSError:
                backup.rename(nested)
                pytest.skip("This host does not permit the ancestor-symlink race fixture.")
        return original_open(trusted_root, relative, metadata)  # type: ignore[arg-type]

    def recording_digest(stream: object, expected_size: int) -> tuple[str, int]:
        nonlocal digest_calls
        digest_calls += 1
        return original_digest(stream, expected_size)  # type: ignore[arg-type]

    monkeypatch.setattr(
        evaluation_harness,
        "_open_regular_file_without_following",
        replacing_open,
    )
    monkeypatch.setattr(evaluation_harness, "_stream_digest", recording_digest)
    manifest = _build_integrity_manifest(repository)

    assert manifest.complete is False
    assert manifest.digest is None
    assert digest_calls == 0


def test_ancestor_symlink_replacement_before_metadata_cannot_read_external_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "plain"
    nested = repository / "dir"
    nested.mkdir(parents=True)
    (nested / "file.py").write_text("inside\n", encoding="utf-8")
    external = tmp_path / "external"
    external.mkdir()
    target = tmp_path / "outside-secret.txt"
    target.write_text("outside secret\n", encoding="utf-8")
    try:
        (external / "file.py").symlink_to(target)
    except OSError:
        pytest.skip("This host does not permit the ancestor-symlink race fixture.")
    original_lstat = evaluation_harness._TrustedRoot.lstat
    original_readlink = evaluation_harness._TrustedRoot.readlink
    readlink_calls = 0

    def replacing_lstat(trusted_root: object, relative: str) -> os.stat_result:
        if relative == "dir/file.py" and not nested.is_symlink():
            nested.rename(repository / "dir-backup")
            nested.symlink_to(external, target_is_directory=True)
        return original_lstat(trusted_root, relative)  # type: ignore[arg-type]

    def recording_readlink(trusted_root: object, relative: str) -> str:
        nonlocal readlink_calls
        readlink_calls += 1
        return original_readlink(trusted_root, relative)  # type: ignore[arg-type]

    monkeypatch.setattr(evaluation_harness._TrustedRoot, "lstat", replacing_lstat)
    monkeypatch.setattr(evaluation_harness._TrustedRoot, "readlink", recording_readlink)
    manifest = _build_integrity_manifest(repository)

    assert manifest.complete is False
    assert manifest.digest is None
    assert readlink_calls == 0


def test_queued_directory_symlink_replacement_is_not_enumerated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "plain"
    queued = repository / "queued"
    queued.mkdir(parents=True)
    (queued / "inside.txt").write_text("inside\n", encoding="utf-8")
    external = tmp_path / "external"
    external.mkdir()
    (external / "outside.txt").write_text("outside secret\n", encoding="utf-8")
    original_scandir = evaluation_harness._TrustedRoot.scandir
    original_os_scandir = evaluation_harness.os.scandir
    scandir_calls: list[object] = []

    def recording_os_scandir(path: object):
        scandir_calls.append(path)
        return original_os_scandir(path)  # type: ignore[arg-type]

    @contextmanager
    def replacing_scandir(
        trusted_root: object,
        relative: str,
        expected: os.stat_result | None = None,
    ):
        if relative == "queued" and not queued.is_symlink():
            backup = repository / "queued-backup"
            queued.rename(backup)
            try:
                queued.symlink_to(external, target_is_directory=True)
            except OSError:
                backup.rename(queued)
                pytest.skip("This host does not permit the queued-symlink race fixture.")
        with original_scandir(trusted_root, relative, expected) as entries:  # type: ignore[arg-type]
            yield entries

    monkeypatch.setattr(evaluation_harness._TrustedRoot, "scandir", replacing_scandir)
    monkeypatch.setattr(evaluation_harness.os, "scandir", recording_os_scandir)
    manifest = _build_integrity_manifest(repository)

    assert manifest.complete is False
    assert manifest.digest is None
    assert "outside.txt" not in {entry.relative_path for entry in manifest.entries}
    assert len(scandir_calls) == 1


def test_queued_directory_regular_replacement_fails_identity_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "plain"
    queued = repository / "queued"
    queued.mkdir(parents=True)
    (queued / "inside.txt").write_text("inside\n", encoding="utf-8")
    replacement = repository / "replacement"
    replacement.mkdir()
    (replacement / "replacement.txt").write_text("replacement\n", encoding="utf-8")
    original_scandir = evaluation_harness._TrustedRoot.scandir
    original_os_scandir = evaluation_harness.os.scandir
    scandir_calls: list[object] = []

    def recording_os_scandir(path: object):
        scandir_calls.append(path)
        return original_os_scandir(path)  # type: ignore[arg-type]

    @contextmanager
    def replacing_scandir(
        trusted_root: object,
        relative: str,
        expected: os.stat_result | None = None,
    ):
        if relative == "queued" and queued.exists():
            queued.rename(repository / "queued-backup")
            replacement.rename(queued)
        with original_scandir(trusted_root, relative, expected) as entries:  # type: ignore[arg-type]
            yield entries

    monkeypatch.setattr(evaluation_harness._TrustedRoot, "scandir", replacing_scandir)
    monkeypatch.setattr(evaluation_harness.os, "scandir", recording_os_scandir)
    manifest = _build_integrity_manifest(repository)

    assert manifest.complete is False
    assert manifest.digest is None
    assert "replacement.txt" not in {entry.relative_path for entry in manifest.entries}
    assert len(scandir_calls) == 1


@pytest.mark.parametrize(
    ("limits", "expected_reason"),
    (
        (IntegrityLimits(maximum_files=1), "maximum-files-exceeded"),
        (IntegrityLimits(maximum_file_size_bytes=2), "maximum-file-size-exceeded"),
        (IntegrityLimits(maximum_total_bytes=3), "maximum-total-bytes-exceeded"),
    ),
)
def test_integrity_limits_fail_closed(
    tmp_path: Path,
    limits: IntegrityLimits,
    expected_reason: str,
) -> None:
    repository = tmp_path / "plain"
    repository.mkdir()
    (repository / "a.bin").write_bytes(b"abc")
    (repository / "b.bin").write_bytes(b"def")

    incomplete = _build_integrity_manifest(repository, limits=limits)
    complete = _build_integrity_manifest(repository)

    assert incomplete.complete is False
    assert incomplete.digest is None
    assert incomplete.failure_reason == expected_reason
    assert _integrity_manifests_equal(incomplete, incomplete) is False
    assert _integrity_manifests_equal(incomplete, complete) is False


@pytest.mark.parametrize("unsafe", ("../escape", "/absolute", "C:/absolute", "safe/../../escape"))
def test_integrity_path_validation_rejects_unsafe_paths(unsafe: str) -> None:
    with pytest.raises(ValueError, match="repository-relative|inside"):
        _validated_relative_path(unsafe)


def test_integrity_path_validation_preserves_posix_backslashes() -> None:
    if os.name == "nt":
        with pytest.raises(ValueError, match="separators"):
            _validated_relative_path("nested\\file.bin")
    else:
        assert _validated_relative_path("nested\\file.bin") == "nested\\file.bin"


def test_regular_file_replaced_by_symlink_fails_before_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "plain"
    repository.mkdir()
    victim = repository / "victim.bin"
    victim.write_bytes(b"inside")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"secret")
    original_open = evaluation_harness._open_regular_file_without_following
    digest_calls = 0
    original_digest = evaluation_harness._stream_digest

    def replacing_open(
        trusted_root: object,
        relative: str,
        metadata: os.stat_result,
    ) -> int:
        if relative == "victim.bin" and not victim.is_symlink():
            victim.unlink()
            try:
                victim.symlink_to(outside)
            except OSError:
                pytest.skip("This host does not permit the symlink race fixture.")
        return original_open(trusted_root, relative, metadata)  # type: ignore[arg-type]

    def recording_digest(stream: object, expected_size: int) -> tuple[str, int]:
        nonlocal digest_calls
        digest_calls += 1
        return original_digest(stream, expected_size)  # type: ignore[arg-type]

    monkeypatch.setattr(evaluation_harness, "_open_regular_file_without_following", replacing_open)
    monkeypatch.setattr(evaluation_harness, "_stream_digest", recording_digest)
    manifest = _build_integrity_manifest(repository)

    assert manifest.complete is False
    assert manifest.digest is None
    assert manifest.failure_reason in {"symlink-follow-blocked", "filesystem-entry-changed"}
    assert digest_calls == 0


def test_regular_file_replaced_by_different_regular_file_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "plain"
    repository.mkdir()
    victim = repository / "victim.bin"
    victim.write_bytes(b"first!")
    replacement = repository / "replacement.tmp"
    replacement.write_bytes(b"second")
    original_open = evaluation_harness._open_regular_file_without_following
    replaced = False

    def replacing_open(
        trusted_root: object,
        relative: str,
        metadata: os.stat_result,
    ) -> int:
        nonlocal replaced
        if relative == "victim.bin" and not replaced:
            replaced = True
            replacement.replace(victim)
        return original_open(trusted_root, relative, metadata)  # type: ignore[arg-type]

    monkeypatch.setattr(evaluation_harness, "_open_regular_file_without_following", replacing_open)
    manifest = _build_integrity_manifest(repository)

    assert manifest.complete is False
    assert manifest.digest is None
    assert manifest.failure_reason == "filesystem-entry-changed"


def test_regular_file_size_change_before_open_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "plain"
    repository.mkdir()
    victim = repository / "victim.bin"
    victim.write_bytes(b"first")
    original_open = evaluation_harness._open_regular_file_without_following
    mutated = False

    def mutating_open(
        trusted_root: object,
        relative: str,
        metadata: os.stat_result,
    ) -> int:
        nonlocal mutated
        if relative == "victim.bin" and not mutated:
            mutated = True
            with victim.open("ab") as stream:
                stream.write(b"!")
        return original_open(trusted_root, relative, metadata)  # type: ignore[arg-type]

    monkeypatch.setattr(evaluation_harness, "_open_regular_file_without_following", mutating_open)
    manifest = _build_integrity_manifest(repository)

    assert manifest.complete is False
    assert manifest.failure_reason == "filesystem-entry-changed"


def test_duplicate_git_integrity_path_fails_explicitly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "git-subject"
    repository.mkdir()
    (repository / "same.txt").write_text("same\n", encoding="utf-8")
    listings = iter((b"same.txt\0same.txt\0", b""))
    monkeypatch.setattr(
        evaluation_harness,
        "_run_fixed_git_listing",
        lambda *args, **kwargs: next(listings),
    )

    manifest = evaluation_harness._build_git_integrity_manifest(
        repository,
        IntegrityLimits(),
        (),
    )

    assert manifest.complete is False
    assert manifest.digest is None
    assert manifest.failure_reason == "duplicate-integrity-path"


@pytest.mark.parametrize(
    ("candidate_payload", "excluded_payload"),
    (
        (b"a\0b\0c\0", b""),
        (b"", b"ignored-a\0ignored-b\0ignored-c\0"),
        (b"a\0", b"ignored-a\0ignored-b\0"),
    ),
)
def test_git_path_records_share_one_incremental_entry_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    candidate_payload: bytes,
    excluded_payload: bytes,
) -> None:
    repository = tmp_path / "git-subject"
    repository.mkdir()
    for name in ("a", "b", "c"):
        (repository / name).write_text(name, encoding="utf-8")
    listings = iter((candidate_payload, excluded_payload))
    monkeypatch.setattr(
        evaluation_harness,
        "_run_fixed_git_listing",
        lambda *args, **kwargs: next(listings),
    )

    manifest = evaluation_harness._build_git_integrity_manifest(
        repository,
        IntegrityLimits(maximum_path_entries=2),
        (),
    )

    assert manifest.complete is False
    assert manifest.digest is None
    assert manifest.failure_reason == "maximum-path-entries-exceeded"


def test_git_incremental_path_budget_accepts_exact_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "git-subject"
    repository.mkdir()
    (repository / "a").write_text("a", encoding="utf-8")
    listings = iter((b"a\0", b"ignored\0"))
    monkeypatch.setattr(
        evaluation_harness,
        "_run_fixed_git_listing",
        lambda *args, **kwargs: next(listings),
    )

    manifest = evaluation_harness._build_git_integrity_manifest(
        repository,
        IntegrityLimits(maximum_path_entries=2),
        (),
    )

    assert manifest.complete is True
    assert {entry.relative_path for entry in manifest.entries} == {"a"}
    assert manifest.exclusion_counts_dict() == {"gitignored": 1}


@pytest.mark.parametrize("payload", (b"missing-nul", b"\xff\0"))
def test_git_incremental_path_parser_rejects_bounded_invalid_payloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> None:
    repository = tmp_path / "git-subject"
    repository.mkdir()
    listings = iter((payload, b""))
    monkeypatch.setattr(
        evaluation_harness,
        "_run_fixed_git_listing",
        lambda *args, **kwargs: next(listings),
    )

    manifest = evaluation_harness._build_git_integrity_manifest(
        repository,
        IntegrityLimits(maximum_path_entries=2),
        (),
    )

    assert manifest.complete is False
    assert manifest.failure_reason == "unsafe-git-path-list"


def test_git_incremental_parser_does_not_split_whole_payload() -> None:
    class NoSplitBytes(bytes):
        def split(self, *args: object, **kwargs: object):
            raise AssertionError("whole-payload split must not be used")

    budget = evaluation_harness._PathEntryBudget(2)
    records = tuple(evaluation_harness._iter_bounded_nul_paths(NoSplitBytes(b"a\0b\0"), budget))

    assert records == ("a", "b")
    assert budget.count == 2


def test_git_manifest_ignores_global_xdg_and_info_excludes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "git-subject"
    repository.mkdir()
    _git(repository, "init")
    (repository / ".gitignore").write_text(
        "repo-ignored.txt\ntracked-ignored.txt\n",
        encoding="utf-8",
    )
    for name in (
        "global.txt",
        "xdg.txt",
        "info.txt",
        "repo-ignored.txt",
        "tracked-ignored.txt",
    ):
        (repository / name).write_text(name, encoding="utf-8")
    _git(repository, "add", ".gitignore")
    _git(repository, "add", "-f", "tracked-ignored.txt")
    with (repository / ".git" / "info" / "exclude").open("a", encoding="utf-8") as stream:
        stream.write("\ninfo.txt\n")

    global_ignore = tmp_path / "global-ignore"
    global_ignore.write_text("global.txt\n", encoding="utf-8")
    global_config = tmp_path / "global.gitconfig"
    subprocess.run(
        [
            "git",
            "config",
            "--file",
            str(global_config),
            "core.excludesFile",
            str(global_ignore),
        ],
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    )
    xdg = tmp_path / "xdg"
    (xdg / "git").mkdir(parents=True)
    (xdg / "git" / "ignore").write_text("xdg.txt\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))

    baseline = _build_integrity_manifest(repository)
    included = {entry.relative_path for entry in baseline.entries}
    assert baseline.complete is True
    assert {"global.txt", "xdg.txt", "info.txt", "tracked-ignored.txt"} <= included
    assert "repo-ignored.txt" not in included
    assert baseline.exclusion_counts_dict()["gitignored"] >= 1

    alternate = tmp_path / "alternate"
    alternate.mkdir()
    monkeypatch.setenv("HOME", str(alternate))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(alternate / "missing-config"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(alternate / "missing-xdg"))
    assert _build_integrity_manifest(repository).digest == baseline.digest


@pytest.mark.skipif(os.name == "nt", reason="Windows filenames cannot contain literal backslashes")
def test_git_manifest_preserves_distinct_posix_backslash_paths(tmp_path: Path) -> None:
    repository = tmp_path / "git-subject"
    repository.mkdir()
    _git(repository, "init")
    literal = repository / "a\\b"
    nested = repository / "a" / "b"
    nested.parent.mkdir()
    literal.write_text("literal\n", encoding="utf-8")
    nested.write_text("nested\n", encoding="utf-8")
    _git(repository, "add", "--", "a\\b", "a/b")

    baseline = _build_integrity_manifest(repository)
    assert {entry.relative_path for entry in baseline.entries} == {"a\\b", "a/b"}
    literal.write_text("changed literal\n", encoding="utf-8")
    literal_changed = _build_integrity_manifest(repository)
    assert literal_changed.digest != baseline.digest
    literal.write_text("literal\n", encoding="utf-8")
    nested.write_text("changed nested\n", encoding="utf-8")
    assert _build_integrity_manifest(repository).digest != baseline.digest


@pytest.mark.parametrize(
    ("size", "limit"),
    ((7, 8), (8, 8)),
)
def test_git_listing_accepts_output_at_or_below_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    size: int,
    limit: int,
) -> None:
    processes = _replace_git_with_python_producer(
        monkeypatch, f"import sys;sys.stdout.buffer.write(b'x'*{size})"
    )

    payload = evaluation_harness._run_fixed_git_listing(
        tmp_path,
        ("ls-files", "-z"),
        maximum_output_bytes=limit,
    )

    assert payload == b"x" * size
    assert processes[0].poll() is not None


def test_git_listing_terminates_producer_one_byte_over_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processes = _replace_git_with_python_producer(
        monkeypatch,
        "import sys,time;sys.stdout.buffer.write(b'x'*9);sys.stdout.buffer.flush();time.sleep(10)",
    )

    with pytest.raises(ValueError, match="bounded output limit"):
        evaluation_harness._run_fixed_git_listing(
            tmp_path,
            ("ls-files", "-z"),
            maximum_output_bytes=8,
        )

    assert processes[0].poll() is not None


def test_git_listing_terminates_continuing_producer_at_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = "import sys,time\nwhile True:\n sys.stdout.buffer.write(b'x'*1024);sys.stdout.buffer.flush();time.sleep(.001)"
    processes = _replace_git_with_python_producer(monkeypatch, script)

    with pytest.raises(ValueError, match="bounded output limit"):
        evaluation_harness._run_fixed_git_listing(
            tmp_path,
            ("ls-files", "-z"),
            maximum_output_bytes=8,
        )

    assert processes[0].poll() is not None


def test_git_listing_timeout_terminates_and_reaps_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processes = _replace_git_with_python_producer(monkeypatch, "import time;time.sleep(10)")
    monkeypatch.setattr(evaluation_harness, "_GIT_COMMAND_TIMEOUT_SECONDS", 0.05)

    with pytest.raises(subprocess.TimeoutExpired):
        evaluation_harness._run_fixed_git_listing(
            tmp_path,
            ("ls-files", "-z"),
            maximum_output_bytes=8,
        )

    assert processes[0].poll() is not None


def test_git_listing_nonzero_exit_is_bounded_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processes = _replace_git_with_python_producer(monkeypatch, "raise SystemExit(3)")

    with pytest.raises(ValueError, match="listed safely"):
        evaluation_harness._run_fixed_git_listing(
            tmp_path,
            ("ls-files", "-z"),
            maximum_output_bytes=8,
        )

    assert processes[0].poll() is not None


def test_public_fixtures_have_reproducible_manifest_evidence(tmp_path: Path) -> None:
    first = generate_public_fixtures(tmp_path / "first")
    second = generate_public_fixtures(tmp_path / "second")

    first_evidence = {
        label: (
            manifest.digest,
            manifest.included_file_count,
            manifest.included_byte_count,
            manifest.excluded_counts,
        )
        for label, root in first
        for manifest in (_build_integrity_manifest(root),)
    }
    second_evidence = {
        label: (
            manifest.digest,
            manifest.included_file_count,
            manifest.included_byte_count,
            manifest.excluded_counts,
        )
        for label, root in second
        for manifest in (_build_integrity_manifest(root),)
    }

    assert first_evidence == second_evidence
    assert dict(first_evidence)["public-large"][3] == (("gitignored", 1),)


def test_evaluation_detects_repository_mutation_without_path_leakage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "subject"
    repository.mkdir()
    included = repository / "sample.py"
    included.write_text("value = 1\n", encoding="utf-8")
    original_analyze = evaluation_harness.RepositoryReviewService.analyze
    calls = 0

    def mutating_analyze(service: object, path: Path, **kwargs: object):
        nonlocal calls
        evidence = original_analyze(service, path, **kwargs)  # type: ignore[arg-type]
        calls += 1
        if calls == 1:
            included.write_text("value = 2\n", encoding="utf-8")
        return evidence

    monkeypatch.setattr(evaluation_harness.RepositoryReviewService, "analyze", mutating_analyze)
    output = tmp_path / "result.json"
    payload = evaluate_subjects(
        (("public-mutation", repository),),
        output_path=output,
        data_directory=tmp_path / "data",
        repeats=2,
        limits=ScanLimits(),
    )

    subject = payload["subjects"][0]
    serialized = output.read_text(encoding="utf-8")
    assert subject["integrity"]["complete"] is True
    assert subject["integrity"]["equal"] is False
    assert subject["persistence"]["repository_bytes_unchanged"] is False
    assert str(repository.resolve()) not in serialized
    assert "sample.py" not in serialized
    assert os.environ.get("USERNAME", "__missing_username__") not in serialized


def test_nested_git_output_and_data_paths_are_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "git-subject"
    nested = repository / "nested"
    nested.mkdir(parents=True)
    _git(repository, "init")
    (nested / "sample.py").write_text("value = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="outside every analyzed repository"):
        evaluate_subjects(
            (("public-nested", nested),),
            output_path=repository / "sibling-result.json",
            data_directory=tmp_path / "data",
            repeats=2,
            limits=ScanLimits(),
        )


def test_dogfood_report_preserves_history_and_documents_new_integrity_contract() -> None:
    report = (
        Path(__file__).resolve().parents[2] / "docs" / "product" / "REPOSITORY_REVIEW_DOGFOOD_REPORT.md"
    ).read_text(encoding="utf-8")

    assert "## Integrity methodology correction (#114)" in report
    assert "evaluation output format `2`" in report.casefold()
    assert "integrity-manifest format `1`" in report
    assert "were not produced with integrity-manifest" in report
    assert "Exact measured dogfood build SHA" in report
    assert "Post-polish rerun" in report
    assert "#115" in report


def test_finding_sample_manifest_is_reproducible_sanitized_and_matches_report() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    manifest_path = repository_root / "docs" / "product" / "REPOSITORY_REVIEW_DOGFOOD_FINDING_SAMPLE.json"
    report_path = repository_root / "docs" / "product" / "REPOSITORY_REVIEW_DOGFOOD_REPORT.md"
    serialized = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(serialized)
    entries = _assert_finding_sample_manifest_contract(
        serialized,
        manifest,
        expected_build_sha="".join(("678356bf", "4e237308", "86abaffd", "84186d0c", "5d3627f7")),
        expected_snapshot_id="".join(
            (
                "d283a162",
                "2b361e0f",
                "f4484455",
                "0525b05d",
                "a2e04683",
                "524dd3bb",
                "8d017e2b",
                "116e14d6",
            )
        ),
    )
    report_rows = _historical_finding_review_rows(report_path.read_text(encoding="utf-8"))
    _assert_manifest_matches_report(entries, report_rows)


def test_post_polish_finding_sample_manifest_is_reproducible_sanitized_and_matches_report() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    manifest_path = repository_root / "docs" / "product" / "REPOSITORY_REVIEW_POST_POLISH_FINDING_SAMPLE.json"
    report_path = repository_root / "docs" / "product" / "REPOSITORY_REVIEW_DOGFOOD_REPORT.md"
    serialized = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(serialized)
    entries = _assert_finding_sample_manifest_contract(
        serialized,
        manifest,
        expected_build_sha="".join(("741a86c4", "a62fceb9", "e6e4c285", "84ffebfa", "32080d9d")),
        expected_snapshot_id="".join(
            (
                "74f193c8",
                "3f921f1c",
                "45040382",
                "e70afb91",
                "1d938962",
                "e33df665",
                "cbc32db8",
                "0d230735",
            )
        ),
    )

    compatibility = manifest["historical_sample_compatibility"]
    assert compatibility == {
        "historical_entries": 50,
        "historical_logical_keys_still_present": 47,
        "exact_current_selection_overlap": 17,
        "current_entries": 50,
        "compatible_for_exact_parity": False,
    }
    assert 0 <= compatibility["historical_logical_keys_still_present"] <= compatibility["historical_entries"]
    assert (
        0
        <= compatibility["exact_current_selection_overlap"]
        <= min(
            compatibility["historical_logical_keys_still_present"],
            compatibility["current_entries"],
        )
    )

    expected_totals = {
        "useful-actionable": 22,
        "valid-low-priority": 11,
        "intentional-design": 8,
        "false-positive": 0,
        "unsupported-ambiguous": 9,
    }
    classification_counts = Counter(entry["classification"] for entry in entries)
    assert {
        classification: classification_counts[classification]
        for classification in _ALLOWED_SAMPLE_CLASSIFICATIONS
    } == expected_totals

    report = report_path.read_text(encoding="utf-8")
    assert report.index("### Finding families and high-signal queue") < report.index(
        "## Finding-Family Review"
    )
    report_rows = _post_polish_finding_review_rows(report)
    _assert_manifest_matches_report(entries, report_rows)

    post_polish_section = _report_section(
        report,
        "### Finding families and high-signal queue",
        "### #100 — Exact Handoff JSON budget",
    )
    normalized_section = " ".join(post_polish_section.split())
    assert (
        "The post-polish deterministic sample contains 50 entries: 22 useful or actionable, "
        "11 valid low priority, 8 intentional design, zero false positives, and 9 unsupported "
        "or ambiguous."
    ) in normalized_section


def _assert_finding_sample_manifest_contract(
    serialized: str,
    manifest: dict[str, object],
    *,
    expected_build_sha: str,
    expected_snapshot_id: str,
) -> list[dict[str, object]]:
    assert manifest["format_version"] == 1
    build_sha = manifest["evaluated_build_sha"]
    assert isinstance(build_sha, dict)
    assert build_sha["algorithm"] == "git-sha1"
    assert all(re.fullmatch(r"[0-9a-f]{8}", part) for part in build_sha["parts"])
    assert "".join(build_sha["parts"]) == expected_build_sha

    snapshot_id = manifest["evaluated_snapshot_id"]
    assert isinstance(snapshot_id, dict)
    assert snapshot_id["algorithm"] == "sha256"
    assert all(re.fullmatch(r"[0-9a-f]{8}", part) for part in snapshot_id["parts"])
    assert "".join(snapshot_id["parts"]) == expected_snapshot_id
    assert len(expected_snapshot_id) == 64

    assert manifest["source_label"] == "zscripts-public"
    assert manifest["scan_limits"] == asdict(ScanLimits())
    selection_policy = manifest["selection_policy"]
    assert isinstance(selection_policy, dict)
    assert selection_policy == {
        "ordering": ["family", "finding_id"],
        "manifest_identifier": "stable public logical finding key",
        "maximum_per_family": 5,
        "rule": (
            "Select the first five stable finding IDs in each family, or every finding when "
            "the family contains fewer than five."
        ),
    }
    assert set(manifest["allowed_classifications"]) == _ALLOWED_SAMPLE_CLASSIFICATIONS

    entries = manifest["entries"]
    assert isinstance(entries, list)
    assert len(entries) == 50
    assert all(
        set(entry)
        == {
            "family",
            "selection_rank",
            "finding_key",
            "rule_id",
            "subject_type",
            "classification",
            "rationale_code",
        }
        for entry in entries
    )
    ordering = [(entry["family"], entry["selection_rank"]) for entry in entries]
    assert ordering == sorted(ordering)
    assert all(entry["family"] in _ALLOWED_FINDING_FAMILIES for entry in entries)
    assert all(entry["subject_type"] in _ALLOWED_SAMPLE_SUBJECT_TYPES for entry in entries)
    assert all(entry["classification"] in _ALLOWED_SAMPLE_CLASSIFICATIONS for entry in entries)
    assert all(re.fullmatch(r"[A-Za-z0-9_.+]+", entry["finding_key"]) for entry in entries)
    assert all(re.fullmatch(r"[a-z0-9-]+", entry["rationale_code"]) for entry in entries)
    assert len({(entry["family"], entry["rule_id"], entry["finding_key"]) for entry in entries}) == len(
        entries
    )
    family_counts = Counter(entry["family"] for entry in entries)
    assert max(family_counts.values()) <= 5
    for family, count in family_counts.items():
        assert [entry["selection_rank"] for entry in entries if entry["family"] == family] == list(
            range(1, count + 1)
        )

    assert re.search(r"(?i)[a-z]:[\\/]", serialized) is None
    assert re.search(r'"/', serialized) is None
    assert "source_excerpt" not in serialized
    assert "relative_path" not in serialized
    for marker in (
        "Nobod",
        "dev-logger-dogfood-worktree",
        "repository-review-dogfood-raw",
        "private-repository",
    ):
        assert marker not in serialized
    return entries


def _assert_manifest_matches_report(
    entries: list[dict[str, object]],
    report_rows: dict[str, dict[str, int]],
) -> None:
    manifest_counts = Counter((entry["family"], entry["classification"]) for entry in entries)
    for family in _ALLOWED_FINDING_FAMILIES:
        report_row = report_rows[family]
        assert report_row["reviewed"] == sum(
            manifest_counts[(family, classification)] for classification in _ALLOWED_SAMPLE_CLASSIFICATIONS
        )
        for classification in _ALLOWED_SAMPLE_CLASSIFICATIONS:
            assert report_row[classification] == manifest_counts[(family, classification)]


def _historical_finding_review_rows(report: str) -> dict[str, dict[str, int]]:
    section = _report_section(report, "## Finding-Family Review", "## Performance")
    row_pattern = re.compile(
        r"^\| (?P<label>[^|]+?) \| [\d,]+ \| "
        r"(?P<reviewed>\d+) \| (?P<useful>\d+) \| (?P<low>\d+) \| "
        r"(?P<intentional>\d+) \| (?P<false_positive>\d+) \| "
        r"(?P<unsupported>\d+) \|",
        re.MULTILINE,
    )
    rows: dict[str, dict[str, int]] = {}
    for match in row_pattern.finditer(section):
        label = match.group("label")
        if label not in _REPORT_FAMILY_NAMES:
            continue
        rows[_REPORT_FAMILY_NAMES[label]] = {
            "reviewed": int(match.group("reviewed")),
            "useful-actionable": int(match.group("useful")),
            "valid-low-priority": int(match.group("low")),
            "intentional-design": int(match.group("intentional")),
            "false-positive": int(match.group("false_positive")),
            "unsupported-ambiguous": int(match.group("unsupported")),
        }
    assert set(rows) == _ALLOWED_FINDING_FAMILIES
    return rows


def _post_polish_finding_review_rows(report: str) -> dict[str, dict[str, int]]:
    section = _report_section(
        report,
        "### Finding families and high-signal queue",
        "### #100 — Exact Handoff JSON budget",
    )
    assert "Before observed" in section
    assert "Current sample" in section
    row_pattern = re.compile(
        r"^\| (?P<label>[^|]+?) \| [\d,]+ \| [\d,]+ \| "
        r"(?P<reviewed>\d+) \| (?P<useful>\d+) \| (?P<low>\d+) \| "
        r"(?P<intentional>\d+) \| (?P<false_positive>\d+) \| "
        r"(?P<unsupported>\d+) \|",
        re.MULTILINE,
    )
    rows: dict[str, dict[str, int]] = {}
    for match in row_pattern.finditer(section):
        label = match.group("label")
        if label not in _REPORT_FAMILY_NAMES:
            continue
        rows[_REPORT_FAMILY_NAMES[label]] = {
            "reviewed": int(match.group("reviewed")),
            "useful-actionable": int(match.group("useful")),
            "valid-low-priority": int(match.group("low")),
            "intentional-design": int(match.group("intentional")),
            "false-positive": int(match.group("false_positive")),
            "unsupported-ambiguous": int(match.group("unsupported")),
        }
    assert set(rows) == _ALLOWED_FINDING_FAMILIES
    return rows


def _report_section(report: str, start_heading: str, end_heading: str) -> str:
    start = report.index(start_heading)
    end = report.index(end_heading, start + len(start_heading))
    return report[start:end]


def _fixture_digest(subjects: tuple[tuple[str, Path], ...]) -> str:
    digest = hashlib.sha256()
    for label, root in subjects:
        digest.update(label.encode())
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _replace_git_with_python_producer(
    monkeypatch: pytest.MonkeyPatch,
    script: str,
) -> list[subprocess.Popen[bytes]]:
    original_popen = evaluation_harness.subprocess.Popen
    processes: list[subprocess.Popen[bytes]] = []

    def producer_popen(command: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
        assert command[0] == "git"
        assert kwargs.get("shell") is False
        process = original_popen(
            [sys.executable, "-c", script],
            **kwargs,  # type: ignore[arg-type]
        )
        processes.append(process)
        return process

    monkeypatch.setattr(evaluation_harness.subprocess, "Popen", producer_popen)
    return processes


def _git(repository: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    )
