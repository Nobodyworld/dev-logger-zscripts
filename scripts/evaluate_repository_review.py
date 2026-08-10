"""Run sanitized, reproducible dogfood measurements for Repository Review."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import stat
import statistics
import subprocess  # nosec B404 - fixed Git metadata command only
import sys
import tempfile
import threading
import time
import tracemalloc
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Sequence

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    if str(_REPOSITORY_ROOT) in sys.path:
        sys.path.remove(str(_REPOSITORY_ROOT))
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from zscripts.application.repository_review import RepositoryReviewService  # noqa: E402
from zscripts.domain.repository_comparison import HandoffSelection  # noqa: E402
from zscripts.domain.repository_review import ScanLimits  # noqa: E402
from zscripts.infrastructure.repository_discovery import (  # noqa: E402
    DEFAULT_EXCLUDED_DIRECTORIES,
    RepositoryDiscovery,
)

_LABEL_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_MAX_FINDING_SAMPLE = 20
_MAX_NEIGHBORHOOD_FOCUSES = 5
_NEIGHBORHOOD_MAX_NODES = 40
_NEIGHBORHOOD_MAX_EDGES = 80
EVALUATION_OUTPUT_FORMAT_VERSION = 2
INTEGRITY_MANIFEST_FORMAT_VERSION = 1
_HASH_CHUNK_BYTES = 1024 * 1024
_GIT_COMMAND_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class IntegrityLimits:
    """Independent bounds for repository-integrity evidence."""

    maximum_files: int = 50_000
    maximum_path_entries: int = 50_000
    maximum_file_size_bytes: int = 256 * 1024 * 1024
    maximum_total_bytes: int = 2 * 1024 * 1024 * 1024
    maximum_path_listing_bytes: int = 64 * 1024 * 1024

    def __post_init__(self) -> None:
        if (
            min(
                self.maximum_files,
                self.maximum_path_entries,
                self.maximum_file_size_bytes,
                self.maximum_total_bytes,
                self.maximum_path_listing_bytes,
            )
            < 1
        ):
            raise ValueError("Integrity limits must be positive integers.")

    def sanitized(self) -> dict[str, int]:
        return {
            "maximum_files": self.maximum_files,
            "maximum_path_entries": self.maximum_path_entries,
            "maximum_file_size_bytes": self.maximum_file_size_bytes,
            "maximum_total_bytes": self.maximum_total_bytes,
            "maximum_path_listing_bytes": self.maximum_path_listing_bytes,
        }


@dataclass(frozen=True, slots=True)
class IntegrityManifestEntry:
    """One deterministic in-memory manifest entry; never emitted publicly."""

    relative_path: str
    entry_type: str
    size_bytes: int
    content_digest: str


@dataclass(frozen=True, slots=True)
class IntegrityManifestResult:
    """A bounded integrity result with an optional complete manifest."""

    format_version: int
    mode: str
    complete: bool
    digest: str | None
    included_file_count: int
    included_byte_count: int
    excluded_counts: tuple[tuple[str, int], ...]
    limits: IntegrityLimits
    failure_reason: str | None
    entries: tuple[IntegrityManifestEntry, ...] = ()

    def exclusion_counts_dict(self) -> dict[str, int]:
        return dict(self.excluded_counts)


class _ManifestBuilder:
    def __init__(self, *, mode: str, limits: IntegrityLimits) -> None:
        self.mode = mode
        self.limits = limits
        self.entries: list[IntegrityManifestEntry] = []
        self.excluded: Counter[str] = Counter()
        self.included_bytes = 0
        self.considered_entries = 0
        self.failure_reason: str | None = None

    @property
    def complete(self) -> bool:
        return self.failure_reason is None

    def exclude(self, reason: str, count: int = 1) -> None:
        self.excluded[reason] += count

    def fail(self, reason: str) -> None:
        if self.failure_reason is None:
            self.failure_reason = reason

    def add_path(self, root: Path, relative: str) -> None:
        if not self.complete:
            return
        self.considered_entries += 1
        if self.considered_entries > self.limits.maximum_files:
            self.fail("maximum-files-exceeded")
            return
        absolute = root.joinpath(*PurePosixPath(relative).parts)
        try:
            metadata = absolute.lstat()
        except OSError:
            self.fail("filesystem-entry-unreadable")
            return
        if stat.S_ISLNK(metadata.st_mode):
            try:
                target = os.readlink(absolute).encode("utf-8", errors="strict")
            except (OSError, UnicodeError):
                self.fail("symlink-target-unreadable")
                return
            self._add_bytes(relative, "symlink", target)
            return
        if not stat.S_ISREG(metadata.st_mode):
            self.exclude("unsupported-entry-type")
            return
        size = metadata.st_size
        if size > self.limits.maximum_file_size_bytes:
            self.fail("maximum-file-size-exceeded")
            return
        if self.included_bytes + size > self.limits.maximum_total_bytes:
            self.fail("maximum-total-bytes-exceeded")
            return
        try:
            descriptor = _open_regular_file_without_following(absolute, metadata)
        except OSError:
            self.fail("symlink-follow-blocked")
            return
        except ValueError as exc:
            self.fail(str(exc))
            return
        try:
            with os.fdopen(descriptor, "rb", closefd=True) as stream:
                content_digest, observed_size = _stream_digest(stream, size)
                final_metadata = os.fstat(stream.fileno())
        except OSError:
            self.fail("file-content-unreadable")
            return
        if observed_size != size or not _same_regular_file(metadata, final_metadata):
            self.fail("filesystem-entry-changed")
            return
        self.entries.append(IntegrityManifestEntry(relative, "regular", size, content_digest))
        self.included_bytes += size

    def _add_bytes(self, relative: str, entry_type: str, content: bytes) -> None:
        size = len(content)
        if size > self.limits.maximum_file_size_bytes:
            self.fail("maximum-file-size-exceeded")
            return
        if self.included_bytes + size > self.limits.maximum_total_bytes:
            self.fail("maximum-total-bytes-exceeded")
            return
        self.entries.append(
            IntegrityManifestEntry(relative, entry_type, size, hashlib.sha256(content).hexdigest())
        )
        self.included_bytes += size

    def result(self) -> IntegrityManifestResult:
        entries = tuple(sorted(self.entries, key=lambda item: item.relative_path.encode("utf-8")))
        complete = self.complete
        digest = (
            hashlib.sha256(_canonical_manifest_bytes(self.mode, entries)).hexdigest() if complete else None
        )
        return IntegrityManifestResult(
            format_version=INTEGRITY_MANIFEST_FORMAT_VERSION,
            mode=self.mode,
            complete=complete,
            digest=digest,
            included_file_count=len(entries),
            included_byte_count=self.included_bytes,
            excluded_counts=tuple(sorted(self.excluded.items())),
            limits=self.limits,
            failure_reason=self.failure_reason,
            entries=entries,
        )


def _stream_digest(stream: BinaryIO, expected_size: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    observed_size = 0
    while observed_size < expected_size:
        chunk = stream.read(min(_HASH_CHUNK_BYTES, expected_size - observed_size))
        if not chunk:
            break
        observed_size += len(chunk)
        digest.update(chunk)
    if stream.read(1):
        observed_size += 1
    return digest.hexdigest(), observed_size


def _open_regular_file_without_following(absolute: Path, expected: os.stat_result) -> int:
    flags = os.O_RDONLY
    for optional_flag in ("O_NOFOLLOW", "O_CLOEXEC", "O_BINARY"):
        flags |= int(getattr(os, optional_flag, 0))
    descriptor = os.open(absolute, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError("opened-entry-not-regular")
        if not _same_regular_file(expected, opened):
            raise ValueError("filesystem-entry-changed")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _same_regular_file(
    expected: os.stat_result,
    observed: os.stat_result,
) -> bool:
    if not stat.S_ISREG(expected.st_mode) or not stat.S_ISREG(observed.st_mode):
        return False
    if expected.st_size != observed.st_size:
        return False
    expected_identity = (expected.st_dev, expected.st_ino)
    observed_identity = (observed.st_dev, observed.st_ino)
    if all(expected_identity) and expected_identity != observed_identity:
        return False
    return True


def _canonical_manifest_bytes(
    mode: str,
    entries: Sequence[IntegrityManifestEntry],
) -> bytes:
    canonical = bytearray(
        f"integrity-manifest\0{INTEGRITY_MANIFEST_FORMAT_VERSION}\0{mode}\0".encode("ascii")
    )
    for entry in entries:
        canonical.extend(entry.relative_path.encode("utf-8"))
        canonical.extend(b"\0")
        canonical.extend(entry.entry_type.encode("ascii"))
        canonical.extend(b"\0")
        canonical.extend(str(entry.size_bytes).encode("ascii"))
        canonical.extend(b"\0")
        canonical.extend(entry.content_digest.encode("ascii"))
        canonical.extend(b"\0")
    return bytes(canonical)


def _build_integrity_manifest(
    repository_path: Path,
    *,
    limits: IntegrityLimits | None = None,
    configured_excludes: Sequence[str] = (),
) -> IntegrityManifestResult:
    """Build a deterministic bounded manifest at the analyzer's resolved root."""

    selected_limits = limits or IntegrityLimits()
    discovery = RepositoryDiscovery()
    scope = discovery.resolve_scope(repository_path)
    root = Path(scope.analysis_root)
    excludes = tuple(
        sorted(
            {
                item.strip().replace("\\", "/") if os.name == "nt" else item.strip()
                for item in configured_excludes
                if item.strip()
            }
        )
    )
    if scope.git_root_detected:
        return _build_git_integrity_manifest(root, selected_limits, excludes)
    return _build_filesystem_integrity_manifest(root, selected_limits, excludes)


def _build_git_integrity_manifest(
    root: Path,
    limits: IntegrityLimits,
    configured_excludes: Sequence[str],
) -> IntegrityManifestResult:
    builder = _ManifestBuilder(mode="git", limits=limits)
    fixed_default_excludes = tuple(
        f"--exclude={name}/" for name in DEFAULT_EXCLUDED_DIRECTORIES if name != ".git"
    )
    try:
        payload = _run_fixed_git_listing(
            root,
            (
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                *fixed_default_excludes,
                "-z",
            ),
            maximum_output_bytes=limits.maximum_path_listing_bytes,
        )
        excluded_payload = _run_fixed_git_listing(
            root,
            (
                "ls-files",
                "--others",
                "--ignored",
                "--exclude-standard",
                *fixed_default_excludes,
                "--directory",
                "--no-empty-directory",
                "-z",
            ),
            maximum_output_bytes=limits.maximum_path_listing_bytes,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        builder.fail("git-path-list-unavailable-or-bounded")
        return builder.result()

    try:
        raw_candidates = _decode_nul_paths(payload)
        raw_excluded = _decode_nul_paths(excluded_payload)
    except ValueError:
        builder.fail("unsafe-git-path-list")
        return builder.result()

    for relative in raw_excluded:
        if _has_default_excluded_part(relative):
            builder.exclude("default-environment-or-cache")
        else:
            builder.exclude("gitignored")

    candidates: list[str] = []
    seen_candidates: set[str] = set()
    for raw_relative in raw_candidates:
        try:
            relative = _validated_relative_path(raw_relative)
        except ValueError:
            builder.fail("unsafe-git-path-list")
            return builder.result()
        if _has_default_excluded_part(relative):
            builder.exclude("default-environment-or-cache")
            continue
        if _matches_configured_integrity_exclude(relative, configured_excludes):
            builder.exclude("configured-integrity-exclude")
            continue
        if relative in seen_candidates:
            builder.fail("duplicate-integrity-path")
            return builder.result()
        if len(candidates) >= limits.maximum_files:
            builder.fail("maximum-files-exceeded")
            return builder.result()
        candidates.append(relative)
        seen_candidates.add(relative)
    for relative in sorted(candidates, key=lambda item: item.encode("utf-8")):
        builder.add_path(root, relative)
        if not builder.complete:
            break
    return builder.result()


def _build_filesystem_integrity_manifest(
    root: Path,
    limits: IntegrityLimits,
    configured_excludes: Sequence[str],
) -> IntegrityManifestResult:
    builder = _ManifestBuilder(mode="filesystem", limits=limits)
    ignore_patterns = RepositoryDiscovery._load_gitignore_patterns(root)
    candidates: list[str] = []
    encountered_entries = 0
    directories: list[tuple[Path, str]] = [(root, "")]
    try:
        while directories:
            directory_path, relative_directory = directories.pop()
            bounded_names: list[str] = []
            with os.scandir(directory_path) as entries:
                for entry in entries:
                    encountered_entries += 1
                    if encountered_entries > limits.maximum_path_entries:
                        builder.fail("maximum-path-entries-exceeded")
                        return builder.result()
                    bounded_names.append(entry.name)
            child_directories: list[tuple[Path, str]] = []
            for name in sorted(bounded_names, key=lambda item: item.encode("utf-8")):
                candidate = directory_path / name
                relative = _validated_relative_path(
                    f"{relative_directory}/{name}" if relative_directory else name
                )
                if _has_default_excluded_part(relative):
                    builder.exclude("default-environment-or-cache")
                elif _matches_configured_integrity_exclude(relative, configured_excludes):
                    builder.exclude("configured-integrity-exclude")
                elif RepositoryDiscovery._matches_gitignore(relative, ignore_patterns):
                    builder.exclude("gitignored")
                else:
                    metadata = candidate.lstat()
                    if stat.S_ISDIR(metadata.st_mode):
                        child_directories.append((candidate, relative))
                        continue
                    if len(candidates) >= limits.maximum_files:
                        builder.fail("maximum-files-exceeded")
                        return builder.result()
                    candidates.append(relative)
            directories.extend(reversed(child_directories))
    except (OSError, ValueError):
        builder.fail("filesystem-walk-unavailable")
        return builder.result()
    for relative in sorted(candidates, key=lambda item: item.encode("utf-8")):
        builder.add_path(root, relative)
        if not builder.complete:
            break
    return builder.result()


def _run_fixed_git_listing(
    root: Path,
    arguments: Sequence[str],
    *,
    maximum_output_bytes: int,
) -> bytes:
    no_hooks = Path(tempfile.gettempdir()) / "zscripts-no-git-hooks"
    command = [
        "git",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-c",
        f"core.hooksPath={no_hooks}",
        "-C",
        str(root),
        *arguments,
    ]
    environment = os.environ.copy()
    environment.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1", "LC_ALL": "C"})
    process = subprocess.Popen(  # nosec B603 - executable and argument contract are fixed
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment,
        shell=False,
    )
    stdout = process.stdout
    if stdout is None:  # pragma: no cover - PIPE guarantees stdout
        _terminate_and_reap(process)
        raise ValueError("Git integrity paths could not be listed safely.")
    output = bytearray()
    output_exceeded = threading.Event()
    reader_failed = threading.Event()

    def read_bounded_output() -> None:
        try:
            while len(output) <= maximum_output_bytes:
                remaining = maximum_output_bytes + 1 - len(output)
                chunk = stdout.read(min(_HASH_CHUNK_BYTES, remaining))
                if not chunk:
                    return
                output.extend(chunk)
                if len(output) > maximum_output_bytes:
                    output_exceeded.set()
                    try:
                        process.terminate()
                    except OSError:
                        pass
                    return
        except OSError:
            reader_failed.set()
            return

    reader = threading.Thread(target=read_bounded_output, daemon=True)
    reader.start()
    deadline = time.monotonic() + _GIT_COMMAND_TIMEOUT_SECONDS
    timed_out = False
    while process.poll() is None and not output_exceeded.is_set() and not reader_failed.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            break
        try:
            process.wait(timeout=min(0.05, remaining))
        except subprocess.TimeoutExpired:
            continue
    if timed_out or output_exceeded.is_set() or reader_failed.is_set():
        _terminate_and_reap(process)
    else:
        process.wait()
    reader.join(timeout=1.0)
    stdout.close()
    if reader.is_alive():
        _terminate_and_reap(process)
        raise ValueError("Git integrity paths could not be listed safely.")
    if timed_out:
        raise subprocess.TimeoutExpired(command, _GIT_COMMAND_TIMEOUT_SECONDS)
    if output_exceeded.is_set():
        raise ValueError("Git integrity path listing exceeded its bounded output limit.")
    if reader_failed.is_set():
        raise ValueError("Git integrity paths could not be listed safely.")
    if process.returncode:
        raise ValueError("Git integrity paths could not be listed safely.")
    return bytes(output)


def _terminate_and_reap(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        process.wait()
        return
    process.terminate()
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _decode_nul_paths(payload: bytes) -> tuple[str, ...]:
    if payload and not payload.endswith(b"\0"):
        raise ValueError("Git path listing was not NUL terminated.")
    try:
        return tuple(item.decode("utf-8", errors="strict") for item in payload.split(b"\0") if item)
    except UnicodeDecodeError as exc:
        raise ValueError("Git path listing was not valid UTF-8.") from exc


def _validated_relative_path(path: str) -> str:
    if not path or "\0" in path:
        raise ValueError("Integrity paths must be non-empty and NUL-free.")
    if os.name == "nt" and "\\" in path:
        raise ValueError("Integrity paths must use safe Git repository-relative separators.")
    pure = PurePosixPath(path)
    if pure.is_absolute() or pure.as_posix() == "." or ".." in pure.parts or re.match(r"^[A-Za-z]:", path):
        raise ValueError("Integrity paths must be safe repository-relative paths.")
    normalized = pure.as_posix()
    if normalized.startswith("../") or normalized.startswith("//"):
        raise ValueError("Integrity paths must remain inside the repository root.")
    return normalized


def _has_default_excluded_part(relative: str) -> bool:
    return any(part in DEFAULT_EXCLUDED_DIRECTORIES for part in PurePosixPath(relative).parts)


def _matches_configured_integrity_exclude(relative: str, patterns: Sequence[str]) -> bool:
    name = PurePosixPath(relative).name
    return any(
        fnmatch.fnmatchcase(relative, pattern) or fnmatch.fnmatchcase(name, pattern) for pattern in patterns
    )


def generate_public_fixtures(root: Path) -> tuple[tuple[str, Path], ...]:
    """Create deterministic public-only fixtures at one explicit external root."""

    root = root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("Public fixture root must be absent or empty.")
    root.mkdir(parents=True, exist_ok=True)
    subjects = (
        ("public-medium", root / "public-medium"),
        ("public-large", root / "public-large"),
        ("public-multipackage", root / "public-multipackage"),
        ("public-partial", root / "public-partial"),
        ("public-cycles-repeated", root / "public-cycles-repeated"),
    )
    _write_medium(subjects[0][1])
    _write_large(subjects[1][1])
    _write_multipackage(subjects[2][1])
    _write_partial(subjects[3][1])
    _write_cycles_repeated(subjects[4][1])
    return subjects


def evaluate_subjects(
    subjects: tuple[tuple[str, Path], ...],
    *,
    output_path: Path,
    data_directory: Path,
    repeats: int,
    limits: ScanLimits,
    integrity_limits: IntegrityLimits | None = None,
    integrity_excludes: Sequence[str] = (),
) -> dict[str, Any]:
    """Evaluate subjects through application services and write sanitized JSON."""

    if repeats < 2 or repeats > 5:
        raise ValueError("Repeat count must be between 2 and 5.")
    normalized = _normalize_subjects(subjects)
    _require_external_path(output_path, normalized, kind="output")
    _require_external_path(data_directory, normalized, kind="data directory")
    data_directory.mkdir(parents=True, exist_ok=True)
    selected_integrity_limits = integrity_limits or IntegrityLimits()
    results = [
        _evaluate_subject(
            label,
            path,
            data_directory=data_directory / label,
            repeats=repeats,
            limits=limits,
            integrity_limits=selected_integrity_limits,
            integrity_excludes=integrity_excludes,
        )
        for label, path in normalized
    ]
    payload: dict[str, Any] = {
        "format_version": EVALUATION_OUTPUT_FORMAT_VERSION,
        "integrity_manifest_format_version": INTEGRITY_MANIFEST_FORMAT_VERSION,
        "sanitized": True,
        "tracemalloc_scope": (
            "Python allocations observed by tracemalloc; not complete process or native memory."
        ),
        "limits": {
            "max_files": limits.max_files,
            "max_file_size_bytes": limits.max_file_size_bytes,
            "max_total_bytes": limits.max_total_bytes,
            "max_source_lines": limits.max_source_lines,
            "max_source_bytes": limits.max_source_bytes,
        },
        "integrity_limits": selected_integrity_limits.sanitized(),
        "subjects": results,
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    for _, path in normalized:
        if str(path) in serialized:
            raise RuntimeError("Sanitized output unexpectedly contains a subject path.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(serialized, encoding="utf-8", newline="\n")
    return payload


def _evaluate_subject(
    label: str,
    path: Path,
    *,
    data_directory: Path,
    repeats: int,
    limits: ScanLimits,
    integrity_limits: IntegrityLimits,
    integrity_excludes: Sequence[str],
) -> dict[str, Any]:
    before_manifest = _build_integrity_manifest(
        path,
        limits=integrity_limits,
        configured_excludes=integrity_excludes,
    )
    _require_complete_manifest(before_manifest, phase="before")
    service = RepositoryReviewService(data_directory=data_directory, limits=limits)
    evidences = []
    elapsed_ms: list[float] = []
    peak_bytes: list[int] = []
    phase_sequences: list[list[str]] = []
    for _ in range(repeats):
        phases: list[str] = []
        tracemalloc.start()
        started = time.perf_counter()
        evidence = service.analyze(
            path,
            progress=lambda update: (
                phases.append(update.phase) if not phases or phases[-1] != update.phase else None
            ),
        )
        elapsed_ms.append((time.perf_counter() - started) * 1_000)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_bytes.append(peak)
        phase_sequences.append(phases)
        evidences.append(evidence)
    after_manifest = _build_integrity_manifest(
        path,
        limits=integrity_limits,
        configured_excludes=integrity_excludes,
    )
    _require_complete_manifest(after_manifest, phase="after")
    integrity_equal = _integrity_manifests_equal(before_manifest, after_manifest)
    evidence = evidences[-1]
    relationship_statuses = Counter(item.resolution_status for item in evidence.relationships)
    unresolved = relationship_statuses["ambiguous"] + relationship_statuses["unresolved-dynamic"]
    relationship_total = len(evidence.relationships)
    dependency_cycles = [item for item in evidence.cycles if item.relationship_type == "imports"]
    neighborhood = _largest_bounded_neighborhood(service, evidence)
    family_counts = Counter(item.family for item in evidence.findings)
    finding_summary = service.finding_summary(evidence.snapshot.snapshot_id)

    comparison_started = time.perf_counter()
    comparison = service.comparison_summary(
        evidence.snapshot.snapshot_id,
        evidence.snapshot.snapshot_id,
    )
    comparison_latency_ms = (time.perf_counter() - comparison_started) * 1_000
    comparison_bytes = len(json.dumps(comparison, separators=(",", ":"), sort_keys=True).encode("utf-8"))

    selected_findings = tuple(
        item.finding_id for item in sorted(evidence.findings, key=lambda item: item.finding_id)[:5]
    )
    selection = HandoffSelection(
        target_snapshot_id=evidence.snapshot.snapshot_id,
        baseline_snapshot_id=evidence.snapshot.snapshot_id,
        comparison_id=str(comparison["identity"]["comparison_id"]),
        enabled_sections=("comparison", "findings", "task-objective"),
        selected_delta_ids=(),
        selected_finding_ids=selected_findings,
        selected_cycle_ids=(),
        include_current_review_status=True,
        explicit_review_note_finding_ids=(),
        task_objective="Review the bounded public dogfood evidence.",
    )
    handoff_started = time.perf_counter()
    preview = service.preview_handoff(selection)
    handoff_latency_ms = (time.perf_counter() - handoff_started) * 1_000
    saved = service.save_handoff(selection)
    reopened = service.get_handoff(str(saved["handoff_id"]))
    return {
        "label": label,
        "scan": {
            "elapsed_ms": _round_series(elapsed_ms),
            "median_elapsed_ms": round(statistics.median(elapsed_ms), 3),
            "tracemalloc_peak_bytes": peak_bytes,
            "median_tracemalloc_peak_bytes": int(statistics.median(peak_bytes)),
            "files_discovered": evidence.snapshot.file_count,
            "files_analyzed": evidence.snapshot.included_file_count,
            "files_excluded": evidence.snapshot.file_count - evidence.snapshot.included_file_count,
            "modules": evidence.snapshot.module_count,
            "symbols": evidence.snapshot.symbol_count,
            "relationships": len(evidence.relationships),
            "cycles": len(evidence.cycles),
            "metrics": len(evidence.metrics),
            "findings": len(evidence.findings),
            "parse_gaps": evidence.snapshot.parse_gap_count,
            "truncated": evidence.snapshot.truncated,
            "lifecycle_reconciled": bool(finding_summary["lifecycle_reconciled"]),
            "reconciliation_complete": bool(finding_summary["reconciliation_complete"]),
            "reconciliation_skip_reason": finding_summary["reconciliation_skip_reason"],
            "progress_phase_sequences": phase_sequences,
        },
        "relationships": {
            "resolution_statuses": dict(sorted(relationship_statuses.items())),
            "unresolved_or_ambiguous_ratio": (
                round(unresolved / relationship_total, 6) if relationship_total else 0.0
            ),
            "largest_dependency_cycle": max(
                (len(item.member_node_ids) for item in dependency_cycles),
                default=0,
            ),
            "largest_bounded_graph": neighborhood,
        },
        "findings": {
            "by_family": dict(sorted(family_counts.items())),
            "bounded_review_sample_size": min(len(evidence.findings), _MAX_FINDING_SAMPLE),
        },
        "persistence": {
            "repeated_snapshot_identity_equal": len({item.snapshot.snapshot_id for item in evidences}) == 1,
            "repeated_canonical_bytes_equal": len(
                {hashlib.sha256(item.canonical_bytes()).hexdigest() for item in evidences}
            )
            == 1,
            "repository_bytes_unchanged": integrity_equal,
            "recent_repository_count": len(service.list_repositories()),
        },
        "integrity": {
            "format_version": INTEGRITY_MANIFEST_FORMAT_VERSION,
            "mode": before_manifest.mode,
            "complete": before_manifest.complete and after_manifest.complete,
            "before_digest": before_manifest.digest,
            "after_digest": after_manifest.digest,
            "equal": integrity_equal,
            "inclusion_metadata_equal": (
                before_manifest.included_file_count == after_manifest.included_file_count
                and before_manifest.included_byte_count == after_manifest.included_byte_count
                and before_manifest.excluded_counts == after_manifest.excluded_counts
                and before_manifest.mode == after_manifest.mode
            ),
            "included_files": {
                "before": before_manifest.included_file_count,
                "after": after_manifest.included_file_count,
            },
            "included_bytes": {
                "before": before_manifest.included_byte_count,
                "after": after_manifest.included_byte_count,
            },
            "excluded_counts": {
                "before": before_manifest.exclusion_counts_dict(),
                "after": after_manifest.exclusion_counts_dict(),
            },
            "limits": integrity_limits.sanitized(),
            "failure_reason": None,
        },
        "comparison": {
            "equal_snapshots": bool(comparison["equal_snapshots"]),
            "summary_latency_ms": round(comparison_latency_ms, 3),
            "response_bytes": comparison_bytes,
            "counts": comparison["counts"],
        },
        "handoff": {
            "selected_sections": 3,
            "selected_items": len(selected_findings),
            "markdown_characters": int(preview["markdown_character_count"]),
            "json_bytes": int(preview["json_byte_count"]),
            "render_latency_ms": round(handoff_latency_ms, 3),
            "truncated": bool(preview["truncated"]),
            "omitted_counts": preview["omitted_counts"],
            "saved_reopened_integrity": (
                reopened["rendered_digest"] == saved["rendered_digest"]
                and reopened["markdown"] == saved["markdown"]
                and reopened["normalized_json"] == saved["normalized_json"]
            ),
        },
    }


def _largest_bounded_neighborhood(
    service: RepositoryReviewService,
    evidence: Any,
) -> dict[str, Any]:
    module_ids = sorted(item.node_id for item in evidence.graph_nodes if item.node_type == "module")[
        :_MAX_NEIGHBORHOOD_FOCUSES
    ]
    largest = {
        "nodes": 0,
        "relationships": 0,
        "response_bytes": 0,
        "latency_ms": 0.0,
        "truncated": False,
    }
    for focus_id in module_ids:
        started = time.perf_counter()
        response = service.relationship_neighborhood(
            evidence.snapshot.snapshot_id,
            focus_id=focus_id,
            mode="modules",
            depth=3,
            max_nodes=_NEIGHBORHOOD_MAX_NODES,
            max_edges=_NEIGHBORHOOD_MAX_EDGES,
        )
        latency_ms = (time.perf_counter() - started) * 1_000
        response_bytes = len(json.dumps(response, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        candidate = {
            "nodes": len(response["nodes"]),
            "relationships": len(response["relationships"]),
            "response_bytes": response_bytes,
            "latency_ms": round(latency_ms, 3),
            "truncated": bool(response["truncated"]),
        }
        if (candidate["response_bytes"], candidate["nodes"]) > (
            largest["response_bytes"],
            largest["nodes"],
        ):
            largest = candidate
    return largest


def _normalize_subjects(
    subjects: tuple[tuple[str, Path], ...],
) -> tuple[tuple[str, Path], ...]:
    if not subjects:
        raise ValueError("At least one subject is required.")
    labels: set[str] = set()
    normalized: list[tuple[str, Path]] = []
    for label, path in subjects:
        if not _LABEL_PATTERN.fullmatch(label):
            raise ValueError("Subject labels must be anonymous lowercase slugs.")
        if label in labels:
            raise ValueError("Subject labels must be unique.")
        resolved = path.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError("Subject path must be a directory.")
        labels.add(label)
        normalized.append((label, resolved))
    return tuple(normalized)


def _require_external_path(
    candidate: Path,
    subjects: tuple[tuple[str, Path], ...],
    *,
    kind: str,
) -> None:
    resolved = candidate.resolve()
    discovery = RepositoryDiscovery()
    analysis_roots = tuple(Path(discovery.resolve_scope(root).analysis_root) for _, root in subjects)
    if any(resolved == root or resolved.is_relative_to(root) for root in analysis_roots):
        raise ValueError(f"Evaluation {kind} must be outside every analyzed repository.")


def _require_complete_manifest(manifest: IntegrityManifestResult, *, phase: str) -> None:
    if manifest.complete:
        return
    reason = manifest.failure_reason or "unknown-bounded-failure"
    raise ValueError(f"Integrity manifest {phase} phase incomplete: {reason}.")


def _integrity_manifests_equal(
    before: IntegrityManifestResult,
    after: IntegrityManifestResult,
) -> bool:
    return bool(
        before.complete
        and after.complete
        and before.format_version == after.format_version
        and before.mode == after.mode
        and before.digest == after.digest
        and before.included_file_count == after.included_file_count
        and before.included_byte_count == after.included_byte_count
        and before.excluded_counts == after.excluded_counts
    )


def _round_series(values: list[float]) -> list[float]:
    return [round(value, 3) for value in values]


def _write_medium(root: Path) -> None:
    package = root / "fixture"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Public medium fixture."""\n', encoding="utf-8")
    for module_index in range(30):
        previous = (module_index - 1) % 30
        lines = [f"from . import module_{previous:03d}\n\n"]
        for symbol_index in range(12):
            lines.extend(
                (
                    f"class Type{symbol_index:02d}:\n",
                    f"    peer: 'module_{previous:03d}.Type{symbol_index:02d}'\n",
                    "    pass\n\n",
                )
            )
        (package / f"module_{module_index:03d}.py").write_text(
            "".join(lines),
            encoding="utf-8",
        )


def _write_large(root: Path) -> None:
    package = root / "application"
    package.mkdir(parents=True)
    (root / ".gitignore").write_text("generated/\n", encoding="utf-8")
    (package / "__init__.py").write_text('"""Public large fixture."""\n', encoding="utf-8")
    for module_index in range(120):
        next_module = (module_index + 1) % 120
        lines = [f"from . import module_{next_module:03d}\n\n"]
        for symbol_index in range(10):
            lines.extend(
                (
                    f"def operation_{symbol_index:02d}(value: int) -> int:\n",
                    f"    return value + {symbol_index}\n\n",
                )
            )
        (package / f"module_{module_index:03d}.py").write_text(
            "".join(lines),
            encoding="utf-8",
        )
    generated = root / "generated"
    generated.mkdir()
    for index in range(200):
        (generated / f"generated_{index:03d}.py").write_text(
            "raise RuntimeError('excluded generated content')\n",
            encoding="utf-8",
        )


def _write_multipackage(root: Path) -> None:
    for package_index, package_name in enumerate(("api", "domain", "worker")):
        package = root / package_name
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            f'"""{package_name} public package."""\n',
            encoding="utf-8",
        )
        dependency = ("domain", "worker", "api")[package_index]
        for module_index in range(12):
            lines = [f"from {dependency} import module_{module_index:02d}\n\n"]
            for symbol_index in range(6):
                lines.extend(
                    (
                        f"class Component{symbol_index:02d}:\n",
                        f"    dependency: module_{module_index:02d}.Component{symbol_index:02d}\n",
                        "    pass\n\n",
                    )
                )
            (package / f"module_{module_index:02d}.py").write_text(
                "".join(lines),
                encoding="utf-8",
            )


def _write_partial(root: Path) -> None:
    root.mkdir(parents=True)
    for index in range(12):
        (root / f"module_{index:02d}.py").write_text(
            f"def public_{index:02d}():\n    return {index}\n",
            encoding="utf-8",
        )
    (root / "malformed.py").write_text("def broken(:\n", encoding="utf-8")


def _write_cycles_repeated(root: Path) -> None:
    for package_name, peer_name in (("alpha", "beta"), ("beta", "alpha")):
        package = root / package_name
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            f"from . import first\nfrom . import second\nfrom {peer_name} import first as peer\n",
            encoding="utf-8",
        )
        (package / "first.py").write_text(
            "from . import second\n\nclass Shared:\n    pass\n",
            encoding="utf-8",
        )
        (package / "second.py").write_text(
            "from . import first\n\nclass Shared:\n    pass\n",
            encoding="utf-8",
        )


def _parse_subject(value: str) -> tuple[str, Path]:
    label, separator, path = value.partition("=")
    if not separator or not path:
        raise argparse.ArgumentTypeError("Subjects use LABEL=PATH.")
    return label, Path(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="Generate public dogfood fixtures.")
    generate.add_argument("--root", type=Path, required=True)
    evaluate = subparsers.add_parser("evaluate", help="Evaluate one or more repositories.")
    evaluate.add_argument("--subject", type=_parse_subject, action="append", required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--data-directory", type=Path, required=True)
    evaluate.add_argument("--repeat", type=int, default=2)
    evaluate.add_argument("--max-files", type=int, default=5_000)
    evaluate.add_argument("--max-file-size-bytes", type=int, default=1_000_000)
    evaluate.add_argument("--max-total-bytes", type=int, default=100_000_000)
    evaluate.add_argument("--integrity-max-files", type=int, default=50_000)
    evaluate.add_argument("--integrity-max-path-entries", type=int, default=50_000)
    evaluate.add_argument(
        "--integrity-max-file-size-bytes",
        type=int,
        default=256 * 1024 * 1024,
    )
    evaluate.add_argument(
        "--integrity-max-total-bytes",
        type=int,
        default=2 * 1024 * 1024 * 1024,
    )
    evaluate.add_argument(
        "--integrity-max-path-listing-bytes",
        type=int,
        default=64 * 1024 * 1024,
    )
    evaluate.add_argument(
        "--integrity-exclude",
        action="append",
        default=[],
        help="Add an explicit repository-relative integrity exclusion pattern.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "generate":
        subjects = generate_public_fixtures(args.root)
        print("Generated public fixtures: " + ", ".join(label for label, _ in subjects))
        return 0
    subjects = tuple(args.subject)
    evaluate_subjects(
        subjects,
        output_path=args.output,
        data_directory=args.data_directory,
        repeats=args.repeat,
        limits=ScanLimits(
            max_files=args.max_files,
            max_file_size_bytes=args.max_file_size_bytes,
            max_total_bytes=args.max_total_bytes,
        ),
        integrity_limits=IntegrityLimits(
            maximum_files=args.integrity_max_files,
            maximum_path_entries=args.integrity_max_path_entries,
            maximum_file_size_bytes=args.integrity_max_file_size_bytes,
            maximum_total_bytes=args.integrity_max_total_bytes,
            maximum_path_listing_bytes=args.integrity_max_path_listing_bytes,
        ),
        integrity_excludes=tuple(args.integrity_exclude),
    )
    print(f"Wrote sanitized dogfood results for {len(subjects)} subject(s) to {args.output.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
