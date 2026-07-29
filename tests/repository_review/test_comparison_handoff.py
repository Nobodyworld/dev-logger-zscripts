from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
from dataclasses import replace
from pathlib import Path
from time import perf_counter

import pytest
from fastapi.testclient import TestClient

from zscripts.application.repository_review import RepositoryReviewService, _snapshot_identifier
from zscripts.domain.repository_comparison import (
    HANDOFF_FORMAT_VERSION,
    HandoffBudgetPolicy,
    HandoffSelection,
    rendered_output_digest,
)
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
    assert any(item["change_type"] == "not-observed-in-target" for item in partial["items"])


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
        preview_payload = preview.json()
        assert json.loads(preview_payload["normalized_json"]) == preview_payload["json_payload"]
        assert preview_payload["rendered_digest"] == rendered_output_digest(
            preview_payload["handoff_format_version"],
            preview_payload["markdown"],
            preview_payload["normalized_json"],
        )
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
        assert json.loads(json_download.text)["handoff_format_version"] == HANDOFF_FORMAT_VERSION
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
    assert version == DATABASE_SCHEMA_VERSION == 6
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


def test_snapshot_identity_preserves_exact_repository_observations(tmp_path: Path) -> None:
    repository = tmp_path / "observations"
    shutil.copytree(FIXTURES / "ordinary", repository)
    _git(repository, "init", "-b", "branch-a")
    _git(repository, "config", "user.email", "repository-review@example.invalid")
    _git(repository, "config", "user.name", "Repository Review")
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "fixture")
    service = RepositoryReviewService(data_directory=tmp_path / "data")

    branch_a = service.analyze(repository)
    _git(repository, "switch", "-c", "branch-b")
    branch_b = service.analyze(repository)
    branch_b_repeat = service.analyze(repository)

    assert branch_a.snapshot.snapshot_id != branch_b.snapshot.snapshot_id
    assert branch_b_repeat.snapshot.snapshot_id == branch_b.snapshot.snapshot_id
    choices = service.comparison_snapshots(branch_a.repository.repository_id)["snapshots"]
    assert {item["branch"] for item in choices} == {"branch-a", "branch-b"}
    assert all(item["observed_state_known"] is True for item in choices)
    assert len(choices) == 2
    assert str(repository.resolve()) not in json.dumps(choices)

    def identifier(repository_state):
        return _snapshot_identifier(
            repository=repository_state,
            source_fingerprint=branch_a.snapshot.source_fingerprint,
            files=branch_a.files,
            modules=branch_a.modules,
            symbols=branch_a.symbols,
            diagnostics=branch_a.diagnostics,
            graph_nodes=branch_a.graph_nodes,
            relationships=branch_a.relationships,
            cycles=branch_a.cycles,
            metrics=branch_a.metrics,
            findings=branch_a.findings,
            truncated=branch_a.snapshot.truncated,
        )

    clean = replace(
        branch_a.repository,
        branch="branch-a",
        dirty=False,
        staged=False,
        untracked=False,
    )
    identities = {
        identifier(clean),
        identifier(replace(clean, dirty=True)),
        identifier(replace(clean, dirty=True, staged=True)),
        identifier(replace(clean, dirty=True, untracked=True)),
    }
    assert len(identities) == 4
    assert identifier(clean) == identifier(clean)


def test_schema_v5_migration_marks_historical_observations_unknown(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    database = data / "repository-review.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        connection.execute("INSERT INTO schema_version (version) VALUES (5)")
        for schema in (
            snapshot_store_module._SCHEMA_V1,
            snapshot_store_module._SCHEMA_V2,
            snapshot_store_module._SCHEMA_V3,
            snapshot_store_module._SCHEMA_V4,
            snapshot_store_module._SCHEMA_V5,
        ):
            connection.executescript(schema)
        connection.execute(
            """
            INSERT INTO repositories (
                repository_id, display_name, canonical_path, git_root, branch,
                git_sha, dirty, staged, untracked, configuration_digest,
                source_roots_json, test_roots_json, latest_analysis_generation
            ) VALUES (
                'historical-repository', 'historical', ?, NULL, 'current-branch',
                'current-sha', 1, 1, 1, 'config', '[]', '[]', 0
            )
            """,
            (str(tmp_path / "historical"),),
        )
        connection.executemany(
            """
            INSERT INTO snapshots (
                snapshot_id, repository_id, analyzer_version, schema_version,
                rule_set_version, state, source_fingerprint, file_count,
                included_file_count, module_count, symbol_count, started_at,
                completed_at, duration_ms, truncated, parse_gap_count,
                observed_branch, observed_git_sha, observed_dirty,
                observed_staged, observed_untracked
            ) VALUES (
                ?, 'historical-repository', '3', '3', '4', 'completed',
                ?, 0, 0, 0, 0, ?, ?, 0, 0, 0, ?, ?, 1, 1, 1
            )
            """,
            (
                (
                    "historical-snapshot-a",
                    "source-a",
                    "2026-07-01T00:00:00Z",
                    "2026-07-01T00:00:00Z",
                    "incorrect-a",
                    "incorrect-sha-a",
                ),
                (
                    "historical-snapshot-b",
                    "source-b",
                    "2026-07-02T00:00:00Z",
                    "2026-07-02T00:00:00Z",
                    "incorrect-b",
                    "incorrect-sha-b",
                ),
            ),
        )

    store = SnapshotStore(data)
    service = RepositoryReviewService(store=store)
    choices = service.comparison_snapshots("historical-repository")["snapshots"]
    assert len(choices) == 2
    assert all(item["observed_state_known"] is False for item in choices)
    assert all(item["branch"] is None and item["git_sha"] is None for item in choices)
    assert all(
        item["dirty"] is None and item["staged"] is None and item["untracked"] is None for item in choices
    )
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT observed_state_known FROM snapshots ORDER BY snapshot_id"
        ).fetchall()
        version = connection.execute("SELECT version FROM schema_version").fetchone()[0]
    assert rows == [(0,), (0,)]
    assert version == DATABASE_SCHEMA_VERSION == 6


@pytest.mark.parametrize(
    ("baseline_changes", "target_changes", "expected"),
    (
        ({}, {}, {"added", "removed"}),
        ({"truncated": True}, {}, {"not-observed-in-baseline", "removed"}),
        ({"parse_gap_count": 1}, {}, {"not-observed-in-baseline", "removed"}),
        ({}, {"truncated": True}, {"added", "not-observed-in-target"}),
        ({}, {"parse_gap_count": 1}, {"added", "not-observed-in-target"}),
        (
            {"truncated": True},
            {"parse_gap_count": 1},
            {"not-observed-in-baseline", "not-observed-in-target"},
        ),
        (
            {},
            {"analyzer_version": "4", "rule_set_version": "5"},
            {"not-observed-in-baseline", "not-observed-in-target"},
        ),
    ),
)
def test_every_comparison_section_models_uncertainty_on_both_sides(
    tmp_path: Path,
    baseline_changes: dict[str, object],
    target_changes: dict[str, object],
    expected: set[str],
) -> None:
    service, _, baseline_id, _ = _snapshot_pair(tmp_path)
    evidence = service.store.comparison_snapshot(baseline_id)
    nodes = (
        _node("node-a", "pkg.a"),
        _node("node-b", "pkg.b"),
        _node("node-c", "pkg.c"),
        _node("node-d", "pkg.d"),
    )
    baseline = replace(
        evidence,
        snapshot=replace(evidence.snapshot, **baseline_changes),
        files=(replace(evidence.files[0], file_id="file-a", relative_path="pkg/a.py"),),
        symbols=(
            replace(
                evidence.symbols[0],
                symbol_id="symbol-a",
                qualified_name="pkg.a.A",
                display_name="A",
            ),
        ),
        graph_nodes=nodes,
        relationships=(_relationship("relationship-a", "node-a", "node-b"),),
        cycles=(CycleGroupRecord("cycle-a", "imports", ("node-a", "node-b"), ()),),
        metrics=(_metric("metric-a", "node-a", "fan-out", 1),),
        findings=(_finding(evidence.findings[0], "finding-a", "rule-a", "1", ("pkg.a",)),),
    )
    target = replace(
        evidence,
        snapshot=replace(
            evidence.snapshot,
            snapshot_id="uncertainty-target",
            **target_changes,
        ),
        files=(replace(evidence.files[0], file_id="file-d", relative_path="pkg/d.py"),),
        symbols=(
            replace(
                evidence.symbols[0],
                symbol_id="symbol-d",
                qualified_name="pkg.d.D",
                display_name="D",
            ),
        ),
        graph_nodes=nodes,
        relationships=(_relationship("relationship-d", "node-c", "node-d"),),
        cycles=(CycleGroupRecord("cycle-d", "imports", ("node-c", "node-d"), ()),),
        metrics=(_metric("metric-d", "node-d", "fan-out", 1),),
        findings=(_finding(evidence.findings[0], "finding-d", "rule-d", "1", ("pkg.d",)),),
    )

    result = compare_snapshots(baseline, target)
    for section in ("files", "symbols", "relationships", "cycles", "metrics", "findings"):
        assert {item.change_type for item in result.section(section)} == expected, section
    if "not-observed-in-baseline" in expected:
        target_occurrence = next(
            item for item in result.findings if item.change_type == "not-observed-in-baseline"
        )
        assert target_occurrence.occurrence_state == "not-observed-in-baseline"
    if "not-observed-in-target" in expected:
        baseline_occurrence = next(
            item for item in result.findings if item.change_type == "not-observed-in-target"
        )
        assert baseline_occurrence.occurrence_state == "not-observed-in-target"


def test_handoff_selection_validation_and_exact_output_integrity(tmp_path: Path) -> None:
    service, _, baseline_id, target_id = _snapshot_pair(tmp_path)
    app = create_workspace_app(service=service)
    summary = service.comparison_summary(baseline_id, target_id)
    comparison_id = str(summary["identity"]["comparison_id"])
    file_delta = service.comparison_items(
        baseline_id,
        target_id,
        section="files",
        page_size=100,
    )["items"][0]
    symbol_delta = service.comparison_items(
        baseline_id,
        target_id,
        section="symbols",
        page_size=100,
    )["items"][0]
    cycle_delta = service.comparison_items(
        baseline_id,
        target_id,
        section="cycles",
        page_size=100,
    )["items"][0]
    cycle_id = cycle_delta["target_cycle_id"] or cycle_delta["baseline_cycle_id"]
    finding_id = service.store.comparison_snapshot(target_id).findings[0].finding_id
    stale_delta = service.comparison_items(
        target_id,
        baseline_id,
        section="files",
        page_size=100,
    )["items"][0]["delta_id"]
    other_repository = tmp_path / "selection-other"
    shutil.copytree(FIXTURES / "findings", other_repository)
    other_snapshot = service.analyze(other_repository)
    other_finding_id = other_snapshot.findings[0].finding_id
    request = {
        "target_snapshot_id": target_id,
        "baseline_snapshot_id": baseline_id,
        "comparison_id": comparison_id,
        "enabled_sections": ["comparison", "files", "symbols", "cycles", "findings"],
        "selected_delta_ids": [
            file_delta["delta_id"],
            file_delta["delta_id"],
            symbol_delta["delta_id"],
        ],
        "selected_finding_ids": [finding_id, finding_id],
        "selected_cycle_ids": [cycle_id, cycle_id],
        "include_current_review_status": False,
        "explicit_review_note_finding_ids": [],
        "task_objective": "Validate exact evidence.",
    }
    invalid_requests = (
        {**request, "selected_delta_ids": ["unknown-delta"]},
        {**request, "selected_delta_ids": [stale_delta]},
        {**request, "selected_cycle_ids": ["unknown-cycle"]},
        {
            **request,
            "enabled_sections": ["comparison", "symbols", "cycles", "findings"],
        },
        {
            **request,
            "explicit_review_note_finding_ids": ["not-selected"],
        },
        {**request, "comparison_id": "comparison-stale"},
        {
            **request,
            "baseline_snapshot_id": None,
            "comparison_id": None,
        },
        {**request, "selected_finding_ids": ["unknown-finding"]},
        {**request, "selected_finding_ids": [other_finding_id]},
    )

    with TestClient(app) as client:
        for invalid in invalid_requests:
            response_item = client.post("/api/handoffs/preview", json=invalid)
            assert response_item.status_code == 400
            assert response_item.json() == {"detail": "Handoff selection is invalid."}

        preview = client.post("/api/handoffs/preview", json=request)
        assert preview.status_code == 200
        saved = client.post("/api/handoffs", json=request)
        assert saved.status_code == 201
        saved_payload = saved.json()
        assert saved_payload["selection"]["selected_delta_ids"] == sorted(
            {file_delta["delta_id"], symbol_delta["delta_id"]}
        )
        assert saved_payload["selection"]["selected_cycle_ids"] == [cycle_id]
        assert saved_payload["selection"]["selected_finding_ids"] == [finding_id]
        handoff_id = saved_payload["handoff_id"]
        record = service.store.get_handoff(handoff_id)
        assert record is not None
        assert record.rendered_digest == rendered_output_digest(
            record.format_version,
            record.rendered_markdown,
            record.rendered_json,
        )
        assert record.rendered_digest != rendered_output_digest(
            record.format_version,
            record.rendered_markdown + "x",
            record.rendered_json,
        )
        assert record.rendered_digest != rendered_output_digest(
            record.format_version,
            record.rendered_markdown,
            record.rendered_json + " ",
        )
        markdown = client.get(f"/api/handoffs/{handoff_id}/markdown")
        json_download = client.get(f"/api/handoffs/{handoff_id}/json")
        assert markdown.content == record.rendered_markdown.encode("utf-8")
        assert json_download.content == record.rendered_json.encode("utf-8")
        reopened = client.get(f"/api/handoffs/{handoff_id}").json()
        assert reopened["markdown_character_count"] == len(record.rendered_markdown)
        assert reopened["json_byte_count"] == len(record.rendered_json.encode("utf-8"))
        assert reopened["markdown"] == record.rendered_markdown
        assert reopened["normalized_json"] == record.rendered_json

        with sqlite3.connect(service.store.database_path) as connection:
            connection.execute(
                "UPDATE saved_handoffs SET rendered_markdown = rendered_markdown || 'x' WHERE handoff_id = ?",
                (handoff_id,),
            )
        assert client.get(f"/api/handoffs/{handoff_id}").status_code == 409
        assert client.get(f"/api/handoffs/{handoff_id}/markdown").status_code == 409
        assert client.get(f"/api/handoffs/{handoff_id}/json").status_code == 409


def test_forced_markdown_truncation_is_part_of_exact_digest(tmp_path: Path) -> None:
    service, _, baseline_id, target_id = _snapshot_pair(tmp_path)
    baseline = service.store.comparison_snapshot(baseline_id)
    target = service.store.comparison_snapshot(target_id)
    comparison = compare_snapshots(baseline, target)
    selection = HandoffSelection(
        target_snapshot_id=target_id,
        baseline_snapshot_id=baseline_id,
        comparison_id=comparison.summary.identity.comparison_id,
        enabled_sections=("comparison", "files", "task-objective"),
        selected_delta_ids=tuple(item.delta_id for item in comparison.files),
        selected_finding_ids=(),
        selected_cycle_ids=(),
        include_current_review_status=False,
        explicit_review_note_finding_ids=(),
        task_objective="Force exact Markdown truncation.",
        budget_policy=HandoffBudgetPolicy(maximum_markdown_characters=180),
    )
    first = render_handoff(
        selection=selection,
        repository=target.repository,
        target=target,
        baseline=baseline,
        comparison=comparison,
        current_findings=(),
    )
    second = render_handoff(
        selection=selection,
        repository=target.repository,
        target=target,
        baseline=baseline,
        comparison=comparison,
        current_findings=(),
    )
    assert first == second
    assert first.truncated is True
    assert len(first.markdown) == 180
    assert first.rendered_digest == rendered_output_digest(
        first.handoff_format_version,
        first.markdown,
        first.normalized_json,
    )


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


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
