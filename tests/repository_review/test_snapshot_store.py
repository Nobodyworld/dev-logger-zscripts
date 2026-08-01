from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from zscripts.application.repository_review import RepositoryReviewService, SourceEvidenceError
from zscripts.domain.repository_review import AnalysisEvidence, AnalysisState, EvidenceStatusSurface
from zscripts.infrastructure import snapshot_store as snapshot_store_module
from zscripts.infrastructure.snapshot_store import DATABASE_SCHEMA_VERSION, SnapshotStore

FIXTURES = Path(__file__).parents[1] / "fixtures" / "repository_review"


def test_same_named_non_git_repositories_keep_distinct_identity_and_snapshots(
    tmp_path: Path,
) -> None:
    first_repository = tmp_path / "first" / "shared-name"
    second_repository = tmp_path / "second" / "shared-name"
    shutil.copytree(FIXTURES / "ordinary", first_repository)
    shutil.copytree(FIXTURES / "ordinary", second_repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")

    first = service.analyze(first_repository)
    repeated_first = service.analyze(first_repository)
    second = service.analyze(second_repository)

    assert first.repository.repository_id == repeated_first.repository.repository_id
    assert first.repository.repository_id != second.repository.repository_id
    assert {item.repository_id for item in service.list_repositories()} == {
        first.repository.repository_id,
        second.repository.repository_id,
    }
    assert {item.snapshot_id for item in service.list_snapshots(first.repository.repository_id)} == {
        first.snapshot.snapshot_id
    }
    assert {item.snapshot_id for item in service.list_snapshots(second.repository.repository_id)} == {
        second.snapshot.snapshot_id
    }

    public_payloads = (
        first.canonical_bytes(),
        second.canonical_bytes(),
        str(service.overview(first.snapshot.snapshot_id)).encode(),
        str(service.overview(second.snapshot.snapshot_id)).encode(),
    )
    for path in (first_repository.resolve(), second_repository.resolve()):
        encoded_path = str(path).encode()
        assert all(encoded_path not in payload for payload in public_payloads)


def test_snapshot_round_trip_filters_and_source_evidence(tmp_path: Path) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")

    first = service.analyze(repository)
    second = service.analyze(repository)

    assert first.snapshot.snapshot_id == second.snapshot.snapshot_id
    assert first.canonical_bytes() == second.canonical_bytes()
    assert service.list_repositories()[0].repository_id == first.repository.repository_id
    snapshots = service.list_snapshots(first.repository.repository_id)
    assert len(snapshots) == 1
    assert snapshots[0].snapshot_id == second.snapshot.snapshot_id
    overview = service.overview(first.snapshot.snapshot_id)
    assert overview["counts"] == {
        "files_analyzed": 2,
        "files_excluded": 0,
        "packages": 1,
        "modules": 2,
        "classes": 2,
        "functions": 2,
        "methods": 1,
        "parse_gaps": 0,
        "relationship_analysis_supported": True,
        "resolved_import_edges": 2,
        "inheritance_edges": 0,
        "cycle_groups": 0,
        "largest_cycle_size": 0,
        "active_findings": 3,
        "needs_action_findings": 0,
        "resolved_since_last_scan": 0,
        "high_confidence_high_severity_findings": 0,
    }
    assert first.relationships
    assert service.store.list_graph_nodes(first.snapshot.snapshot_id)
    assert service.store.all_relationships(first.snapshot.snapshot_id) == first.relationships
    node_page = service.store.query_graph_nodes(
        first.snapshot.snapshot_id,
        mode="inheritance",
        search="example",
        page=1,
        page_size=1,
    )
    assert node_page.total == 2
    assert node_page.items[0].qualified_name == "pkg.module.Example"

    page = service.symbols(
        first.snapshot.snapshot_id,
        search="method",
        kind="method",
        visibility="public",
        sort="line",
        direction="desc",
        page=1,
        page_size=5,
    )
    assert page.total == 1
    assert page.items[0].qualified_name == "pkg.module.Example.method"
    assert "method" in service.symbol_filters(first.snapshot.snapshot_id)["kinds"]
    source = service.read_source(
        first.snapshot.snapshot_id,
        "pkg/module.py",
        start_line=1,
        end_line=10_000,
    )
    assert source.start_line == 1
    assert source.end_line <= service.limits.max_source_lines
    assert source.lines[0][1].startswith('"""Ordinary Python syntax')

    (repository / "pkg" / "module.py").write_text("def changed(): ...\n", encoding="utf-8")
    with pytest.raises(SourceEvidenceError, match="changed after"):
        service.read_source(
            first.snapshot.snapshot_id,
            "pkg/module.py",
            start_line=1,
            end_line=5,
        )
    with pytest.raises(SourceEvidenceError, match="repository-relative"):
        service.read_source(first.snapshot.snapshot_id, "../outside.py", start_line=1, end_line=5)


def test_snapshot_evidence_status_is_complete_and_zero_noise(tmp_path: Path) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)

    status = service.snapshot_evidence_status(evidence.snapshot.snapshot_id)

    assert status.presentation_version == "1"
    assert status.surface == "generic"
    assert status.snapshot_id == evidence.snapshot.snapshot_id
    assert status.evidence_complete is True
    assert status.observation_state_known is True
    assert status.lifecycle_reconciled is True
    assert status.reconciliation_skip_reason is None
    assert status.limitations == ()


def test_generic_evidence_status_does_not_reject_readable_historical_schema(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    snapshot_id = evidence.snapshot.snapshot_id

    for schema_version in ("1", "2", "3", "4"):
        with sqlite3.connect(service.store.database_path) as connection:
            connection.execute(
                "UPDATE snapshots SET schema_version = ? WHERE snapshot_id = ?",
                (schema_version, snapshot_id),
            )

        status = service.snapshot_evidence_status(snapshot_id)

        assert "snapshot-schema-unsupported" not in {limitation.code for limitation in status.limitations}


@pytest.mark.parametrize(
    ("schema_version", "surface", "supported"),
    [
        ("1", "overview", True),
        ("1", "symbols", True),
        ("1", "relationships", False),
        ("1", "findings", False),
        ("1", "generic", True),
        ("2", "overview", True),
        ("2", "symbols", True),
        ("2", "relationships", True),
        ("2", "findings", False),
        ("2", "generic", True),
        ("3", "overview", True),
        ("3", "symbols", True),
        ("3", "relationships", True),
        ("3", "findings", True),
        ("3", "generic", True),
        ("4", "overview", True),
        ("4", "symbols", True),
        ("4", "relationships", True),
        ("4", "findings", True),
        ("4", "generic", True),
    ],
)
def test_snapshot_evidence_status_schema_support_is_surface_aware(
    tmp_path: Path,
    schema_version: str,
    surface: EvidenceStatusSurface,
    supported: bool,
) -> None:
    repository = tmp_path / f"schema-{schema_version}-{surface}"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    snapshot_id = evidence.snapshot.snapshot_id
    with sqlite3.connect(service.store.database_path) as connection:
        connection.execute(
            "UPDATE snapshots SET schema_version = ? WHERE snapshot_id = ?",
            (schema_version, snapshot_id),
        )

    status = service.snapshot_evidence_status(snapshot_id, surface=surface)

    assert status.surface == surface
    assert ("snapshot-schema-unsupported" not in {item.code for item in status.limitations}) is (supported)


@pytest.mark.parametrize("schema_version", ["5", "future", "", "1.0", "0"])
def test_snapshot_evidence_status_rejects_newer_or_malformed_schema(
    tmp_path: Path,
    schema_version: str,
) -> None:
    repository = tmp_path / f"schema-{schema_version or 'empty'}"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    with sqlite3.connect(service.store.database_path) as connection:
        connection.execute(
            "UPDATE snapshots SET schema_version = ? WHERE snapshot_id = ?",
            (schema_version, evidence.snapshot.snapshot_id),
        )

    status = service.snapshot_evidence_status(evidence.snapshot.snapshot_id)

    assert [item.code for item in status.limitations] == ["snapshot-schema-unsupported"]


@pytest.mark.parametrize(
    "surface",
    ["generic", "overview", "symbols", "relationships", "findings"],
)
def test_snapshot_partial_facts_are_preserved_for_each_surface(
    tmp_path: Path,
    surface: EvidenceStatusSurface,
) -> None:
    repository = tmp_path / f"partial-{surface}"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    with sqlite3.connect(service.store.database_path) as connection:
        connection.execute(
            """
            UPDATE snapshots
            SET truncated = 1, parse_gap_count = 2
            WHERE snapshot_id = ?
            """,
            (evidence.snapshot.snapshot_id,),
        )

    status = service.snapshot_evidence_status(evidence.snapshot.snapshot_id, surface=surface)

    assert [item.code for item in status.limitations[:2]] == [
        "snapshot-truncated",
        "snapshot-parse-gaps",
    ]
    assert status.limitations[1].count == 2


def test_snapshot_evidence_status_rejects_an_unallowlisted_surface(tmp_path: Path) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)

    with pytest.raises(ValueError, match="Unsupported evidence status surface"):
        service.snapshot_evidence_status(
            evidence.snapshot.snapshot_id,
            surface="metrics",  # type: ignore[arg-type]
        )


def test_snapshot_evidence_status_orders_combined_limitations_and_redacts_paths(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "private-repository-name"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    snapshot_id = evidence.snapshot.snapshot_id
    with sqlite3.connect(service.store.database_path) as connection:
        connection.execute(
            """
            UPDATE snapshots
            SET truncated = 1, parse_gap_count = 2, schema_version = '1',
                observed_state_known = 0
            WHERE snapshot_id = ?
            """,
            (snapshot_id,),
        )
        connection.execute(
            """
            UPDATE analyses
            SET lifecycle_reconciled = 1, reconciliation_skip_reason = 'parse-gaps'
            WHERE snapshot_id = ? AND state = 'completed'
            """,
            (snapshot_id,),
        )

    status = service.snapshot_evidence_status(snapshot_id, surface="findings")

    assert status.evidence_complete is False
    assert [item.code for item in status.limitations] == [
        "snapshot-truncated",
        "snapshot-parse-gaps",
        "snapshot-schema-unsupported",
        "observation-state-unknown",
        "lifecycle-parse-gaps",
    ]
    assert status.limitations[1].count == 2
    assert all(str(repository.resolve()) not in item.consequence for item in status.limitations)


def test_snapshot_evidence_status_reports_individual_snapshot_limitations(tmp_path: Path) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    snapshot_id = evidence.snapshot.snapshot_id
    cases = (
        (1, 0, "4", 1, ["snapshot-truncated"]),
        (0, 2, "4", 1, ["snapshot-parse-gaps"]),
        (1, 2, "4", 1, ["snapshot-truncated", "snapshot-parse-gaps"]),
        (0, 0, "5", 1, ["snapshot-schema-unsupported"]),
        (0, 0, "4", 0, ["observation-state-unknown"]),
    )
    for truncated, parse_gaps, schema_version, observation_known, expected in cases:
        with sqlite3.connect(service.store.database_path) as connection:
            connection.execute(
                """
                UPDATE snapshots
                SET truncated = ?, parse_gap_count = ?, schema_version = ?,
                    observed_state_known = ?
                WHERE snapshot_id = ?
                """,
                (truncated, parse_gaps, schema_version, observation_known, snapshot_id),
            )

        status = service.snapshot_evidence_status(snapshot_id)

        assert [item.code for item in status.limitations] == expected


def test_snapshot_evidence_status_maps_allowlisted_lifecycle_reasons(tmp_path: Path) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    snapshot_id = evidence.snapshot.snapshot_id
    cases = (
        ("truncated-scan", True, "lifecycle-truncated-scan"),
        ("parse-gaps", True, "lifecycle-parse-gaps"),
        ("superseded-by-newer-analysis", False, "lifecycle-superseded"),
        (None, False, "lifecycle-analysis-status-unavailable"),
    )
    for reason, reconciled, expected_code in cases:
        with sqlite3.connect(service.store.database_path) as connection:
            connection.execute(
                """
                UPDATE analyses
                SET lifecycle_reconciled = ?, reconciliation_skip_reason = ?
                WHERE snapshot_id = ? AND state = 'completed'
                """,
                (int(reconciled), reason, snapshot_id),
            )

        status = service.snapshot_evidence_status(snapshot_id)

        assert status.limitations[-1].code == expected_code
        assert status.reconciliation_skip_reason == (reason or "analysis-status-unavailable")


def test_snapshot_evidence_status_uses_latest_completed_analysis_for_exact_snapshot(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    first_analysis = service.store.allocate_analysis_id()
    first = service.analyze(repository, analysis_id=first_analysis)
    repeated_analysis = service.store.allocate_analysis_id()
    repeated = service.analyze(repository, analysis_id=repeated_analysis)
    assert repeated.snapshot.snapshot_id == first.snapshot.snapshot_id
    (repository / "pkg" / "module.py").write_text("def next_snapshot(): ...\n", encoding="utf-8")
    next_analysis = service.store.allocate_analysis_id()
    next_evidence = service.analyze(repository, analysis_id=next_analysis)
    with sqlite3.connect(service.store.database_path) as connection:
        connection.execute(
            """
            UPDATE analyses
            SET lifecycle_reconciled = 1, reconciliation_skip_reason = 'truncated-scan'
            WHERE analysis_id = ?
            """,
            (first_analysis,),
        )
        connection.execute(
            """
            UPDATE analyses
            SET lifecycle_reconciled = 0,
                reconciliation_skip_reason = 'superseded-by-newer-analysis'
            WHERE analysis_id = ?
            """,
            (repeated_analysis,),
        )
        connection.execute(
            """
            UPDATE analyses
            SET lifecycle_reconciled = 1, reconciliation_skip_reason = 'parse-gaps'
            WHERE analysis_id = ?
            """,
            (next_analysis,),
        )

    first_status = service.snapshot_evidence_status(first.snapshot.snapshot_id)
    next_status = service.snapshot_evidence_status(next_evidence.snapshot.snapshot_id)

    assert first_status.reconciliation_skip_reason == "superseded-by-newer-analysis"
    assert first_status.limitations[-1].code == "lifecycle-superseded"
    assert next_status.reconciliation_skip_reason == "parse-gaps"
    assert next_status.limitations[-1].code == "lifecycle-parse-gaps"


def test_snapshot_promotion_rolls_back_all_evidence_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)
    store = SnapshotStore(tmp_path / "data")
    analysis_id = store.allocate_analysis_id()
    original_insert = SnapshotStore._insert_snapshot

    def insert_then_fail(connection: sqlite3.Connection, evidence: AnalysisEvidence) -> None:
        original_insert(connection, evidence)
        raise RuntimeError("simulated storage interruption")

    monkeypatch.setattr(SnapshotStore, "_insert_snapshot", staticmethod(insert_then_fail))
    service = RepositoryReviewService(store=store)

    with pytest.raises(RuntimeError, match="storage interruption"):
        service.analyze(repository, analysis_id=analysis_id)

    status = store.get_analysis(analysis_id)
    assert status is not None
    assert status.state is AnalysisState.FAILED
    assert status.snapshot_id is None
    assert store.list_snapshots(status.repository_id) == ()
    with sqlite3.connect(store.database_path) as connection:
        for table in (
            "snapshots",
            "files",
            "modules",
            "symbols",
            "diagnostics",
            "graph_nodes",
            "relationships",
            "cycle_groups",
            "cycle_members",
            "cycle_edges",
            "metrics",
            "finding_occurrences",
            "findings",
            "finding_reviews",
            "finding_review_events",
        ):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_schema_migration_is_idempotent(tmp_path: Path) -> None:
    first = SnapshotStore(tmp_path / "data")
    second = SnapshotStore(tmp_path / "data")

    assert first.database_path == second.database_path
    with sqlite3.connect(first.database_path) as connection:
        version = connection.execute("SELECT version FROM schema_version").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_list(symbols)").fetchall()
    assert version == DATABASE_SCHEMA_VERSION
    assert foreign_keys


def test_mvp_schema_migrates_without_reinterpreting_old_snapshot(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    database = data / "repository-review.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        connection.execute("INSERT INTO schema_version (version) VALUES (1)")
        connection.executescript(snapshot_store_module._SCHEMA_V1)
        connection.execute(
            """
            INSERT INTO repositories (
                repository_id, display_name, canonical_path, git_root, branch,
                git_sha, dirty, staged, untracked, configuration_digest,
                source_roots_json, test_roots_json
            ) VALUES ('old-repository', 'old', ?, NULL, NULL, NULL, 0, 0, 0, 'config', '[]', '[]')
            """,
            (str(tmp_path / "old"),),
        )
        connection.execute(
            """
            INSERT INTO snapshots (
                snapshot_id, repository_id, analyzer_version, schema_version,
                rule_set_version, state, source_fingerprint, file_count,
                included_file_count, module_count, symbol_count, started_at,
                completed_at, duration_ms, truncated, parse_gap_count
            ) VALUES (
                'old-snapshot', 'old-repository', '1', '1', '1', 'completed',
                'source', 0, 0, 0, 0, '2026-01-01T00:00:00.000Z',
                '2026-01-01T00:00:00.000Z', 0, 0, 0
            )
            """
        )

    store = SnapshotStore(data)
    service = RepositoryReviewService(store=store)

    assert store.get_snapshot("old-snapshot").schema_version == "1"
    assert service.relationship_summary("old-snapshot")["supported"] is False
    assert service.relationships("old-snapshot")["items"] == []
    assert service.cycles("old-snapshot")["items"] == []
    assert service.finding_summary("old-snapshot")["supported"] is False
    assert service.findings("old-snapshot")["items"] == []
    old_status = service.snapshot_evidence_status("old-snapshot")
    assert [item.code for item in old_status.limitations] == [
        "observation-state-unknown",
        "lifecycle-analysis-status-unavailable",
    ]
    assert (
        service.snapshot_evidence_status("old-snapshot", surface="overview").limitations[0].code
        == "observation-state-unknown"
    )
    assert (
        service.snapshot_evidence_status("old-snapshot", surface="relationships").limitations[0].code
        == "snapshot-schema-unsupported"
    )
    assert (
        service.snapshot_evidence_status("old-snapshot", surface="findings").limitations[0].code
        == "snapshot-schema-unsupported"
    )
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT version FROM schema_version").fetchone()[0] == DATABASE_SCHEMA_VERSION
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM relationships WHERE snapshot_id = 'old-snapshot'"
            ).fetchone()[0]
            == 0
        )
    with store._connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_relationship_schema_v2_migrates_without_finding_reinterpretation(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    database = data / "repository-review.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        connection.execute("INSERT INTO schema_version (version) VALUES (2)")
        connection.executescript(snapshot_store_module._SCHEMA_V1)
        connection.executescript(snapshot_store_module._SCHEMA_V2)
        connection.execute(
            """
            INSERT INTO repositories (
                repository_id, display_name, canonical_path, git_root, branch,
                git_sha, dirty, staged, untracked, configuration_digest,
                source_roots_json, test_roots_json
            ) VALUES ('v2-repository', 'v2', ?, NULL, NULL, NULL, 0, 0, 0, 'config', '[]', '[]')
            """,
            (str(tmp_path / "v2"),),
        )
        connection.execute(
            """
            INSERT INTO snapshots (
                snapshot_id, repository_id, analyzer_version, schema_version,
                rule_set_version, state, source_fingerprint, file_count,
                included_file_count, module_count, symbol_count, started_at,
                completed_at, duration_ms, truncated, parse_gap_count
            ) VALUES (
                'v2-snapshot', 'v2-repository', '3', '2', '3', 'completed',
                'source', 0, 0, 0, 0, '2026-01-01T00:00:00.000Z',
                '2026-01-01T00:00:00.000Z', 0, 0, 0
            )
            """
        )

    store = SnapshotStore(data)
    service = RepositoryReviewService(store=store)

    assert store.get_snapshot("v2-snapshot").schema_version == "2"
    assert service.relationship_summary("v2-snapshot")["supported"] is True
    assert service.finding_summary("v2-snapshot")["supported"] is False
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT version FROM schema_version").fetchone()[0] == DATABASE_SCHEMA_VERSION
        )
        assert connection.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0


def test_finding_schema_v3_migrates_analysis_generations_idempotently(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    database = data / "repository-review.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        connection.execute("INSERT INTO schema_version (version) VALUES (3)")
        connection.executescript(snapshot_store_module._SCHEMA_V1)
        connection.executescript(snapshot_store_module._SCHEMA_V2)
        connection.executescript(snapshot_store_module._SCHEMA_V3)
        connection.execute(
            """
            INSERT INTO repositories (
                repository_id, display_name, canonical_path, git_root, branch,
                git_sha, dirty, staged, untracked, configuration_digest,
                source_roots_json, test_roots_json
            ) VALUES ('repository', 'repository', ?, NULL, NULL, NULL, 0, 0, 0, 'config', '[]', '[]')
            """,
            (str(tmp_path / "repository"),),
        )
        connection.executemany(
            """
            INSERT INTO analyses (
                analysis_id, repository_id, state, progress_completed,
                progress_total, progress_phase, message, started_at,
                completed_at, snapshot_id
            ) VALUES (?, 'repository', 'started', 0, 0, 'discovery', NULL, ?, NULL, NULL)
            """,
            (
                ("analysis-00000001", "2026-07-27T10:00:00.000Z"),
                ("analysis-00000002", "2026-07-27T10:00:01.000Z"),
            ),
        )

    first = SnapshotStore(data)
    second = SnapshotStore(data)

    assert first.database_path == second.database_path
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT repository_generation, lifecycle_reconciled,
                   reconciliation_skip_reason
            FROM analyses
            ORDER BY analysis_id
            """
        ).fetchall()
        repository = connection.execute(
            """
            SELECT latest_analysis_generation
            FROM repositories
            WHERE repository_id = 'repository'
            """
        ).fetchone()
        version = connection.execute("SELECT version FROM schema_version").fetchone()[0]
    assert [row["repository_generation"] for row in rows] == [1, 2]
    assert [row["lifecycle_reconciled"] for row in rows] == [0, 0]
    assert all(row["reconciliation_skip_reason"] is None for row in rows)
    assert repository["latest_analysis_generation"] == 2
    assert version == DATABASE_SCHEMA_VERSION
