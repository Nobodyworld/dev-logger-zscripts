from __future__ import annotations

import json
import shutil
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zscripts import cli as cli_module
from zscripts.application.repository_review import RepositoryReviewService
from zscripts.interfaces.workspace_api import create_workspace_app, validate_workspace_host

FIXTURES = Path(__file__).parents[1] / "fixtures" / "repository_review"
TERMINAL_STATES = {"completed", "cancelled", "failed"}


def _wait_for_analysis(client: TestClient, analysis_id: str) -> dict[str, object]:
    for _ in range(300):
        response = client.get(f"/api/analyses/{analysis_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["state"] in TERMINAL_STATES:
            return payload
        time.sleep(0.01)
    raise AssertionError("Analysis did not reach a terminal state.")


def test_workspace_api_end_to_end_and_security_headers(tmp_path: Path) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    app = create_workspace_app(service=service)

    with TestClient(app) as client:
        assert client.get("/api/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        openapi = client.get("/api/openapi.json")
        assert openapi.status_code == 200
        assert openapi.json()["info"]["title"] == "Zscripts Experimental Repository Review API"
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.headers["content-security-policy"].startswith("default-src 'self'")
        assert health.headers["x-frame-options"] == "DENY"
        notices = client.get("/THIRD_PARTY_NOTICES.md")
        assert notices.status_code == 200
        assert "Meta Platforms" in notices.text
        response = client.post(
            "/api/repositories/analyze",
            json={"repository_path": str(repository)},
        )
        assert response.status_code == 202
        job = _wait_for_analysis(client, response.json()["analysis_id"])
        assert job["state"] == "completed"
        snapshot_id = str(job["snapshot_id"])
        repository_id = str(job["repository_id"])

        repositories = client.get("/api/repositories").json()["repositories"]
        assert repositories[0]["repository_id"] == repository_id
        assert str(tmp_path) not in json.dumps(repositories)
        snapshots = client.get(f"/api/repositories/{repository_id}/snapshots").json()["snapshots"]
        assert snapshots[0]["snapshot_id"] == snapshot_id
        overview = client.get(f"/api/snapshots/{snapshot_id}/overview")
        assert overview.status_code == 200
        assert overview.json()["counts"]["modules"] == 2
        symbols = client.get(
            f"/api/snapshots/{snapshot_id}/symbols",
            params={"search": "method", "kind": "method", "sort": "line", "direction": "desc"},
        )
        assert symbols.status_code == 200
        assert symbols.json()["items"][0]["qualified_name"] == "pkg.module.Example.method"
        source = client.get(
            f"/api/snapshots/{snapshot_id}/source",
            params={"path": "pkg/module.py", "start_line": 1, "end_line": 10},
        )
        assert source.status_code == 200
        assert source.json()["relative_path"] == "pkg/module.py"
        traversal = client.get(
            f"/api/snapshots/{snapshot_id}/source",
            params={"path": "../outside.py"},
        )
        assert traversal.status_code == 400
        assert client.get("/api/route-that-does-not-exist").status_code == 404


def test_validation_is_generic_and_does_not_reflect_input(tmp_path: Path) -> None:
    secret_path = str(tmp_path / "private-secret-repository")
    app = create_workspace_app(data_directory=tmp_path / "data")

    with TestClient(app) as client:
        response = client.post(
            "/api/repositories/analyze",
            json={"repository_path": secret_path, "repository_id": "also-present"},
        )

    assert response.status_code == 422
    assert response.json() == {"detail": "Request validation failed."}
    assert secret_path not in response.text


def test_resolve_scope_api_is_strict_read_only_and_path_safe(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    nested = repository / "src" / "feature"
    nested.mkdir(parents=True)
    (repository / ".git").mkdir()
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    app = create_workspace_app(service=service)

    def persistence_counts() -> dict[str, int]:
        tables = (
            "analysis_sequence",
            "repositories",
            "analyses",
            "snapshots",
            "findings",
            "finding_review_events",
            "saved_handoffs",
        )
        with sqlite3.connect(service.store.database_path) as connection:
            return {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in tables
            }

    with TestClient(app) as client:
        before = client.get("/api/repositories").json()
        before_persistence = persistence_counts()
        nested_response = client.post(
            "/api/repositories/resolve-scope",
            json={"repository_path": str(nested)},
        )
        same_response = client.post(
            "/api/repositories/resolve-scope",
            json={"repository_path": str(repository)},
        )
        ordinary_response = client.post(
            "/api/repositories/resolve-scope",
            json={"repository_path": str(ordinary)},
        )
        after = client.get("/api/repositories").json()
        after_persistence = persistence_counts()
        invalid = client.post(
            "/api/repositories/resolve-scope",
            json={"repository_path": str(tmp_path / "private-missing")},
        )
        unknown = client.post(
            "/api/repositories/resolve-scope",
            json={"repository_path": str(ordinary), "unexpected": True},
        )
        oversized = client.post(
            "/api/repositories/resolve-scope",
            json={"repository_path": "x" * 1_025},
        )

    assert nested_response.status_code == 200
    assert nested_response.json() == {
        "presentation_version": "1",
        "entered_path": str(nested),
        "resolved_input_path": str(nested.resolve()),
        "analysis_root": str(repository.resolve()),
        "git_root_detected": True,
        "confirmation_required": True,
        "reason": "enclosing-git-root",
    }
    assert same_response.json()["reason"] == "same-directory"
    assert same_response.json()["confirmation_required"] is False
    assert ordinary_response.json()["reason"] == "non-git-directory"
    assert ordinary_response.json()["git_root_detected"] is False
    assert before == after == {"repositories": []}
    assert (
        before_persistence
        == after_persistence
        == {
            "analysis_sequence": 0,
            "repositories": 0,
            "analyses": 0,
            "snapshots": 0,
            "findings": 0,
            "finding_review_events": 0,
            "saved_handoffs": 0,
        }
    )
    for response in (invalid, unknown, oversized):
        assert response.status_code in {400, 422}
        assert response.json() == {
            "detail": "Repository path is invalid."
            if response.status_code == 400
            else "Request validation failed."
        }
        assert "private-missing" not in response.text


def test_snapshot_evidence_status_api_is_strict_bounded_and_allowlisted(tmp_path: Path) -> None:
    repository = tmp_path / "private-status-repository"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    snapshot_id = evidence.snapshot.snapshot_id
    app = create_workspace_app(service=service)

    with TestClient(app) as client:
        complete = client.get(f"/api/snapshots/{snapshot_id}/evidence-status")
        assert complete.status_code == 200
        assert complete.json() == {
            "presentation_version": "1",
            "surface": "generic",
            "snapshot_id": snapshot_id,
            "evidence_complete": True,
            "observation_state_known": True,
            "lifecycle_reconciled": True,
            "reconciliation_skip_reason": None,
            "limitations": [],
        }
        with sqlite3.connect(service.store.database_path) as connection:
            connection.execute(
                """
                UPDATE snapshots
                SET truncated = 1, parse_gap_count = 3, schema_version = '1',
                    observed_state_known = 0
                WHERE snapshot_id = ?
                """,
                (snapshot_id,),
            )
            connection.execute(
                """
                UPDATE analyses
                SET lifecycle_reconciled = 1,
                    reconciliation_skip_reason = 'truncated-scan'
                WHERE snapshot_id = ? AND state = 'completed'
                """,
                (snapshot_id,),
            )

        partial = client.get(f"/api/snapshots/{snapshot_id}/evidence-status?surface=findings")
        assert partial.status_code == 200
        payload = partial.json()
        assert set(payload) == {
            "presentation_version",
            "surface",
            "snapshot_id",
            "evidence_complete",
            "observation_state_known",
            "lifecycle_reconciled",
            "reconciliation_skip_reason",
            "limitations",
        }
        assert [item["code"] for item in payload["limitations"]] == [
            "snapshot-truncated",
            "snapshot-parse-gaps",
            "snapshot-schema-unsupported",
            "observation-state-unknown",
            "lifecycle-truncated-scan",
        ]
        assert payload["surface"] == "findings"
        assert all(
            set(item) == {"code", "category", "consequence", "count"} for item in payload["limitations"]
        )
        assert payload["limitations"][1]["count"] == 3
        assert str(repository.resolve()) not in partial.text
        assert "canonical_path" not in partial.text
        assert '"source"' not in partial.text

        for reason, expected_code in (
            ("parse-gaps", "lifecycle-parse-gaps"),
            ("superseded-by-newer-analysis", "lifecycle-superseded"),
            ("analysis-status-unavailable", "lifecycle-analysis-status-unavailable"),
        ):
            with sqlite3.connect(service.store.database_path) as connection:
                connection.execute(
                    """
                    UPDATE analyses
                    SET lifecycle_reconciled = 0, reconciliation_skip_reason = ?
                    WHERE snapshot_id = ? AND state = 'completed'
                    """,
                    (reason, snapshot_id),
                )
            response = client.get(f"/api/snapshots/{snapshot_id}/evidence-status?surface=findings")
            assert response.status_code == 200
            assert response.json()["limitations"][-1]["code"] == expected_code

        missing = client.get("/api/snapshots/not-a-snapshot/evidence-status")
        assert missing.status_code == 404
        assert missing.json() == {"detail": "Snapshot was not found."}

        invalid_surface = client.get(f"/api/snapshots/{snapshot_id}/evidence-status?surface=metrics")
        assert invalid_surface.status_code == 422
        assert invalid_surface.json() == {"detail": "Request validation failed."}


def test_snapshot_evidence_status_api_schema_support_matrix(tmp_path: Path) -> None:
    repository = tmp_path / "schema-matrix"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    snapshot_id = evidence.snapshot.snapshot_id
    app = create_workspace_app(service=service)
    matrix = {
        "1": {"overview": True, "symbols": True, "relationships": False, "findings": False},
        "2": {"overview": True, "symbols": True, "relationships": True, "findings": False},
        "3": {"overview": True, "symbols": True, "relationships": True, "findings": True},
        "4": {"overview": True, "symbols": True, "relationships": True, "findings": True},
    }

    with TestClient(app) as client:
        for schema_version, surfaces in matrix.items():
            with sqlite3.connect(service.store.database_path) as connection:
                connection.execute(
                    "UPDATE snapshots SET schema_version = ? WHERE snapshot_id = ?",
                    (schema_version, snapshot_id),
                )
            generic = client.get(f"/api/snapshots/{snapshot_id}/evidence-status")
            assert generic.status_code == 200
            assert generic.json()["surface"] == "generic"
            assert generic.json()["limitations"] == []
            for surface, supported in surfaces.items():
                response = client.get(f"/api/snapshots/{snapshot_id}/evidence-status?surface={surface}")
                assert response.status_code == 200
                payload = response.json()
                assert payload["surface"] == surface
                assert (
                    "snapshot-schema-unsupported" not in {item["code"] for item in payload["limitations"]}
                ) is supported

        for schema_version in ("5", "future"):
            with sqlite3.connect(service.store.database_path) as connection:
                connection.execute(
                    "UPDATE snapshots SET schema_version = ? WHERE snapshot_id = ?",
                    (schema_version, snapshot_id),
                )
            response = client.get(f"/api/snapshots/{snapshot_id}/evidence-status")
            assert response.status_code == 200
            assert [item["code"] for item in response.json()["limitations"]] == [
                "snapshot-schema-unsupported"
            ]


def test_relationship_api_is_bounded_typed_and_path_redacted(tmp_path: Path) -> None:
    repository = tmp_path / "relationships"
    shutil.copytree(FIXTURES / "relationships", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    snapshot_id = evidence.snapshot.snapshot_id
    app = create_workspace_app(service=service)

    with TestClient(app) as client:
        summary = client.get(
            f"/api/snapshots/{snapshot_id}/relationships/summary",
            params={"max_nodes": 200},
        )
        assert summary.status_code == 200
        summary_payload = summary.json()
        assert summary_payload["supported"] is True
        assert summary_payload["relationship_types"]["imports"] >= 1
        assert summary_payload["resolution_statuses"]["ambiguous"] >= 1
        module = next(
            item
            for item in summary_payload["nodes"]
            if item["node_type"] == "module" and item["qualified_name"] == "app.cycle_a"
        )
        bounded_summary = client.get(
            f"/api/snapshots/{snapshot_id}/relationships/summary",
            params={"max_nodes": 2},
        ).json()
        assert bounded_summary["truncated"] is True
        assert len(bounded_summary["nodes"]) == 2
        assert len(bounded_summary["fan_in"]) <= 2
        assert len(bounded_summary["fan_out"]) <= 2
        assert len(bounded_summary["inheritance_depth"]) <= 2

        page = client.get(
            f"/api/snapshots/{snapshot_id}/relationships",
            params={"relationship_type": "imports", "page": 1, "page_size": 3},
        )
        assert page.status_code == 200
        assert page.json()["page_size"] == 3
        assert page.json()["total"] >= 3

        neighborhood = client.get(
            f"/api/snapshots/{snapshot_id}/relationships/neighborhood",
            params={
                "mode": "modules",
                "focus_id": module["node_id"],
                "depth": 1,
                "max_nodes": 3,
                "max_edges": 3,
            },
        )
        assert neighborhood.status_code == 200
        neighborhood_payload = neighborhood.json()
        assert neighborhood_payload["focus_id"] == module["node_id"]
        assert len(neighborhood_payload["nodes"]) <= 3
        assert len(neighborhood_payload["relationships"]) <= 3

        cycles = client.get(
            f"/api/snapshots/{snapshot_id}/cycles",
            params={"relationship_type": "imports", "max_results": 10},
        )
        assert cycles.status_code == 200
        assert len(cycles.json()["items"]) == 1
        assert len(cycles.json()["items"][0]["member_node_ids"]) == 2

        invalid_mode = client.get(
            f"/api/snapshots/{snapshot_id}/relationships/neighborhood",
            params={"mode": "global", "focus_id": module["node_id"]},
        )
        assert invalid_mode.status_code == 422
        assert invalid_mode.json() == {"detail": "Request validation failed."}
        invalid_limit = client.get(
            f"/api/snapshots/{snapshot_id}/relationships/summary",
            params={"max_nodes": 0},
        )
        assert invalid_limit.status_code == 422
        assert invalid_limit.json() == {"detail": "Request validation failed."}
        assert str(repository.resolve()) not in json.dumps(
            {
                "summary": summary_payload,
                "page": page.json(),
                "neighborhood": neighborhood_payload,
                "cycles": cycles.json(),
            }
        )


def test_relationship_node_query_reaches_omitted_nodes_and_cycle_members(tmp_path: Path) -> None:
    repository = tmp_path / "large-graph"
    repository.mkdir()
    for index in range(205):
        (repository / f"module_{index:03}.py").write_text(
            f"class Item{index:03}: pass\n",
            encoding="utf-8",
        )
    (repository / "zcycle_a.py").write_text("import zcycle_b\n", encoding="utf-8")
    (repository / "zcycle_b.py").write_text("import zcycle_a\n", encoding="utf-8")
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    snapshot_id = evidence.snapshot.snapshot_id
    app = create_workspace_app(service=service)

    with TestClient(app) as client:
        summary = client.get(
            f"/api/snapshots/{snapshot_id}/relationships/summary",
            params={"max_nodes": 200},
        ).json()
        assert summary["node_count"] > 200
        assert all(item["qualified_name"] != "zcycle_a" for item in summary["nodes"])

        initial = client.get(
            f"/api/snapshots/{snapshot_id}/relationships/nodes",
            params={"mode": "modules", "page": 1, "page_size": 10},
        )
        assert initial.status_code == 200
        assert initial.json()["total"] == 207
        assert initial.json()["truncated"] is True

        search = client.get(
            f"/api/snapshots/{snapshot_id}/relationships/nodes",
            params={"mode": "modules", "search": "ZCYCLE_A", "page_size": 10},
        )
        assert search.status_code == 200
        assert search.json()["total"] == 1
        omitted = search.json()["items"][0]
        assert omitted["qualified_name"] == "zcycle_a"

        neighborhood = client.get(
            f"/api/snapshots/{snapshot_id}/relationships/neighborhood",
            params={"mode": "modules", "focus_id": omitted["node_id"], "depth": 1},
        )
        assert neighborhood.status_code == 200
        assert neighborhood.json()["focus_id"] == omitted["node_id"]
        assert {item["qualified_name"] for item in neighborhood.json()["nodes"]} == {
            "zcycle_a",
            "zcycle_b",
        }

        cycle = client.get(
            f"/api/snapshots/{snapshot_id}/cycles",
            params={"relationship_type": "imports"},
        ).json()["items"][0]
        member_id = cycle["member_node_ids"][0]
        assert all(item["node_id"] != member_id for item in summary["nodes"])
        member = client.get(
            f"/api/snapshots/{snapshot_id}/relationships/nodes",
            params=[("mode", "modules"), ("node_ids", member_id), ("page_size", "10")],
        )
        assert member.status_code == 200
        assert member.json()["total"] == 1
        assert member.json()["items"][0]["node_id"] == member_id
        assert str(repository.resolve()) not in json.dumps(
            {"search": search.json(), "member": member.json(), "neighborhood": neighborhood.json()}
        )


def test_relationship_api_handles_old_snapshot_explicitly(tmp_path: Path) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    with sqlite3.connect(service.store.database_path) as connection:
        connection.execute(
            "UPDATE snapshots SET analyzer_version = '1', schema_version = '1' WHERE snapshot_id = ?",
            (evidence.snapshot.snapshot_id,),
        )
        connection.execute(
            "DELETE FROM relationships WHERE snapshot_id = ?",
            (evidence.snapshot.snapshot_id,),
        )
        connection.execute(
            "DELETE FROM graph_nodes WHERE snapshot_id = ?",
            (evidence.snapshot.snapshot_id,),
        )
    app = create_workspace_app(service=service)

    with TestClient(app) as client:
        summary = client.get(f"/api/snapshots/{evidence.snapshot.snapshot_id}/relationships/summary")
        relationships = client.get(f"/api/snapshots/{evidence.snapshot.snapshot_id}/relationships")
        nodes = client.get(
            f"/api/snapshots/{evidence.snapshot.snapshot_id}/relationships/nodes",
            params={"mode": "modules"},
        )
        cycles = client.get(f"/api/snapshots/{evidence.snapshot.snapshot_id}/cycles")
        finding_summary = client.get(f"/api/snapshots/{evidence.snapshot.snapshot_id}/findings/summary")
        findings = client.get(f"/api/snapshots/{evidence.snapshot.snapshot_id}/findings")

    assert summary.status_code == 200
    assert summary.json()["supported"] is False
    assert relationships.json()["items"] == []
    assert nodes.json() == {
        "supported": False,
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 100,
        "truncated": False,
    }
    assert cycles.json()["items"] == []
    assert finding_summary.json()["supported"] is False
    assert set(finding_summary.json()["families"]) == {
        "dependency-cycle",
        "inheritance-cycle",
        "duplicate-name-candidate",
        "oversized",
        "complexity",
        "nesting",
        "parameters",
        "coupling",
        "inheritance",
        "documentation",
        "test-evidence-candidate",
        "orphan-candidate",
    }
    assert not any(finding_summary.json()["families"].values())
    assert findings.json()["supported"] is False
    assert findings.json()["preset"] == "all"
    assert findings.json()["items"] == []


def test_findings_api_filters_reviews_conflicts_and_redacts_paths(tmp_path: Path) -> None:
    repository = tmp_path / "findings"
    shutil.copytree(FIXTURES / "findings", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    snapshot_id = evidence.snapshot.snapshot_id
    app = create_workspace_app(service=service)

    with TestClient(app) as client:
        summary = client.get(f"/api/snapshots/{snapshot_id}/findings/summary")
        assert summary.status_code == 200
        assert summary.json()["supported"] is True
        assert summary.json()["active"] == len(evidence.findings)
        assert summary.json()["reconciliation_complete"] is True
        assert summary.json()["lifecycle_reconciled"] is True
        assert summary.json()["reconciliation_skip_reason"] is None
        assert summary.json()["families"] == {
            family: sum(1 for item in evidence.findings if item.family == family)
            for family in summary.json()["families"]
        }

        default_page = client.get(f"/api/snapshots/{snapshot_id}/findings")
        assert default_page.status_code == 200
        assert default_page.json()["preset"] == "all"
        assert default_page.json()["total"] == len(evidence.findings)
        focused_page = client.get(
            f"/api/snapshots/{snapshot_id}/findings",
            params={"preset": "high-signal-v1", "page_size": 100},
        )
        assert focused_page.status_code == 200
        assert focused_page.json()["preset"] == "high-signal-v1"
        assert {item["family"] for item in focused_page.json()["items"]} == {
            "dependency-cycle",
            "inheritance",
        }

        page = client.get(
            f"/api/snapshots/{snapshot_id}/findings",
            params={
                "family": "parameters",
                "severity": "low",
                "confidence": "high",
                "search": "COMPLEX_TARGET",
                "page": 1,
                "page_size": 5,
            },
        )
        assert page.status_code == 200
        assert page.json()["preset"] == "all"
        assert page.json()["total"] == 1
        finding = page.json()["items"][0]
        assert finding["subject_keys"] == ["pkg.metrics.complex_target"]
        assert str(repository.resolve()) not in page.text
        focused_low = client.get(
            f"/api/snapshots/{snapshot_id}/findings",
            params={
                "preset": "high-signal-v1",
                "family": "parameters",
                "severity": "low",
                "confidence": "high",
            },
        )
        assert focused_low.status_code == 200
        assert focused_low.json()["total"] == 0

        detail = client.get(
            f"/api/findings/{finding['finding_id']}",
            params={"snapshot_id": snapshot_id},
        )
        assert detail.status_code == 200
        history = client.get(f"/api/findings/{finding['finding_id']}/history")
        assert history.status_code == 200
        assert history.json()["items"][0]["event_type"] == "finding-first-seen"

        malicious_note = '<img src=x onerror="alert(1)">'
        update = client.patch(
            f"/api/findings/{finding['finding_id']}/review",
            json={
                "expected_version": 0,
                "review_status": "needs-action",
                "note": malicious_note,
                "reason_code": "needs-investigation",
            },
        )
        assert update.status_code == 200
        assert update.json()["note"] == malicious_note
        assert update.json()["review_version"] == 1

        conflict = client.patch(
            f"/api/findings/{finding['finding_id']}/review",
            json={
                "expected_version": 0,
                "review_status": "dismissed",
                "note": "stale",
                "reason_code": "false-positive",
            },
        )
        assert conflict.status_code == 409
        assert conflict.json()["detail"] == "Finding review version conflict."
        assert conflict.json()["current"]["review_version"] == 1
        assert conflict.json()["current"]["note"] == malicious_note

        invalid = client.get(
            f"/api/snapshots/{snapshot_id}/findings",
            params={"severity": "critical"},
        )
        assert invalid.status_code == 422
        assert invalid.json() == {"detail": "Request validation failed."}
        invalid_preset = client.get(
            f"/api/snapshots/{snapshot_id}/findings",
            params={"preset": "private-ranker"},
        )
        assert invalid_preset.status_code == 422
        assert invalid_preset.json() == {"detail": "Request validation failed."}
        invalid_note = client.patch(
            f"/api/findings/{finding['finding_id']}/review",
            json={
                "expected_version": 1,
                "review_status": "reviewed",
                "note": "x" * 2_001,
                "reason_code": "other",
            },
        )
        assert invalid_note.status_code == 422
        rules = client.get("/api/finding-rules")
        assert rules.status_code == 200
        assert any(item["rule_id"] == "dependency-cycle" for item in rules.json()["rules"])

    assert str(repository.resolve()) not in json.dumps(
        {
            "summary": summary.json(),
            "page": page.json(),
            "detail": detail.json(),
            "history": history.json(),
            "update": update.json(),
            "conflict": conflict.json(),
        }
    )


def test_cli_and_api_share_canonical_snapshot_contract(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)
    data_directory = tmp_path / "data"

    exit_code = cli_module.main(
        [
            "experimental",
            "analyze",
            str(repository),
            "--app-data-dir",
            str(data_directory),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    cli_payload = json.loads(captured.out)
    service = RepositoryReviewService(data_directory=data_directory)
    snapshot = service.get_snapshot(cli_payload["snapshot"]["snapshot_id"])

    assert exit_code == 0
    assert snapshot.snapshot_id == cli_payload["snapshot"]["snapshot_id"]
    assert service.overview(snapshot.snapshot_id)["snapshot"]["snapshot_id"] == snapshot.snapshot_id
    assert str(tmp_path) not in captured.out

    findings_exit = cli_module.main(
        [
            "experimental",
            "findings",
            snapshot.snapshot_id,
            "--app-data-dir",
            str(data_directory),
            "--json",
        ]
    )
    findings_payload = json.loads(capsys.readouterr().out)
    rules_exit = cli_module.main(
        [
            "experimental",
            "finding-rules",
            "--app-data-dir",
            str(data_directory),
            "--json",
        ]
    )
    rules_payload = json.loads(capsys.readouterr().out)
    assert findings_exit == 0
    assert findings_payload["supported"] is True
    assert rules_exit == 0
    assert rules_payload["rules"]


def test_workspace_binding_is_localhost_only() -> None:
    assert validate_workspace_host("127.0.0.1") == "127.0.0.1"
    try:
        validate_workspace_host("0.0.0.0")
    except ValueError as exc:
        assert "only supports host 127.0.0.1" in str(exc)
    else:
        raise AssertionError("Non-loopback binding was accepted.")
