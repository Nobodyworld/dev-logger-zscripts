from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from zscripts.application.repository_review import RepositoryReviewService, SourceEvidenceError
from zscripts.domain.repository_review import AnalysisEvidence, AnalysisState
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
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 3
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM relationships WHERE snapshot_id = 'old-snapshot'"
            ).fetchone()[0]
            == 0
        )
    with store._connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_relationship_schema_v2_migrates_to_v3_without_finding_reinterpretation(
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
        assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0
