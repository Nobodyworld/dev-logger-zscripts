from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import replace
from pathlib import Path
from time import perf_counter

import pytest
from fastapi.testclient import TestClient

from zscripts.application.repository_review import RepositoryReviewService
from zscripts.domain.repository_comparison import HandoffBudgetPolicy, HandoffSelection
from zscripts.domain.repository_review import (
    CycleGroupRecord,
    FindingEvidenceRecord,
    GraphNodeRecord,
    MetricRecord,
    RelationshipRecord,
)
from zscripts.infrastructure import snapshot_store as snapshot_store_module
from zscripts.infrastructure.comparison_analysis import compare_snapshots
from zscripts.infrastructure.handoff_rendering import render_handoff
from zscripts.infrastructure.snapshot_store import DATABASE_SCHEMA_VERSION, SnapshotStore
from zscripts.interfaces.workspace_api import create_workspace_app

FIXTURES = Path(__file__).parents[1] / "fixtures" / "repository_review"


def test_comparison_is_stable_logical_and_partial_aware(tmp_path: Path) -> None:
    service, repository, baseline_id, target_id = _snapshot_pair(tmp_path)

    first = service.comparison_summary(baseline_id, target_id)
    second = service.comparison_summary(baseline_id, target_id)
    assert first == second
    assert first["identity"]["comparison_id"] == second["identity"]["comparison_id"]
    assert first["counts"]["files_added"] >= 1
    assert first["counts"]["files_removed"] >= 1
    assert first["counts"]["files_changed"] >= 1
    assert first["counts"]["symbols_changed"] >= 1
    assert first["counts"]["relationships_added"] >= 1
    assert first["counts"]["cycles_added"] >= 1
    assert first["counts"]["metrics_changed"] >= 1

    equal = service.comparison_summary(target_id, target_id)
    assert equal["equal_snapshots"] is True
    assert all(count == 0 for count in equal["counts"].values())

    files = service.comparison_items(
        baseline_id,
        target_id,
        section="files",
        page_size=100,
    )
    assert [item["logical_key"] for item in files["items"]] == sorted(
        item["logical_key"] for item in files["items"]
    )
    assert any(item["change_type"] == "removed" for item in files["items"])
    assert str(repository.resolve()) not in json.dumps({"summary": first, "files": files})

    with sqlite3.connect(service.store.database_path) as connection:
        connection.execute(
            "UPDATE snapshots SET truncated = 1 WHERE snapshot_id = ?",
            (target_id,),
        )
    partial = service.comparison_items(
        baseline_id,
        target_id,
        section="files",
        page_size=100,
    )
    assert partial["section_status"] == "partial"
    assert "target-truncated" in partial["reason_codes"]
    assert any(item["change_type"] == "not-observed" for item in partial["items"])


def test_comparison_rejects_other_repository_and_marks_old_sections(
    tmp_path: Path,
) -> None:
    service, _, baseline_id, target_id = _snapshot_pair(tmp_path)
    other = tmp_path / "other"
    shutil.copytree(FIXTURES / "ordinary", other)
    other_snapshot = service.analyze(other).snapshot.snapshot_id

    with pytest.raises(ValueError, match="different repositories"):
        service.comparison_summary(baseline_id, other_snapshot)

    with sqlite3.connect(service.store.database_path) as connection:
        connection.execute(
            "UPDATE snapshots SET schema_version = '1' WHERE snapshot_id = ?",
            (baseline_id,),
        )
    summary = service.comparison_summary(baseline_id, target_id)
    statuses = {item["section"]: item for item in summary["compatibility"]["sections"]}
    assert statuses["files"]["status"] == "partial"
    assert statuses["relationships"]["status"] == "unavailable"
    assert "baseline-schema-unsupported" in statuses["findings"]["reason_codes"]


def test_handoff_rendering_is_deterministic_bounded_and_notes_are_opt_in(
    tmp_path: Path,
) -> None:
    service, repository, baseline_id, target_id = _snapshot_pair(tmp_path)
    comparison = service.comparison_summary(baseline_id, target_id)
    page = service.comparison_items(
        baseline_id,
        target_id,
        section="files",
        page_size=100,
    )
    target = service.store.comparison_snapshot(target_id)
    finding = target.findings[0]
    current = service.finding_detail(finding.finding_id, target_id)
    service.update_finding_review(
        finding.finding_id,
        expected_version=int(current["review_version"]),
        review_status="needs-action",
        note="private review note",
        reason_code="needs-investigation",
    )
    selection = HandoffSelection(
        target_snapshot_id=target_id,
        baseline_snapshot_id=baseline_id,
        comparison_id=str(comparison["identity"]["comparison_id"]),
        enabled_sections=("comparison", "files", "findings", "task-objective"),
        selected_delta_ids=tuple(item["delta_id"] for item in page["items"]),
        selected_finding_ids=(finding.finding_id,),
        selected_cycle_ids=(),
        include_current_review_status=True,
        explicit_review_note_finding_ids=(),
        task_objective="# Fix [bounded] evidence",
    )

    first = service.preview_handoff(selection)
    second = service.preview_handoff(selection)
    assert first == second
    assert first["rendered_digest"] == second["rendered_digest"]
    assert "private review note" not in first["markdown"]
    assert "Current lifecycle state" in first["markdown"]
    assert "\\# Fix \\[bounded\\] evidence" in first["markdown"]
    assert str(repository.resolve()) not in first["markdown"]
    assert str(repository.resolve()) not in json.dumps(first["json_payload"])

    explicit = service.preview_handoff(
        replace(
            selection,
            explicit_review_note_finding_ids=(finding.finding_id,),
        )
    )
    assert "private review note" in explicit["markdown"]
    assert explicit["rendered_digest"] != first["rendered_digest"]

    saved = service.save_handoff(selection)
    reopened = service.get_handoff(str(saved["handoff_id"]))
    assert reopened["rendered_digest"] == first["rendered_digest"]
    assert reopened["markdown"] == first["markdown"]
    assert service.handoff_markdown(str(saved["handoff_id"])) == first["markdown"]
    assert json.loads(service.handoff_json(str(saved["handoff_id"]))) == first["json_payload"]
    assert len(service.list_handoffs(repository_id=target.snapshot.repository_id)["items"]) == 1


def test_comparison_and_handoff_api_are_typed_bounded_and_download_safe(
    tmp_path: Path,
) -> None:
    service, repository, baseline_id, target_id = _snapshot_pair(tmp_path)
    app = create_workspace_app(service=service)
    comparison = service.comparison_summary(baseline_id, target_id)
    delta = service.comparison_items(
        baseline_id,
        target_id,
        section="files",
        page_size=1,
    )["items"][0]
    request = {
        "target_snapshot_id": target_id,
        "baseline_snapshot_id": baseline_id,
        "comparison_id": comparison["identity"]["comparison_id"],
        "enabled_sections": ["comparison", "files", "task-objective"],
        "selected_delta_ids": [delta["delta_id"]],
        "selected_finding_ids": [],
        "selected_cycle_ids": [],
        "include_current_review_status": False,
        "explicit_review_note_finding_ids": [],
        "task_objective": "Review the selected change.",
    }
    other_repository = tmp_path / "api-other"
    shutil.copytree(FIXTURES / "ordinary", other_repository)
    other_snapshot_id = service.analyze(other_repository).snapshot.snapshot_id

    with TestClient(app) as client:
        snapshots = client.get(
            f"/api/repositories/{comparison['identity']['repository_id']}/comparison-snapshots"
        )
        assert snapshots.status_code == 200
        assert len(snapshots.json()["snapshots"]) == 2
        summary = client.get(
            "/api/comparisons/summary",
            params={
                "baseline_snapshot_id": baseline_id,
                "target_snapshot_id": target_id,
            },
        )
        assert summary.status_code == 200
        items = client.get(
            "/api/comparisons/items",
            params={
                "baseline_snapshot_id": baseline_id,
                "target_snapshot_id": target_id,
                "section": "files",
                "page_size": 1,
            },
        )
        assert items.status_code == 200
        assert items.json()["truncated"] is True
        for section in ("symbols", "relationships", "cycles", "metrics", "findings"):
            section_response = client.get(
                "/api/comparisons/items",
                params={
                    "baseline_snapshot_id": baseline_id,
                    "target_snapshot_id": target_id,
                    "section": section,
                    "page_size": 50,
                },
            )
            assert section_response.status_code == 200, section
        unknown_parameter = client.get(
            "/api/comparisons/items",
            params={
                "baseline_snapshot_id": baseline_id,
                "target_snapshot_id": target_id,
                "section": "files",
                "sql": "DROP TABLE snapshots",
            },
        )
        assert unknown_parameter.status_code == 422
        assert unknown_parameter.json() == {"detail": "Request validation failed."}
        oversized_page = client.get(
            "/api/comparisons/items",
            params={
                "baseline_snapshot_id": baseline_id,
                "target_snapshot_id": target_id,
                "section": "files",
                "page_size": 101,
            },
        )
        assert oversized_page.status_code == 422
        missing = client.get(
            "/api/comparisons/summary",
            params={
                "baseline_snapshot_id": "missing-snapshot",
                "target_snapshot_id": target_id,
            },
        )
        assert missing.status_code == 404
        cross_repository = client.get(
            "/api/comparisons/summary",
            params={
                "baseline_snapshot_id": other_snapshot_id,
                "target_snapshot_id": target_id,
            },
        )
        assert cross_repository.status_code == 400
        cross_handoff = client.post(
            "/api/handoffs/preview",
            json={
                **request,
                "baseline_snapshot_id": other_snapshot_id,
                "comparison_id": None,
            },
        )
        assert cross_handoff.status_code == 400
        oversized_objective = client.post(
            "/api/handoffs/preview",
            json={**request, "task_objective": "x" * 4_001},
        )
        assert oversized_objective.status_code == 422

        preview = client.post("/api/handoffs/preview", json=request)
        assert preview.status_code == 200
        saved = client.post("/api/handoffs", json=request)
        assert saved.status_code == 201
        handoff_id = saved.json()["handoff_id"]
        reopened = client.get(f"/api/handoffs/{handoff_id}")
        assert reopened.status_code == 200
        markdown = client.get(f"/api/handoffs/{handoff_id}/markdown")
        json_download = client.get(f"/api/handoffs/{handoff_id}/json")
        assert markdown.headers["content-type"].startswith("text/markdown")
        assert markdown.headers["content-disposition"].endswith('.md"')
        assert "\r" not in markdown.headers["content-disposition"]
        assert json_download.headers["content-type"].startswith("application/json")
        assert json.loads(json_download.text)["handoff_format_version"] == "1"
        assert str(repository.resolve()) not in json.dumps(
            {
                "snapshots": snapshots.json(),
                "summary": summary.json(),
                "items": items.json(),
                "preview": preview.json(),
                "saved": saved.json(),
            }
        )


def test_schema_v4_migrates_saved_handoffs_non_destructively(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    database = data / "repository-review.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        connection.execute("INSERT INTO schema_version (version) VALUES (4)")
        connection.executescript(snapshot_store_module._SCHEMA_V1)
        connection.executescript(snapshot_store_module._SCHEMA_V2)
        connection.executescript(snapshot_store_module._SCHEMA_V3)
        connection.executescript(snapshot_store_module._SCHEMA_V4)

    first = SnapshotStore(data)
    second = SnapshotStore(data)
    assert first.database_path == second.database_path
    with sqlite3.connect(database) as connection:
        version = connection.execute("SELECT version FROM schema_version").fetchone()[0]
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'saved_handoffs'"
        ).fetchone()
        foreign_keys = connection.execute("PRAGMA foreign_key_list(saved_handoffs)").fetchall()
    assert version == DATABASE_SCHEMA_VERSION == 5
    assert table == ("saved_handoffs",)
    assert foreign_keys


def test_file_and_symbol_logical_deltas_cover_supported_field_changes(
    tmp_path: Path,
) -> None:
    service, _, baseline_id, _ = _snapshot_pair(tmp_path)
    evidence = service.store.comparison_snapshot(baseline_id)
    file_prototype = evidence.files[0]
    symbol_prototype = evidence.symbols[0]

    def file_record(path: str, **changes: object):
        base = replace(
            file_prototype,
            file_id=f"file-{path}",
            relative_path=path,
            content_hash="baseline-hash",
            included=True,
            exclusion_reason=None,
            parse_status="parsed",
        )
        return replace(base, **changes)

    baseline_files = (
        file_record("content.py"),
        file_record("inclusion.py"),
        file_record("parse.py"),
        file_record("removed.py"),
        file_record("rename_old.py"),
    )
    target_files = (
        file_record("content.py", content_hash="target-hash"),
        file_record(
            "inclusion.py",
            included=False,
            exclusion_reason="configured-exclusion",
        ),
        file_record("parse.py", parse_status="syntax-error"),
        file_record("added.py"),
        file_record("rename_new.py"),
    )

    def symbol_record(name: str, **changes: object):
        base = replace(
            symbol_prototype,
            symbol_id=f"symbol-{name}",
            qualified_name=f"pkg.{name}",
            display_name=name,
            signature="()",
            visibility="public",
            decorators=(),
            annotations=(),
            docstring_present=False,
            async_flag=False,
            bases=(),
            content_fingerprint="baseline-fingerprint",
        )
        return replace(base, **changes)

    symbol_mutations = {
        "signature": {"signature": "(value: int)"},
        "visibility": {"visibility": "private"},
        "decorator": {"decorators": ("classmethod",)},
        "annotation": {"annotations": ("value: int",)},
        "docstring": {"docstring_present": True},
        "async": {"async_flag": True},
        "bases": {"bases": ("Base",)},
        "fingerprint": {"content_fingerprint": "target-fingerprint"},
    }
    baseline_symbols = tuple(symbol_record(name) for name in symbol_mutations) + (
        symbol_record("rename_old"),
    )
    target_symbols = tuple(symbol_record(name, **changes) for name, changes in symbol_mutations.items()) + (
        symbol_record("rename_new"),
    )

    baseline = replace(evidence, files=baseline_files, symbols=baseline_symbols)
    target = replace(
        evidence,
        snapshot=replace(evidence.snapshot, snapshot_id="synthetic-target"),
        files=target_files,
        symbols=target_symbols,
    )
    result = compare_snapshots(baseline, target)
    file_changes = {item.logical_key: item.change_type for item in result.files}
    assert file_changes == {
        "added.py": "added",
        "content.py": "changed",
        "inclusion.py": "changed",
        "parse.py": "changed",
        "removed.py": "removed",
        "rename_new.py": "added",
        "rename_old.py": "removed",
    }
    symbol_changes = {item.label: item.change_type for item in result.symbols}
    assert all(symbol_changes[f"pkg.{name}"] == "changed" for name in symbol_mutations)
    assert symbol_changes["pkg.rename_old"] == "removed"
    assert symbol_changes["pkg.rename_new"] == "added"
    assert tuple(item.logical_key for item in result.symbols) == tuple(
        sorted(item.logical_key for item in result.symbols)
    )


def test_relationship_cycle_metric_and_finding_deltas_use_logical_subjects(
    tmp_path: Path,
) -> None:
    service, _, baseline_id, _ = _snapshot_pair(tmp_path)
    evidence = service.store.comparison_snapshot(baseline_id)
    finding_prototype = evidence.findings[0]
    baseline_nodes = (
        _node("baseline-a", "pkg.a"),
        _node("baseline-b", "pkg.b"),
        _node("baseline-c", "pkg.c"),
        _node("baseline-d", "pkg.d"),
    )
    target_nodes = (
        _node("target-a", "pkg.a"),
        _node("target-b", "pkg.b"),
        _node("target-c", "pkg.c"),
        _node("target-d", "pkg.d"),
    )
    baseline_relationships = (
        _relationship("rel-shared-old", "baseline-a", "baseline-b"),
        _relationship(
            "rel-removed",
            "baseline-a",
            None,
            unresolved_target="external.Dynamic",
        ),
    )
    target_relationships = (
        replace(
            _relationship("rel-shared-new", "target-a", "target-b"),
            resolution_status="probable-static",
            confidence="medium",
            evidence="from pkg import b",
            line=9,
        ),
        _relationship("rel-added", "target-b", "target-c"),
    )
    baseline_cycles = (
        CycleGroupRecord("cycle-shared-old", "imports", ("baseline-a", "baseline-b"), ()),
        CycleGroupRecord("cycle-removed", "imports", ("baseline-c", "baseline-d"), ()),
    )
    target_cycles = (
        CycleGroupRecord("cycle-shared-new", "imports", ("target-b", "target-a"), ()),
        CycleGroupRecord("cycle-added", "imports", ("target-a", "target-c"), ()),
    )
    baseline_metrics = (
        _metric("metric-zero-old", "baseline-a", "zero", 0),
        _metric("metric-increase-old", "baseline-a", "increase", 1),
        _metric("metric-decrease-old", "baseline-a", "decrease", 3),
        _metric("metric-same-old", "baseline-a", "same", 5),
    )
    target_metrics = (
        _metric("metric-zero-new", "target-a", "zero", 5),
        _metric("metric-increase-new", "target-a", "increase", 3),
        _metric("metric-decrease-new", "target-a", "decrease", 1),
        _metric("metric-same-new", "target-a", "same", 5),
    )
    baseline_findings = (
        _finding(finding_prototype, "shared-old", "rule-shared", "1", ("pkg.a",)),
        _finding(finding_prototype, "removed", "rule-removed", "1", ("pkg.b",)),
        _finding(finding_prototype, "same-old", "rule-same", "1", ("pkg.c",)),
    )
    target_findings = (
        _finding(finding_prototype, "shared-new", "rule-shared", "2", ("pkg.a",)),
        _finding(finding_prototype, "added", "rule-added", "1", ("pkg.d",)),
        _finding(finding_prototype, "same-new", "rule-same", "1", ("pkg.c",)),
    )
    baseline = replace(
        evidence,
        graph_nodes=baseline_nodes,
        relationships=baseline_relationships,
        cycles=baseline_cycles,
        metrics=baseline_metrics,
        findings=baseline_findings,
    )
    target = replace(
        evidence,
        snapshot=replace(evidence.snapshot, snapshot_id="logical-target"),
        graph_nodes=target_nodes,
        relationships=target_relationships,
        cycles=target_cycles,
        metrics=target_metrics,
        findings=target_findings,
    )
    result = compare_snapshots(baseline, target)

    assert sorted(item.change_type for item in result.relationships) == [
        "added",
        "changed",
        "removed",
    ]
    changed_relationship = next(item for item in result.relationships if item.change_type == "changed")
    assert "pkg.a" in changed_relationship.source
    assert "pkg.b" in changed_relationship.target_name
    assert [item.change_type for item in result.cycles] == ["added", "removed"]
    assert result.cycles[0].target_cycle_id == "cycle-added"
    assert result.cycles[1].baseline_cycle_id == "cycle-removed"

    metrics = {item.metric_name: item for item in result.metrics}
    assert metrics["increase"].direction == "increase"
    assert metrics["increase"].percentage_delta == 200
    assert metrics["decrease"].direction == "decrease"
    assert metrics["zero"].percentage_delta is None
    assert "same" not in metrics

    findings = {item.rule_id: item for item in result.findings}
    assert findings["rule-added"].occurrence_state == "new-in-target"
    assert findings["rule-removed"].occurrence_state == "absent-from-target"
    assert findings["rule-shared"].occurrence_state == "rule-version-changed"
    assert "rule-same" not in findings


def test_version_and_superseded_metadata_are_explicitly_partial(
    tmp_path: Path,
) -> None:
    service, _, baseline_id, _ = _snapshot_pair(tmp_path)
    baseline = service.store.comparison_snapshot(baseline_id)
    target = replace(
        baseline,
        snapshot=replace(
            baseline.snapshot,
            snapshot_id="version-target",
            analyzer_version="4",
            rule_set_version="5",
        ),
        lifecycle_reconciled=False,
        reconciliation_skip_reason="superseded-by-newer-analysis",
    )
    result = compare_snapshots(baseline, target)
    compatibility = {item.section: item for item in result.summary.compatibility.sections}
    assert all("version-mismatch" in item.reason_codes for item in compatibility.values())
    assert compatibility["findings"].status == "partial"
    assert "target-lifecycle-incomplete" in compatibility["findings"].reason_codes
    assert result.summary.compatibility.target_reconciliation_skip_reason == "superseded-by-newer-analysis"


def test_handoff_budget_cycle_selection_and_failed_insert_are_safe(
    tmp_path: Path,
) -> None:
    service, _, baseline_id, target_id = _snapshot_pair(tmp_path)
    baseline = service.store.comparison_snapshot(baseline_id)
    target = service.store.comparison_snapshot(target_id)
    comparison = compare_snapshots(baseline, target)
    cycle = comparison.cycles[0]
    selection = HandoffSelection(
        target_snapshot_id=target_id,
        baseline_snapshot_id=baseline_id,
        comparison_id=comparison.summary.identity.comparison_id,
        enabled_sections=("comparison", "files", "cycles", "task-objective"),
        selected_delta_ids=tuple(item.delta_id for item in comparison.files),
        selected_finding_ids=(),
        selected_cycle_ids=tuple(
            item for item in (cycle.baseline_cycle_id, cycle.target_cycle_id) if item is not None
        ),
        include_current_review_status=False,
        explicit_review_note_finding_ids=(),
        task_objective="Bounded handoff",
        budget_policy=HandoffBudgetPolicy(maximum_items_per_section=1),
    )
    rendered = render_handoff(
        selection=selection,
        repository=target.repository,
        target=target,
        baseline=baseline,
        comparison=comparison,
        current_findings=(),
    )
    payload = json.loads(rendered.normalized_json)
    assert rendered.truncated is True
    assert dict(rendered.omitted_counts)["files"] == len(comparison.files) - 1
    assert len(payload["selected_changes"]["files"]) == 1
    assert len(payload["selected_changes"]["cycles"]) == 1

    service_selection = replace(selection, budget_policy=HandoffBudgetPolicy())
    saved = service.save_handoff(service_selection)
    snapshot_id_before = target.snapshot.snapshot_id
    saved_record = service.store.get_handoff(str(saved["handoff_id"]))
    assert saved_record is not None
    with pytest.raises(sqlite3.IntegrityError):
        service.store.save_handoff(saved_record)
    assert service.store.get_snapshot(target_id).snapshot_id == snapshot_id_before
    assert len(service.list_handoffs(repository_id=target.snapshot.repository_id)["items"]) == 1


def test_comparison_performance_is_bounded_for_thousands_of_file_deltas(
    tmp_path: Path,
) -> None:
    service, _, baseline_id, _ = _snapshot_pair(tmp_path)
    evidence = service.store.comparison_snapshot(baseline_id)
    prototype = evidence.files[0]
    baseline_files = tuple(
        replace(
            prototype,
            file_id=f"old-{index}",
            relative_path=f"pkg/generated_{index:04d}.py",
            content_hash=f"old-{index}",
        )
        for index in range(3_000)
    )
    target_files = tuple(
        replace(item, file_id=f"new-{index}", content_hash=f"new-{index}")
        for index, item in enumerate(baseline_files)
    )
    baseline = replace(evidence, files=baseline_files)
    target = replace(
        evidence,
        snapshot=replace(evidence.snapshot, snapshot_id="performance-target"),
        files=target_files,
    )
    started = perf_counter()
    result = compare_snapshots(baseline, target)
    elapsed = perf_counter() - started
    assert len(result.files) == 3_000
    assert elapsed < 1.0


def _node(node_id: str, qualified_name: str) -> GraphNodeRecord:
    return GraphNodeRecord(
        node_id=node_id,
        node_type="module",
        display_name=qualified_name.rsplit(".", 1)[-1],
        qualified_name=qualified_name,
        relative_path=f"{qualified_name.replace('.', '/')}.py",
        symbol_kind=None,
    )


def _relationship(
    relationship_id: str,
    source_id: str,
    target_id: str | None,
    *,
    unresolved_target: str | None = None,
) -> RelationshipRecord:
    return RelationshipRecord(
        relationship_id=relationship_id,
        relationship_type="imports",
        source_id=source_id,
        target_id=target_id,
        unresolved_target=unresolved_target,
        resolution_status="resolved-static" if target_id else "unresolved-dynamic",
        confidence="high" if target_id else "low",
        relative_path="pkg/a.py",
        line=1,
        column=0,
        analyzer_version="3",
        evidence="import pkg.b",
    )


def _metric(
    metric_id: str,
    subject_id: str,
    metric_name: str,
    value: float,
) -> MetricRecord:
    return MetricRecord(
        metric_id=metric_id,
        subject_id=subject_id,
        subject_type="module",
        metric_name=metric_name,
        numeric_value=value,
        unit="count",
        analyzer_version="3",
        relative_path="pkg/a.py",
        line=1,
    )


def _finding(
    prototype: FindingEvidenceRecord,
    finding_id: str,
    rule_id: str,
    rule_version: str,
    subject_keys: tuple[str, ...],
) -> FindingEvidenceRecord:
    return replace(
        prototype,
        finding_id=finding_id,
        rule_id=rule_id,
        rule_version=rule_version,
        subject_keys=subject_keys,
        title=rule_id,
    )


def _snapshot_pair(
    tmp_path: Path,
) -> tuple[RepositoryReviewService, Path, str, str]:
    repository = tmp_path / "comparison"
    shutil.copytree(FIXTURES / "findings", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    baseline = service.analyze(repository)

    metrics = repository / "pkg" / "metrics.py"
    metrics.write_text(
        metrics.read_text(encoding="utf-8")
        .replace(
            "def complex_target(alpha, beta, gamma, delta, epsilon, zeta, eta, theta, iota):",
            "def complex_target(alpha, beta, gamma, delta, epsilon, zeta, eta, theta):",
        )
        .replace("return selected if zeta else [eta, theta, iota]", "return selected or [eta, theta]"),
        encoding="utf-8",
    )
    (repository / "pkg" / "duplicate_b.py").unlink()
    (repository / "pkg" / "new_cycle.py").write_text(
        "from pkg import cycle_a\n\nclass AddedType:\n    pass\n",
        encoding="utf-8",
    )
    (repository / "pkg" / "cycle_a.py").write_text(
        "from pkg import new_cycle\n",
        encoding="utf-8",
    )
    target = service.analyze(repository)
    assert baseline.snapshot.snapshot_id != target.snapshot.snapshot_id
    return service, repository, baseline.snapshot.snapshot_id, target.snapshot.snapshot_id
