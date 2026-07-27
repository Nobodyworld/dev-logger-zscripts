"""Immutable contracts for the experimental repository review workspace."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, cast

ANALYZER_VERSION = "3"
SCHEMA_VERSION = "3"
RULE_SET_VERSION = "4"


class AnalysisState(StrEnum):
    """Lifecycle states shared by scans and stored snapshots."""

    STARTED = "started"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ScanLimits:
    """Resource limits applied before any target source is parsed."""

    max_files: int = 5_000
    max_file_size_bytes: int = 1_000_000
    max_total_bytes: int = 100_000_000
    max_source_lines: int = 200
    max_source_bytes: int = 16_384

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if int(value) <= 0:
                raise ValueError(f"{name} must be greater than zero.")


@dataclass(frozen=True, slots=True)
class RepositoryRecord:
    """A local repository identity and its observed Git/configuration state."""

    repository_id: str
    display_name: str
    canonical_path: str
    git_root: str | None
    branch: str | None
    git_sha: str | None
    dirty: bool
    staged: bool
    untracked: bool
    configuration_digest: str
    source_roots: tuple[str, ...] = ()
    test_roots: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SnapshotRecord:
    """Versioned summary for one completed or interrupted analysis attempt."""

    snapshot_id: str
    repository_id: str
    analyzer_version: str
    schema_version: str
    rule_set_version: str
    state: AnalysisState
    source_fingerprint: str
    file_count: int
    included_file_count: int
    module_count: int
    symbol_count: int
    started_at: str
    completed_at: str | None
    duration_ms: int
    truncated: bool
    parse_gap_count: int


@dataclass(frozen=True, slots=True)
class FileRecord:
    """Metadata-only evidence for one discovered repository file."""

    file_id: str
    relative_path: str
    content_hash: str | None
    language: str
    size_bytes: int
    included: bool
    exclusion_reason: str | None
    parse_status: str


@dataclass(frozen=True, slots=True)
class ImportRecord:
    """An unresolved import statement extracted from Python syntax."""

    module: str | None
    imported_name: str | None
    alias: str | None
    level: int
    line: int = 1
    column: int = 0


@dataclass(frozen=True, slots=True)
class ModuleRecord:
    """A Python module and its statically available public/import evidence."""

    module_id: str
    module_name: str
    package: str
    file_id: str
    relative_path: str
    public_exports: tuple[str, ...]
    imports: tuple[ImportRecord, ...]


@dataclass(frozen=True, slots=True)
class SymbolRecord:
    """A deterministic Python symbol extracted without importing target code."""

    symbol_id: str
    language: str
    kind: str
    qualified_name: str
    display_name: str
    module_name: str
    file_id: str
    relative_path: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    parent_symbol_id: str | None
    visibility: str
    signature: str
    annotations: tuple[str, ...]
    decorators: tuple[str, ...]
    docstring_present: bool
    async_flag: bool
    content_fingerprint: str
    bases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DiagnosticRecord:
    """A bounded, non-sensitive diagnostic produced by static analysis."""

    diagnostic_id: str
    code: str
    severity: str
    message: str
    relative_path: str | None
    line: int | None
    column: int | None
    category: str


@dataclass(frozen=True, slots=True)
class TypeReferenceCandidate:
    """Bounded syntax-only name awaiting deterministic relationship resolution."""

    candidate_id: str
    source_symbol_id: str
    module_name: str
    textual_name: str
    relative_path: str
    line: int
    column: int
    evidence: str
    candidate_kind: str


@dataclass(frozen=True, slots=True)
class GraphNodeRecord:
    """A language-neutral node used by bounded graph queries."""

    node_id: str
    node_type: str
    display_name: str
    qualified_name: str
    relative_path: str | None
    symbol_kind: str | None


@dataclass(frozen=True, slots=True)
class RelationshipRecord:
    """One immutable, source-backed static relationship observation."""

    relationship_id: str
    relationship_type: str
    source_id: str
    target_id: str | None
    unresolved_target: str | None
    resolution_status: str
    confidence: str
    relative_path: str
    line: int
    column: int
    analyzer_version: str
    evidence: str


@dataclass(frozen=True, slots=True)
class CycleGroupRecord:
    """A content-derived strongly connected component with cyclic membership."""

    cycle_id: str
    relationship_type: str
    member_node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MetricRecord:
    """One deterministic raw measurement, independent from finding thresholds."""

    metric_id: str
    subject_id: str
    subject_type: str
    metric_name: str
    numeric_value: float
    unit: str
    analyzer_version: str
    relative_path: str | None
    line: int | None


@dataclass(frozen=True, slots=True)
class FindingEvidenceRecord:
    """Immutable snapshot evidence emitted by one versioned finding rule."""

    finding_id: str
    rule_id: str
    rule_version: str
    family: str
    title: str
    explanation: str
    suggested_action: str
    severity: str
    confidence: str
    subject_type: str
    subject_keys: tuple[str, ...]
    affected_node_ids: tuple[str, ...]
    relative_path: str | None
    line: int | None
    metric_evidence: tuple[tuple[str, float], ...]
    threshold_evidence: tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class FindingLifecycleRecord:
    """Repository-local lifecycle state for stable finding identity."""

    finding_id: str
    repository_id: str
    first_seen_snapshot_id: str
    last_seen_snapshot_id: str
    evidence_state: str
    resolved_snapshot_id: str | None


@dataclass(frozen=True, slots=True)
class ReviewDecisionRecord:
    """Current optimistic-concurrency protected user review decision."""

    finding_id: str
    review_status: str
    note: str
    reason_code: str | None
    version: int
    decided_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ReviewEventRecord:
    """Append-only local audit event for finding lifecycle and review changes."""

    event_id: int
    finding_id: str
    event_type: str
    snapshot_id: str | None
    review_status: str | None
    reason_code: str | None
    note: str
    review_version: int | None
    event_at: str


@dataclass(frozen=True, slots=True)
class AnalysisEvidence:
    """Complete metadata-only evidence promoted atomically to SQLite."""

    repository: RepositoryRecord
    snapshot: SnapshotRecord
    files: tuple[FileRecord, ...]
    modules: tuple[ModuleRecord, ...]
    symbols: tuple[SymbolRecord, ...]
    diagnostics: tuple[DiagnosticRecord, ...]
    graph_nodes: tuple[GraphNodeRecord, ...] = ()
    relationships: tuple[RelationshipRecord, ...] = ()
    cycles: tuple[CycleGroupRecord, ...] = ()
    metrics: tuple[MetricRecord, ...] = ()
    findings: tuple[FindingEvidenceRecord, ...] = ()

    def canonical_payload(self) -> dict[str, Any]:
        """Return the deterministic, path-redacted evidence representation."""

        return {
            "schema_version": SCHEMA_VERSION,
            "repository": {
                "repository_id": self.repository.repository_id,
                "display_name": self.repository.display_name,
                "branch": self.repository.branch,
                "git_sha": self.repository.git_sha,
                "dirty": self.repository.dirty,
                "staged": self.repository.staged,
                "untracked": self.repository.untracked,
                "configuration_digest": self.repository.configuration_digest,
                "source_roots": list(self.repository.source_roots),
                "test_roots": list(self.repository.test_roots),
            },
            "snapshot": {
                "snapshot_id": self.snapshot.snapshot_id,
                "repository_id": self.snapshot.repository_id,
                "analyzer_version": self.snapshot.analyzer_version,
                "schema_version": self.snapshot.schema_version,
                "rule_set_version": self.snapshot.rule_set_version,
                "state": self.snapshot.state.value,
                "source_fingerprint": self.snapshot.source_fingerprint,
                "file_count": self.snapshot.file_count,
                "included_file_count": self.snapshot.included_file_count,
                "module_count": self.snapshot.module_count,
                "symbol_count": self.snapshot.symbol_count,
                "truncated": self.snapshot.truncated,
                "parse_gap_count": self.snapshot.parse_gap_count,
            },
            "files": [_public_dataclass(record) for record in sorted(self.files, key=_file_sort_key)],
            "modules": [_public_dataclass(record) for record in sorted(self.modules, key=_module_sort_key)],
            "symbols": [_public_dataclass(record) for record in sorted(self.symbols, key=_symbol_sort_key)],
            "diagnostics": [
                _public_dataclass(record) for record in sorted(self.diagnostics, key=_diagnostic_sort_key)
            ],
            "graph_nodes": [
                _public_dataclass(record)
                for record in sorted(self.graph_nodes, key=lambda item: item.node_id)
            ],
            "relationships": [
                _public_dataclass(record) for record in sorted(self.relationships, key=_relationship_sort_key)
            ],
            "cycles": [
                _public_dataclass(record) for record in sorted(self.cycles, key=lambda item: item.cycle_id)
            ],
            "metrics": [
                _public_dataclass(record)
                for record in sorted(self.metrics, key=lambda item: (item.subject_id, item.metric_name))
            ],
            "findings": [
                _public_dataclass(record)
                for record in sorted(self.findings, key=lambda item: item.finding_id)
            ],
        }

    def canonical_bytes(self) -> bytes:
        """Serialize normalized evidence with sorted keys and LF termination."""

        return canonical_json_bytes(self.canonical_payload())


def canonical_json_bytes(payload: object) -> bytes:
    """Serialize a JSON-compatible value deterministically."""

    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def stable_digest(namespace: str, payload: object) -> str:
    """Return a namespaced SHA-256 identifier for canonical content."""

    digest = hashlib.sha256()
    digest.update(namespace.encode("utf-8"))
    digest.update(b"\0")
    digest.update(canonical_json_bytes(payload))
    return digest.hexdigest()


def _public_dataclass(
    record: (
        FileRecord
        | ModuleRecord
        | SymbolRecord
        | DiagnosticRecord
        | GraphNodeRecord
        | RelationshipRecord
        | CycleGroupRecord
        | MetricRecord
        | FindingEvidenceRecord
    ),
) -> dict[str, Any]:
    payload = asdict(record)
    return cast(dict[str, Any], _normalize(payload))


def _normalize(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _file_sort_key(record: FileRecord) -> tuple[str, str]:
    return (record.relative_path, record.file_id)


def _module_sort_key(record: ModuleRecord) -> tuple[str, str]:
    return (record.module_name, record.module_id)


def _symbol_sort_key(record: SymbolRecord) -> tuple[str, int, str]:
    return (record.relative_path, record.start_line, record.symbol_id)


def _diagnostic_sort_key(record: DiagnosticRecord) -> tuple[str, int, str]:
    return (record.relative_path or "", record.line or 0, record.diagnostic_id)


def _relationship_sort_key(record: RelationshipRecord) -> tuple[str, str, str, str]:
    return (
        record.relationship_type,
        record.source_id,
        record.target_id or record.unresolved_target or "",
        record.relationship_id,
    )


__all__ = [
    "ANALYZER_VERSION",
    "RULE_SET_VERSION",
    "SCHEMA_VERSION",
    "AnalysisEvidence",
    "AnalysisState",
    "CycleGroupRecord",
    "DiagnosticRecord",
    "FileRecord",
    "FindingEvidenceRecord",
    "FindingLifecycleRecord",
    "GraphNodeRecord",
    "ImportRecord",
    "MetricRecord",
    "ModuleRecord",
    "RelationshipRecord",
    "RepositoryRecord",
    "ReviewDecisionRecord",
    "ReviewEventRecord",
    "ScanLimits",
    "SnapshotRecord",
    "SymbolRecord",
    "TypeReferenceCandidate",
    "canonical_json_bytes",
    "stable_digest",
]
