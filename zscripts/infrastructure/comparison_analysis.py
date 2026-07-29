"""Deterministic transient comparison of immutable repository snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from zscripts.domain.repository_comparison import (
    COMPARISON_FORMAT_VERSION,
    ComparisonCompatibility,
    ComparisonDelta,
    ComparisonIdentity,
    ComparisonSectionCompatibility,
    ComparisonSummary,
    CycleDelta,
    FieldPairs,
    FileDelta,
    FindingOccurrenceDelta,
    MetricDelta,
    RelationshipDelta,
    Scalar,
    SymbolDelta,
)
from zscripts.domain.repository_review import (
    FileRecord,
    FindingEvidenceRecord,
    GraphNodeRecord,
    MetricRecord,
    RelationshipRecord,
    SymbolRecord,
    stable_digest,
)
from zscripts.infrastructure.snapshot_store import ComparisonSnapshotEvidence

COMPARISON_SECTIONS = ("files", "symbols", "relationships", "cycles", "metrics", "findings")
COMPARISON_CHANGE_TYPES = (
    "added",
    "removed",
    "not-observed-in-baseline",
    "not-observed-in-target",
    "changed",
)
_SECTION_MINIMUM_SCHEMA = {
    "files": 1,
    "symbols": 1,
    "relationships": 2,
    "cycles": 2,
    "metrics": 3,
    "findings": 3,
}


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """Complete deterministic result before API filtering and pagination."""

    summary: ComparisonSummary
    files: tuple[FileDelta, ...]
    symbols: tuple[SymbolDelta, ...]
    relationships: tuple[RelationshipDelta, ...]
    cycles: tuple[CycleDelta, ...]
    metrics: tuple[MetricDelta, ...]
    findings: tuple[FindingOccurrenceDelta, ...]

    def section(self, name: str) -> tuple[ComparisonDelta, ...]:
        if name not in COMPARISON_SECTIONS:
            raise ValueError("Unsupported comparison section.")
        return tuple(getattr(self, name))


def compare_snapshots(
    baseline: ComparisonSnapshotEvidence,
    target: ComparisonSnapshotEvidence,
) -> ComparisonResult:
    """Compare exact stored evidence without regenerating either snapshot."""

    if baseline.snapshot.repository_id != target.snapshot.repository_id:
        raise ValueError("Snapshots belong to different repositories.")
    identity = ComparisonIdentity(
        comparison_id=stable_digest(
            "repository-comparison",
            {
                "repository_id": baseline.snapshot.repository_id,
                "baseline_snapshot_id": baseline.snapshot.snapshot_id,
                "target_snapshot_id": target.snapshot.snapshot_id,
                "comparison_format_version": COMPARISON_FORMAT_VERSION,
            },
        ),
        repository_id=baseline.snapshot.repository_id,
        baseline_snapshot_id=baseline.snapshot.snapshot_id,
        target_snapshot_id=target.snapshot.snapshot_id,
        comparison_format_version=COMPARISON_FORMAT_VERSION,
    )
    compatibility = _compatibility(baseline, target)
    section_compatibility = {item.section: item for item in compatibility.sections}

    files = (
        _file_deltas(
            baseline.files,
            target.files,
            **_absence_uncertainty(section_compatibility["files"]),
        )
        if section_compatibility["files"].status != "unavailable"
        else ()
    )
    symbols = (
        _symbol_deltas(
            baseline.symbols,
            target.symbols,
            **_absence_uncertainty(section_compatibility["symbols"]),
        )
        if section_compatibility["symbols"].status != "unavailable"
        else ()
    )
    relationships = (
        _relationship_deltas(
            baseline,
            target,
            **_absence_uncertainty(section_compatibility["relationships"]),
        )
        if section_compatibility["relationships"].status != "unavailable"
        else ()
    )
    cycles = (
        _cycle_deltas(
            baseline,
            target,
            **_absence_uncertainty(section_compatibility["cycles"]),
        )
        if section_compatibility["cycles"].status != "unavailable"
        else ()
    )
    metrics = (
        _metric_deltas(
            baseline,
            target,
            **_absence_uncertainty(section_compatibility["metrics"]),
        )
        if section_compatibility["metrics"].status != "unavailable"
        else ()
    )
    findings = (
        _finding_deltas(
            baseline.findings,
            target.findings,
            **_absence_uncertainty(section_compatibility["findings"]),
        )
        if section_compatibility["findings"].status != "unavailable"
        else ()
    )
    section_items: dict[str, tuple[ComparisonDelta, ...]] = {
        "files": files,
        "symbols": symbols,
        "relationships": relationships,
        "cycles": cycles,
        "metrics": metrics,
        "findings": findings,
    }
    counts: list[tuple[str, int]] = []
    for section in COMPARISON_SECTIONS:
        items = section_items[section]
        for change_type in COMPARISON_CHANGE_TYPES:
            counts.append(
                (
                    f"{section}_{change_type.replace('-', '_')}",
                    sum(item.change_type == change_type for item in items),
                )
            )
    summary = ComparisonSummary(
        identity=identity,
        compatibility=compatibility,
        counts=tuple(counts),
        equal_snapshots=baseline.snapshot.snapshot_id == target.snapshot.snapshot_id,
    )
    return ComparisonResult(
        summary=summary,
        files=files,
        symbols=symbols,
        relationships=relationships,
        cycles=cycles,
        metrics=metrics,
        findings=findings,
    )


def comparison_delta_payload(delta: ComparisonDelta) -> dict[str, Any]:
    """Return a stable JSON-compatible public delta payload."""

    payload = asdict(delta)
    if "baseline" in payload and payload["baseline"] is not None:
        payload["baseline"] = dict(payload["baseline"])
    if "target" in payload and payload["target"] is not None:
        payload["target"] = dict(payload["target"])
    if "target_evidence" in payload:
        target_evidence = payload.pop("target_evidence")
        payload["target"] = dict(target_evidence) if target_evidence is not None else None
    return payload


def comparison_summary_payload(summary: ComparisonSummary) -> dict[str, Any]:
    payload = asdict(summary)
    payload["counts"] = dict(summary.counts)
    return payload


def _compatibility(
    baseline: ComparisonSnapshotEvidence,
    target: ComparisonSnapshotEvidence,
) -> ComparisonCompatibility:
    baseline_schema = _numeric_version(baseline.snapshot.schema_version)
    target_schema = _numeric_version(target.snapshot.schema_version)
    sections: list[ComparisonSectionCompatibility] = []
    for section in COMPARISON_SECTIONS:
        reasons: list[str] = []
        minimum = _SECTION_MINIMUM_SCHEMA[section]
        if baseline_schema < minimum:
            reasons.append("baseline-schema-unsupported")
        if target_schema < minimum:
            reasons.append("target-schema-unsupported")
        if reasons:
            status = "unavailable"
        else:
            if (
                baseline.snapshot.analyzer_version != target.snapshot.analyzer_version
                or baseline.snapshot.schema_version != target.snapshot.schema_version
                or baseline.snapshot.rule_set_version != target.snapshot.rule_set_version
            ):
                reasons.append("version-mismatch")
            if baseline.snapshot.truncated:
                reasons.append("baseline-truncated")
            if target.snapshot.truncated:
                reasons.append("target-truncated")
            if baseline.snapshot.parse_gap_count > 0:
                reasons.append("baseline-parse-gaps")
            if target.snapshot.parse_gap_count > 0:
                reasons.append("target-parse-gaps")
            if section == "findings":
                if not baseline.lifecycle_reconciled:
                    reasons.append("baseline-lifecycle-incomplete")
                if not target.lifecycle_reconciled:
                    reasons.append("target-lifecycle-incomplete")
            status = "partial" if reasons else "supported"
        sections.append(
            ComparisonSectionCompatibility(
                section=section,
                status=status,
                reason_codes=tuple(reasons),
            )
        )
    return ComparisonCompatibility(
        same_repository=True,
        baseline_analyzer_version=baseline.snapshot.analyzer_version,
        target_analyzer_version=target.snapshot.analyzer_version,
        baseline_schema_version=baseline.snapshot.schema_version,
        target_schema_version=target.snapshot.schema_version,
        baseline_rule_set_version=baseline.snapshot.rule_set_version,
        target_rule_set_version=target.snapshot.rule_set_version,
        baseline_truncated=baseline.snapshot.truncated,
        target_truncated=target.snapshot.truncated,
        baseline_parse_gap_count=baseline.snapshot.parse_gap_count,
        target_parse_gap_count=target.snapshot.parse_gap_count,
        baseline_lifecycle_reconciled=baseline.lifecycle_reconciled,
        target_lifecycle_reconciled=target.lifecycle_reconciled,
        baseline_reconciliation_skip_reason=baseline.reconciliation_skip_reason,
        target_reconciliation_skip_reason=target.reconciliation_skip_reason,
        sections=tuple(sections),
    )


def _file_deltas(
    baseline_items: tuple[FileRecord, ...],
    target_items: tuple[FileRecord, ...],
    *,
    baseline_uncertain: bool,
    target_uncertain: bool,
) -> tuple[FileDelta, ...]:
    baseline = {item.relative_path: item for item in baseline_items}
    target = {item.relative_path: item for item in target_items}
    result: list[FileDelta] = []
    for key in sorted(baseline.keys() | target.keys()):
        before = baseline.get(key)
        after = target.get(key)
        before_fields = _file_fields(before) if before is not None else None
        after_fields = _file_fields(after) if after is not None else None
        change_type = _change_type(
            before_fields,
            after_fields,
            baseline_uncertain=baseline_uncertain,
            target_uncertain=target_uncertain,
        )
        if change_type == "unchanged":
            continue
        result.append(
            FileDelta(
                delta_id=_delta_id("files", key, change_type, before_fields, after_fields),
                change_type=change_type,
                logical_key=key,
                label=key,
                relative_path=key,
                baseline=before_fields,
                target=after_fields,
            )
        )
    return tuple(result)


def _symbol_deltas(
    baseline_items: tuple[SymbolRecord, ...],
    target_items: tuple[SymbolRecord, ...],
    *,
    baseline_uncertain: bool,
    target_uncertain: bool,
) -> tuple[SymbolDelta, ...]:
    baseline = {_symbol_key(item): item for item in baseline_items}
    target = {_symbol_key(item): item for item in target_items}
    result: list[SymbolDelta] = []
    for key in sorted(baseline.keys() | target.keys()):
        before = baseline.get(key)
        after = target.get(key)
        before_fields = _symbol_fields(before) if before is not None else None
        after_fields = _symbol_fields(after) if after is not None else None
        change_type = _change_type(
            before_fields,
            after_fields,
            baseline_uncertain=baseline_uncertain,
            target_uncertain=target_uncertain,
        )
        if change_type == "unchanged":
            continue
        representative = after or before
        if representative is None:
            continue
        result.append(
            SymbolDelta(
                delta_id=_delta_id("symbols", key, change_type, before_fields, after_fields),
                change_type=change_type,
                logical_key=key,
                label=representative.qualified_name,
                relative_path=representative.relative_path,
                baseline=before_fields,
                target=after_fields,
            )
        )
    return tuple(result)


def _relationship_deltas(
    baseline: ComparisonSnapshotEvidence,
    target: ComparisonSnapshotEvidence,
    *,
    baseline_uncertain: bool,
    target_uncertain: bool,
) -> tuple[RelationshipDelta, ...]:
    baseline_nodes = {item.node_id: item for item in baseline.graph_nodes}
    target_nodes = {item.node_id: item for item in target.graph_nodes}
    before_groups = _relationship_groups(baseline.relationships, baseline_nodes)
    after_groups = _relationship_groups(target.relationships, target_nodes)
    result: list[RelationshipDelta] = []
    for base_key in sorted(before_groups.keys() | after_groups.keys()):
        before = before_groups.get(base_key, ())
        after = after_groups.get(base_key, ())
        count = max(len(before), len(after))
        for index in range(count):
            before_item = before[index] if index < len(before) else None
            after_item = after[index] if index < len(after) else None
            before_fields = _relationship_fields(before_item) if before_item is not None else None
            after_fields = _relationship_fields(after_item) if after_item is not None else None
            change_type = _change_type(
                before_fields,
                after_fields,
                baseline_uncertain=baseline_uncertain,
                target_uncertain=target_uncertain,
            )
            if change_type == "unchanged":
                continue
            logical_key = f"{base_key}|occurrence:{index + 1}"
            representative = after_item or before_item
            if representative is None:
                continue
            source, target_name = base_key.split("|", 2)[1:]
            result.append(
                RelationshipDelta(
                    delta_id=_delta_id(
                        "relationships",
                        logical_key,
                        change_type,
                        before_fields,
                        after_fields,
                    ),
                    change_type=change_type,
                    logical_key=logical_key,
                    label=f"{source} → {target_name}",
                    relative_path=representative.relative_path,
                    relationship_type=representative.relationship_type,
                    source=source,
                    target_name=target_name,
                    baseline=before_fields,
                    target_evidence=after_fields,
                )
            )
    return tuple(result)


def _cycle_deltas(
    baseline: ComparisonSnapshotEvidence,
    target: ComparisonSnapshotEvidence,
    *,
    baseline_uncertain: bool,
    target_uncertain: bool,
) -> tuple[CycleDelta, ...]:
    before_nodes = {item.node_id: item for item in baseline.graph_nodes}
    after_nodes = {item.node_id: item for item in target.graph_nodes}
    before = {
        _cycle_key(item.relationship_type, item.member_node_ids, before_nodes): item
        for item in baseline.cycles
    }
    after = {
        _cycle_key(item.relationship_type, item.member_node_ids, after_nodes): item for item in target.cycles
    }
    result: list[CycleDelta] = []
    for key in sorted(before | after):
        relationship_type, member_text = key.split("|", 1)
        members = tuple(member_text.split("\x1f")) if member_text else ()
        if key not in before:
            change_type = "not-observed-in-baseline" if baseline_uncertain else "added"
        elif key not in after:
            change_type = "not-observed-in-target" if target_uncertain else "removed"
        else:
            continue
        result.append(
            CycleDelta(
                delta_id=_delta_id("cycles", key, change_type, key in before, key in after),
                change_type=change_type,
                logical_key=key,
                label=" ↔ ".join(members),
                relationship_type=relationship_type,
                members=members,
                baseline_cycle_id=before[key].cycle_id if key in before else None,
                target_cycle_id=after[key].cycle_id if key in after else None,
            )
        )
    return tuple(result)


def _metric_deltas(
    baseline: ComparisonSnapshotEvidence,
    target: ComparisonSnapshotEvidence,
    *,
    baseline_uncertain: bool,
    target_uncertain: bool,
) -> tuple[MetricDelta, ...]:
    before_nodes = {item.node_id: item for item in baseline.graph_nodes}
    after_nodes = {item.node_id: item for item in target.graph_nodes}
    before = {_metric_key(item, before_nodes): item for item in baseline.metrics}
    after = {_metric_key(item, after_nodes): item for item in target.metrics}
    result: list[MetricDelta] = []
    for key in sorted(before.keys() | after.keys()):
        old = before.get(key)
        new = after.get(key)
        if old is not None and new is not None and old.numeric_value == new.numeric_value:
            continue
        if old is None:
            change_type = "not-observed-in-baseline" if baseline_uncertain else "added"
        elif new is None:
            change_type = "not-observed-in-target" if target_uncertain else "removed"
        else:
            change_type = "changed"
        baseline_value = old.numeric_value if old is not None else None
        target_value = new.numeric_value if new is not None else None
        absolute_delta = (
            target_value - baseline_value if target_value is not None and baseline_value is not None else None
        )
        direction = (
            "increase"
            if absolute_delta is not None and absolute_delta > 0
            else "decrease"
            if absolute_delta is not None and absolute_delta < 0
            else "not-comparable"
        )
        percentage = None
        if absolute_delta is not None and baseline_value is not None and baseline_value != 0:
            percentage = (absolute_delta / baseline_value) * 100
        representative = new or old
        if representative is None:
            continue
        subject, metric_name = key.rsplit("|", 1)
        result.append(
            MetricDelta(
                delta_id=_delta_id(
                    "metrics",
                    key,
                    change_type,
                    baseline_value,
                    target_value,
                ),
                change_type=change_type,
                logical_key=key,
                label=f"{subject}: {metric_name}",
                relative_path=representative.relative_path,
                subject=subject,
                metric_name=metric_name,
                unit=representative.unit,
                baseline_value=baseline_value,
                target_value=target_value,
                absolute_delta=absolute_delta,
                direction=direction,
                percentage_delta=percentage,
            )
        )
    return tuple(result)


def _finding_deltas(
    baseline_items: tuple[FindingEvidenceRecord, ...],
    target_items: tuple[FindingEvidenceRecord, ...],
    *,
    baseline_uncertain: bool,
    target_uncertain: bool,
) -> tuple[FindingOccurrenceDelta, ...]:
    baseline = {_finding_key(item): item for item in baseline_items}
    target = {_finding_key(item): item for item in target_items}
    result: list[FindingOccurrenceDelta] = []
    for key in sorted(baseline.keys() | target.keys()):
        old = baseline.get(key)
        new = target.get(key)
        if old is None:
            if baseline_uncertain:
                change_type = "not-observed-in-baseline"
                occurrence = "not-observed-in-baseline"
            else:
                change_type = "added"
                occurrence = "new-in-target"
        elif new is None:
            if target_uncertain:
                change_type = "not-observed-in-target"
                occurrence = "not-observed-in-target"
            else:
                change_type = "removed"
                occurrence = "absent-from-target"
        elif old.rule_version != new.rule_version:
            change_type = "changed"
            occurrence = "rule-version-changed"
        else:
            continue
        representative = new or old
        if representative is None:
            continue
        result.append(
            FindingOccurrenceDelta(
                delta_id=_delta_id(
                    "findings",
                    key,
                    change_type,
                    old.rule_version if old is not None else None,
                    new.rule_version if new is not None else None,
                ),
                change_type=change_type,
                logical_key=key,
                label=representative.title,
                relative_path=representative.relative_path,
                rule_id=representative.rule_id,
                subject_keys=representative.subject_keys,
                baseline_finding_id=old.finding_id if old is not None else None,
                target_finding_id=new.finding_id if new is not None else None,
                baseline_rule_version=old.rule_version if old is not None else None,
                target_rule_version=new.rule_version if new is not None else None,
                occurrence_state=occurrence,
            )
        )
    return tuple(result)


def _file_fields(item: FileRecord) -> FieldPairs:
    fields: dict[str, Scalar] = {
        "content_hash": item.content_hash,
        "language": item.language,
        "size_bytes": item.size_bytes,
        "included": item.included,
        "exclusion_reason": item.exclusion_reason,
        "parse_status": item.parse_status,
    }
    return tuple(sorted(fields.items()))


def _symbol_key(item: SymbolRecord) -> str:
    return f"{item.language}|{item.kind}|{item.qualified_name}"


def _symbol_fields(item: SymbolRecord) -> FieldPairs:
    fields: dict[str, Scalar] = {
        "signature": item.signature,
        "visibility": item.visibility,
        "decorators": "\x1f".join(item.decorators),
        "annotations": "\x1f".join(item.annotations),
        "async_flag": item.async_flag,
        "docstring_present": item.docstring_present,
        "start_line": item.start_line,
        "start_column": item.start_column,
        "end_line": item.end_line,
        "end_column": item.end_column,
        "bases": "\x1f".join(item.bases),
        "content_fingerprint": item.content_fingerprint,
        "relative_path": item.relative_path,
    }
    return tuple(sorted(fields.items()))


def _relationship_groups(
    items: tuple[RelationshipRecord, ...],
    nodes: dict[str, GraphNodeRecord],
) -> dict[str, tuple[RelationshipRecord, ...]]:
    groups: dict[str, list[RelationshipRecord]] = {}
    for item in items:
        source = _node_logical(nodes.get(item.source_id), item.source_id)
        target = (
            _node_logical(nodes.get(item.target_id), item.target_id)
            if item.target_id is not None
            else f"unresolved:{item.unresolved_target}"
        )
        key = f"{item.relationship_type}|{source}|{target}"
        groups.setdefault(key, []).append(item)
    return {
        key: tuple(
            sorted(
                values,
                key=lambda item: (
                    item.relative_path,
                    item.line,
                    item.column,
                    item.resolution_status,
                    item.confidence,
                    item.evidence,
                ),
            )
        )
        for key, values in groups.items()
    }


def _relationship_fields(item: RelationshipRecord) -> FieldPairs:
    fields: dict[str, Scalar] = {
        "resolution_status": item.resolution_status,
        "confidence": item.confidence,
        "relative_path": item.relative_path,
        "line": item.line,
        "column": item.column,
        "evidence": item.evidence,
    }
    return tuple(sorted(fields.items()))


def _node_logical(node: GraphNodeRecord | None, fallback: str | None) -> str:
    if node is None:
        return f"unknown:{fallback or ''}"
    return f"{node.node_type}:{node.qualified_name}:{node.symbol_kind or ''}"


def _cycle_key(
    relationship_type: str,
    member_ids: tuple[str, ...],
    nodes: dict[str, GraphNodeRecord],
) -> str:
    members = sorted(_node_logical(nodes.get(node_id), node_id) for node_id in member_ids)
    member_text = "\x1f".join(members)
    return f"{relationship_type}|{member_text}"


def _metric_key(item: MetricRecord, nodes: dict[str, GraphNodeRecord]) -> str:
    subject = _node_logical(nodes.get(item.subject_id), item.subject_id)
    return f"{subject}|{item.metric_name}"


def _finding_key(item: FindingEvidenceRecord) -> str:
    subject_text = "\x1f".join(sorted(item.subject_keys))
    return f"{item.rule_id}|{item.subject_type}|{subject_text}"


def _change_type(
    baseline: object | None,
    target: object | None,
    *,
    baseline_uncertain: bool,
    target_uncertain: bool,
) -> str:
    if baseline is None:
        return "not-observed-in-baseline" if baseline_uncertain else "added"
    if target is None:
        return "not-observed-in-target" if target_uncertain else "removed"
    return "unchanged" if baseline == target else "changed"


def _absence_uncertainty(
    compatibility: ComparisonSectionCompatibility,
) -> dict[str, bool]:
    reasons = set(compatibility.reason_codes)
    version_mismatch = "version-mismatch" in reasons
    return {
        "baseline_uncertain": version_mismatch
        or "baseline-truncated" in reasons
        or "baseline-parse-gaps" in reasons,
        "target_uncertain": version_mismatch
        or "target-truncated" in reasons
        or "target-parse-gaps" in reasons,
    }


def _delta_id(
    section: str,
    logical_key: str,
    change_type: str,
    baseline: object,
    target: object,
) -> str:
    return stable_digest(
        "comparison-delta",
        {
            "format_version": COMPARISON_FORMAT_VERSION,
            "section": section,
            "logical_key": logical_key,
            "change_type": change_type,
            "baseline": baseline,
            "target": target,
        },
    )


def _numeric_version(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return -1


__all__ = [
    "COMPARISON_SECTIONS",
    "COMPARISON_CHANGE_TYPES",
    "ComparisonResult",
    "compare_snapshots",
    "comparison_delta_payload",
    "comparison_summary_payload",
]
