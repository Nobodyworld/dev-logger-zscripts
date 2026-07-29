"""Pure deterministic rendering for bounded local repository handoffs."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from zscripts.domain.repository_comparison import (
    HANDOFF_FORMAT_VERSION,
    CycleDelta,
    HandoffRenderResult,
    HandoffSelection,
    rendered_output_digest,
)
from zscripts.domain.repository_review import RepositoryRecord
from zscripts.infrastructure.comparison_analysis import (
    COMPARISON_SECTIONS,
    ComparisonResult,
    comparison_delta_payload,
    comparison_summary_payload,
)
from zscripts.infrastructure.snapshot_store import ComparisonSnapshotEvidence, StoredFindingRecord

HANDOFF_SECTIONS = (
    "comparison",
    "files",
    "symbols",
    "relationships",
    "cycles",
    "metrics",
    "findings",
    "task-objective",
)


def render_handoff(
    *,
    selection: HandoffSelection,
    repository: RepositoryRecord,
    target: ComparisonSnapshotEvidence,
    baseline: ComparisonSnapshotEvidence | None,
    comparison: ComparisonResult | None,
    current_findings: tuple[StoredFindingRecord, ...],
) -> HandoffRenderResult:
    """Render stable Markdown and JSON from bounded explicitly selected evidence."""

    budget = selection.budget_policy
    enabled = tuple(dict.fromkeys(selection.enabled_sections))
    if len(enabled) > budget.maximum_selected_sections:
        raise ValueError("Too many handoff sections were selected.")
    if any(item not in HANDOFF_SECTIONS for item in enabled):
        raise ValueError("Unsupported handoff section.")
    if len(selection.task_objective) > budget.maximum_objective_characters:
        raise ValueError("Task objective exceeds the handoff budget.")
    if len(selection.explicit_review_note_finding_ids) > budget.maximum_explicit_notes:
        raise ValueError("Too many review notes were selected.")
    _validate_render_selection(selection, enabled, comparison)

    warnings = _analysis_warnings(target, baseline, comparison)
    omitted: dict[str, int] = {}
    truncated = False
    selected_delta_ids = set(selection.selected_delta_ids)
    selected_cycle_ids = set(selection.selected_cycle_ids)
    changes: dict[str, list[dict[str, Any]]] = {}
    if comparison is not None:
        for section in COMPARISON_SECTIONS:
            if section not in enabled:
                continue
            selected = [
                item
                for item in comparison.section(section)
                if item.delta_id in selected_delta_ids
                or (
                    section == "cycles"
                    and isinstance(item, CycleDelta)
                    and (
                        item.baseline_cycle_id in selected_cycle_ids
                        or item.target_cycle_id in selected_cycle_ids
                    )
                )
            ]
            selected.sort(key=lambda item: (item.logical_key, item.delta_id))
            included = selected[: budget.maximum_items_per_section]
            omitted_count = len(selected) - len(included)
            if omitted_count:
                omitted[section] = omitted_count
                truncated = True
            changes[section] = [comparison_delta_payload(item) for item in included]

    selected_finding_ids = tuple(dict.fromkeys(selection.selected_finding_ids))
    if len(selected_finding_ids) > budget.maximum_selected_findings:
        omitted["findings"] = len(selected_finding_ids) - budget.maximum_selected_findings
        selected_finding_ids = selected_finding_ids[: budget.maximum_selected_findings]
        truncated = True
    selected_finding_set = set(selected_finding_ids)
    note_ids = set(selection.explicit_review_note_finding_ids)
    current_by_id = {
        item.evidence.finding_id: item
        for item in current_findings
        if item.evidence.finding_id in selected_finding_set
    }
    target_occurrences = {item.finding_id: item for item in target.findings}
    finding_payloads: list[dict[str, Any]] = []
    for finding_id in sorted(selected_finding_set):
        current = current_by_id.get(finding_id)
        occurrence = target_occurrences.get(finding_id)
        if current is None and occurrence is None:
            omitted["findings-unavailable"] = omitted.get("findings-unavailable", 0) + 1
            truncated = True
            continue
        if occurrence is not None:
            evidence = occurrence
        elif current is not None:
            evidence = current.evidence
        else:
            continue
        finding_payload: dict[str, Any] = {
            "finding_id": finding_id,
            "title": evidence.title,
            "family": evidence.family,
            "severity": evidence.severity,
            "confidence": evidence.confidence,
            "subject_keys": list(evidence.subject_keys),
            "relative_path": evidence.relative_path,
            "line": evidence.line,
            "metric_evidence": dict(evidence.metric_evidence),
            "threshold_evidence": dict(evidence.threshold_evidence),
            "occurrence_at_target_snapshot": occurrence is not None,
        }
        if selection.include_current_review_status and current is not None:
            finding_payload["current_lifecycle_state"] = current.lifecycle.evidence_state
            finding_payload["current_review_status"] = current.review.review_status
        if finding_id in note_ids and current is not None:
            note = current.review.note
            if len(note) > budget.maximum_note_length:
                note = note[: budget.maximum_note_length]
                omitted["review-note-characters"] = omitted.get("review-note-characters", 0) + (
                    len(current.review.note) - len(note)
                )
                truncated = True
            finding_payload["explicit_review_note"] = note
        finding_payloads.append(finding_payload)

    if truncated:
        warnings.append("Handoff evidence was truncated to the documented deterministic budgets.")
    payload: dict[str, Any] = {
        "handoff_format_version": HANDOFF_FORMAT_VERSION,
        "repository_state": {
            "repository_id": repository.repository_id,
            "display_name": repository.display_name,
            "observed_state_known": target.observed_state_known,
            "branch": target.observed_branch,
            "git_sha": target.observed_git_sha,
            "dirty": target.observed_dirty,
            "staged": target.observed_staged,
            "untracked": target.observed_untracked,
            "target_snapshot_id": target.snapshot.snapshot_id,
            "baseline_snapshot_id": baseline.snapshot.snapshot_id if baseline else None,
        },
        "comparison": (
            comparison_summary_payload(comparison.summary)
            if comparison is not None and "comparison" in enabled
            else None
        ),
        "selected_changes": changes,
        "findings": finding_payloads if "findings" in enabled else [],
        "analysis_gaps": warnings,
        "task_objective": (selection.task_objective if "task-objective" in enabled else ""),
        "evidence_versions": {
            "target_analyzer_version": target.snapshot.analyzer_version,
            "target_schema_version": target.snapshot.schema_version,
            "target_rule_set_version": target.snapshot.rule_set_version,
            "baseline_analyzer_version": (baseline.snapshot.analyzer_version if baseline else None),
            "baseline_schema_version": baseline.snapshot.schema_version if baseline else None,
            "baseline_rule_set_version": (baseline.snapshot.rule_set_version if baseline else None),
        },
        "truncated": truncated,
        "omitted_counts": dict(sorted(omitted.items())),
    }
    normalized_json = _pretty_json(payload)
    if len(normalized_json.encode("utf-8")) > budget.maximum_json_bytes:
        omitted["json-budget-items"] = sum(len(items) for items in changes.values()) + len(finding_payloads)
        warnings.append("Selected evidence exceeded the JSON byte budget and was omitted.")
        truncated = True
        payload["selected_changes"] = {}
        payload["findings"] = []
        payload["analysis_gaps"] = warnings
        payload["truncated"] = True
        payload["omitted_counts"] = dict(sorted(omitted.items()))
        normalized_json = _pretty_json(payload)
    markdown = _render_markdown(payload)
    if len(markdown) > budget.maximum_markdown_characters:
        warnings.append("Markdown output reached the character budget.")
        omitted["markdown-characters"] = 1
        truncated = True
        payload["analysis_gaps"] = warnings
        payload["truncated"] = True
        payload["omitted_counts"] = dict(sorted(omitted.items()))
        normalized_json = _pretty_json(payload)
        markdown = _render_markdown(payload)
        trailer = "\n\n> TRUNCATED: Markdown character budget reached.\n"
        if budget.maximum_markdown_characters <= len(trailer):
            markdown = trailer[: budget.maximum_markdown_characters]
        else:
            markdown = markdown[: budget.maximum_markdown_characters - len(trailer)] + trailer
    digest = rendered_output_digest(
        HANDOFF_FORMAT_VERSION,
        markdown,
        normalized_json,
    )
    return HandoffRenderResult(
        handoff_format_version=HANDOFF_FORMAT_VERSION,
        markdown=markdown,
        normalized_json=normalized_json,
        rendered_digest=digest,
        truncated=truncated,
        omitted_counts=tuple(sorted(omitted.items())),
        warnings=tuple(warnings),
        markdown_character_count=len(markdown),
        json_byte_count=len(normalized_json.encode("utf-8")),
    )


def selection_json(selection: HandoffSelection) -> str:
    """Serialize a selection deterministically for local persistence."""

    return json.dumps(asdict(selection), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_render_selection(
    selection: HandoffSelection,
    enabled: tuple[str, ...],
    comparison: ComparisonResult | None,
) -> None:
    note_ids = set(selection.explicit_review_note_finding_ids)
    if not note_ids.issubset(set(selection.selected_finding_ids)):
        raise ValueError("Review-note selections must also be selected findings.")
    if comparison is None:
        if selection.selected_delta_ids or selection.selected_cycle_ids:
            raise ValueError("Comparison evidence selections require a baseline snapshot.")
        return

    delta_sections = {
        item.delta_id: section for section in COMPARISON_SECTIONS for item in comparison.section(section)
    }
    for delta_id in set(selection.selected_delta_ids):
        section = delta_sections.get(delta_id)
        if section is None:
            raise ValueError("A selected comparison delta is unknown or stale.")
        if section not in enabled:
            raise ValueError("A selected comparison delta belongs to a disabled section.")

    cycle_ids = {
        cycle_id
        for item in comparison.cycles
        for cycle_id in (item.baseline_cycle_id, item.target_cycle_id)
        if cycle_id is not None
    }
    if selection.selected_cycle_ids and "cycles" not in enabled:
        raise ValueError("A selected cycle belongs to a disabled section.")
    if not set(selection.selected_cycle_ids).issubset(cycle_ids):
        raise ValueError("A selected cycle is unknown or stale.")


def _analysis_warnings(
    target: ComparisonSnapshotEvidence,
    baseline: ComparisonSnapshotEvidence | None,
    comparison: ComparisonResult | None,
) -> list[str]:
    warnings: list[str] = []
    for label, evidence in (("target", target), ("baseline", baseline)):
        if evidence is None:
            continue
        if evidence.snapshot.truncated:
            warnings.append(f"{label.capitalize()} snapshot evidence is truncated.")
        if evidence.snapshot.parse_gap_count:
            warnings.append(
                f"{label.capitalize()} snapshot has {evidence.snapshot.parse_gap_count} parse gaps."
            )
        if not evidence.lifecycle_reconciled:
            reason = evidence.reconciliation_skip_reason or "unknown"
            warnings.append(f"{label.capitalize()} lifecycle reconciliation was incomplete ({reason}).")
    if comparison is not None:
        for section in comparison.summary.compatibility.sections:
            if section.status != "supported":
                reasons = ", ".join(section.reason_codes) or "unsupported"
                warnings.append(f"{section.section.capitalize()} comparison is {section.status}: {reasons}.")
    return warnings


def _render_markdown(payload: dict[str, Any]) -> str:
    state = payload["repository_state"]
    lines = [
        "# Repository Handoff",
        "",
        "## Repository State",
        "",
        f"- Repository: {_md(state['display_name'])}",
        f"- Target snapshot: `{_md(state['target_snapshot_id'])}`",
        f"- Baseline snapshot: `{_md(state['baseline_snapshot_id'] or 'none')}`",
    ]
    if state["observed_state_known"]:
        lines.extend(
            [
                f"- Branch: `{_md(state['branch'] or 'detached')}`",
                f"- Git SHA: `{_md(state['git_sha'] or 'unavailable')}`",
                f"- Working tree: dirty={str(state['dirty']).lower()}, staged={str(state['staged']).lower()}, untracked={str(state['untracked']).lower()}",
            ]
        )
    else:
        lines.append("- Repository observation: `unknown`")
    comparison = payload.get("comparison")
    if comparison is not None:
        lines.extend(["", "## Comparison", ""])
        identity = comparison["identity"]
        lines.append(f"- Comparison ID: `{_md(identity['comparison_id'])}`")
        for name, count in sorted(comparison["counts"].items()):
            if count:
                lines.append(f"- {_md(name.replace('_', ' '))}: {count}")
    lines.extend(["", "## Selected Changes"])
    headings = {
        "files": "Files",
        "symbols": "Symbols",
        "relationships": "Relationships",
        "cycles": "Cycles",
        "metrics": "Metrics",
        "findings": "Finding Occurrences",
    }
    for section, heading in headings.items():
        items = payload["selected_changes"].get(section, [])
        if not items:
            continue
        lines.extend(["", f"### {heading}", ""])
        for item in items:
            lines.append(
                f"- **{_md(item['change_type'])}** — {_md(item['label'])} (`{_md(item['delta_id'])}`)"
            )
    lines.extend(["", "## Findings", ""])
    if payload["findings"]:
        for item in payload["findings"]:
            lines.append(
                f"- **{_md(item['title'])}** — severity `{_md(item['severity'])}`, "
                f"confidence `{_md(item['confidence'])}`"
            )
            lines.append(
                f"  - Occurrence at target snapshot: {str(item['occurrence_at_target_snapshot']).lower()}"
            )
            if "current_lifecycle_state" in item:
                lines.append(f"  - Current lifecycle state: `{_md(item['current_lifecycle_state'])}`")
                lines.append(f"  - Current review status: `{_md(item['current_review_status'])}`")
            if "explicit_review_note" in item:
                lines.append(f"  - Explicit review note: {_md(item['explicit_review_note'])}")
    else:
        lines.append("No findings selected.")
    lines.extend(["", "## Analysis Gaps", ""])
    if payload["analysis_gaps"]:
        lines.extend(f"- {_md(item)}" for item in payload["analysis_gaps"])
    else:
        lines.append("No known partial-evidence warnings.")
    lines.extend(["", "## Task Objective", "", _md(payload["task_objective"]) or "Not provided."])
    lines.extend(["", "## Evidence Versions", ""])
    for key, value in sorted(payload["evidence_versions"].items()):
        lines.append(f"- {_md(key.replace('_', ' '))}: `{_md(value or 'none')}`")
    if payload["truncated"]:
        lines.extend(["", "> TRUNCATED: See omitted counts in the JSON handoff."])
    return "\n".join(lines).rstrip() + "\n"


def _pretty_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _md(value: object) -> str:
    text = str(value)
    for token in ("\\", "`", "*", "_", "{", "}", "[", "]", "<", ">", "#", "|"):
        text = text.replace(token, f"\\{token}")
    return text.replace("\r", " ").replace("\n", " ")


__all__ = ["HANDOFF_SECTIONS", "render_handoff", "selection_json"]
