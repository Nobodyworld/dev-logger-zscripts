"""Run sanitized, reproducible dogfood measurements for Repository Review."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import time
import tracemalloc
from collections import Counter
from pathlib import Path
from typing import Any

from zscripts.application.repository_review import RepositoryReviewService
from zscripts.domain.repository_comparison import HandoffSelection
from zscripts.domain.repository_review import ScanLimits

_LABEL_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_MAX_FINDING_SAMPLE = 20
_MAX_NEIGHBORHOOD_FOCUSES = 5
_NEIGHBORHOOD_MAX_NODES = 40
_NEIGHBORHOOD_MAX_EDGES = 80


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
) -> dict[str, Any]:
    """Evaluate subjects through application services and write sanitized JSON."""

    if repeats < 2 or repeats > 5:
        raise ValueError("Repeat count must be between 2 and 5.")
    normalized = _normalize_subjects(subjects)
    _require_external_path(output_path, normalized, kind="output")
    _require_external_path(data_directory, normalized, kind="data directory")
    data_directory.mkdir(parents=True, exist_ok=True)
    results = [
        _evaluate_subject(
            label,
            path,
            data_directory=data_directory / label,
            repeats=repeats,
            limits=limits,
        )
        for label, path in normalized
    ]
    payload: dict[str, Any] = {
        "format_version": 1,
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
) -> dict[str, Any]:
    before_digest = _tree_digest(path)
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
    after_digest = _tree_digest(path)
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
            "repository_bytes_unchanged": before_digest == after_digest,
            "recent_repository_count": len(service.list_repositories()),
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
    if any(resolved == root or resolved.is_relative_to(root) for _, root in subjects):
        raise ValueError(f"Evaluation {kind} must be outside every analyzed repository.")


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for directory, names, files in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        names[:] = sorted(name for name in names if name != ".git")
        for name in sorted(files):
            path = directory_path / name
            relative = path.relative_to(root).as_posix()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            if path.is_symlink():
                digest.update(os.readlink(path).encode("utf-8", errors="replace"))
            else:
                digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


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
    )
    print(f"Wrote sanitized dogfood results for {len(subjects)} subject(s) to {args.output.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
