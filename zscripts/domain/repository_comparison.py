"""Immutable contracts for deterministic snapshot comparison and local handoffs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

COMPARISON_FORMAT_VERSION = "2"
HANDOFF_FORMAT_VERSION = "2"

Scalar = str | int | float | bool | None
FieldPairs = tuple[tuple[str, Scalar], ...]


@dataclass(frozen=True, slots=True)
class ComparisonIdentity:
    """Content-derived identity for one bounded transient comparison."""

    comparison_id: str
    repository_id: str
    baseline_snapshot_id: str
    target_snapshot_id: str
    comparison_format_version: str


@dataclass(frozen=True, slots=True)
class ComparisonSectionCompatibility:
    """Compatibility result for one immutable evidence section."""

    section: str
    status: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComparisonCompatibility:
    """Version and partial-evidence information for a snapshot pair."""

    same_repository: bool
    baseline_analyzer_version: str
    target_analyzer_version: str
    baseline_schema_version: str
    target_schema_version: str
    baseline_rule_set_version: str
    target_rule_set_version: str
    baseline_truncated: bool
    target_truncated: bool
    baseline_parse_gap_count: int
    target_parse_gap_count: int
    baseline_lifecycle_reconciled: bool
    target_lifecycle_reconciled: bool
    baseline_reconciliation_skip_reason: str | None
    target_reconciliation_skip_reason: str | None
    sections: tuple[ComparisonSectionCompatibility, ...]


@dataclass(frozen=True, slots=True)
class FileDelta:
    """Logical file delta keyed by repository-relative path."""

    delta_id: str
    change_type: str
    logical_key: str
    label: str
    relative_path: str
    baseline: FieldPairs | None
    target: FieldPairs | None


@dataclass(frozen=True, slots=True)
class SymbolDelta:
    """Logical symbol delta keyed by language, kind, and qualified name."""

    delta_id: str
    change_type: str
    logical_key: str
    label: str
    relative_path: str | None
    baseline: FieldPairs | None
    target: FieldPairs | None


@dataclass(frozen=True, slots=True)
class RelationshipDelta:
    """Logical relationship delta independent from snapshot-specific node IDs."""

    delta_id: str
    change_type: str
    logical_key: str
    label: str
    relative_path: str | None
    relationship_type: str
    source: str
    target_name: str
    baseline: FieldPairs | None
    target_evidence: FieldPairs | None


@dataclass(frozen=True, slots=True)
class CycleDelta:
    """Logical cycle delta keyed by type and sorted member names."""

    delta_id: str
    change_type: str
    logical_key: str
    label: str
    relationship_type: str
    members: tuple[str, ...]
    baseline_cycle_id: str | None
    target_cycle_id: str | None


@dataclass(frozen=True, slots=True)
class MetricDelta:
    """Logical metric delta with neutral numeric direction."""

    delta_id: str
    change_type: str
    logical_key: str
    label: str
    relative_path: str | None
    subject: str
    metric_name: str
    unit: str
    baseline_value: float | None
    target_value: float | None
    absolute_delta: float | None
    direction: str
    percentage_delta: float | None


@dataclass(frozen=True, slots=True)
class FindingOccurrenceDelta:
    """Immutable occurrence delta, separate from mutable current review state."""

    delta_id: str
    change_type: str
    logical_key: str
    label: str
    relative_path: str | None
    rule_id: str
    subject_keys: tuple[str, ...]
    baseline_finding_id: str | None
    target_finding_id: str | None
    baseline_rule_version: str | None
    target_rule_version: str | None
    occurrence_state: str


ComparisonDelta = (
    FileDelta | SymbolDelta | RelationshipDelta | CycleDelta | MetricDelta | FindingOccurrenceDelta
)


@dataclass(frozen=True, slots=True)
class ComparisonSummary:
    """Bounded factual summary for one transient comparison."""

    identity: ComparisonIdentity
    compatibility: ComparisonCompatibility
    counts: tuple[tuple[str, int], ...]
    equal_snapshots: bool


@dataclass(frozen=True, slots=True)
class HandoffBudgetPolicy:
    """Versioned hard limits for deterministic handoff rendering."""

    maximum_selected_sections: int = 8
    maximum_items_per_section: int = 50
    maximum_selected_findings: int = 50
    maximum_explicit_notes: int = 20
    maximum_note_length: int = 1_000
    maximum_markdown_characters: int = 100_000
    maximum_json_bytes: int = 500_000
    maximum_objective_characters: int = 4_000


DEFAULT_HANDOFF_BUDGET = HandoffBudgetPolicy()


def rendered_output_digest(
    format_version: str,
    markdown: str,
    normalized_json: str,
) -> str:
    """Digest the exact final rendered outputs and their format contract."""

    digest = hashlib.sha256()
    digest.update(format_version.encode("utf-8"))
    digest.update(b"\0")
    digest.update(markdown.encode("utf-8"))
    digest.update(b"\0")
    digest.update(normalized_json.encode("utf-8"))
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class HandoffSelection:
    """User-selected bounded evidence for one pure handoff render."""

    target_snapshot_id: str
    baseline_snapshot_id: str | None
    comparison_id: str | None
    enabled_sections: tuple[str, ...]
    selected_delta_ids: tuple[str, ...]
    selected_finding_ids: tuple[str, ...]
    selected_cycle_ids: tuple[str, ...]
    include_current_review_status: bool
    explicit_review_note_finding_ids: tuple[str, ...]
    task_objective: str
    budget_policy: HandoffBudgetPolicy = DEFAULT_HANDOFF_BUDGET


@dataclass(frozen=True, slots=True)
class HandoffRenderResult:
    """Deterministic Markdown and normalized JSON handoff output."""

    handoff_format_version: str
    markdown: str
    normalized_json: str
    rendered_digest: str
    truncated: bool
    omitted_counts: tuple[tuple[str, int], ...]
    warnings: tuple[str, ...]
    markdown_character_count: int
    json_byte_count: int


@dataclass(frozen=True, slots=True)
class SavedHandoffRecord:
    """Immutable local saved handoff record outside snapshot evidence."""

    handoff_id: str
    repository_id: str
    target_snapshot_id: str
    baseline_snapshot_id: str | None
    comparison_id: str | None
    selection_json: str
    task_objective: str
    format_version: str
    rendered_digest: str
    rendered_markdown: str
    rendered_json: str
    created_at: str
    updated_at: str
    local_only: bool = True


__all__ = [
    "COMPARISON_FORMAT_VERSION",
    "DEFAULT_HANDOFF_BUDGET",
    "HANDOFF_FORMAT_VERSION",
    "ComparisonCompatibility",
    "ComparisonDelta",
    "ComparisonIdentity",
    "ComparisonSectionCompatibility",
    "ComparisonSummary",
    "CycleDelta",
    "FileDelta",
    "FindingOccurrenceDelta",
    "HandoffBudgetPolicy",
    "HandoffRenderResult",
    "HandoffSelection",
    "MetricDelta",
    "RelationshipDelta",
    "SavedHandoffRecord",
    "SymbolDelta",
    "rendered_output_digest",
]
