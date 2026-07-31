"""Narrow SQLite repository for atomic repository-review snapshots."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from zscripts.domain.repository_comparison import (
    HANDOFF_FORMAT_VERSION,
    SavedHandoffRecord,
    rendered_output_digest,
)
from zscripts.domain.repository_review import (
    AnalysisEvidence,
    AnalysisState,
    CycleGroupRecord,
    DiagnosticRecord,
    FileRecord,
    FindingEvidenceRecord,
    FindingLifecycleRecord,
    GraphNodeRecord,
    MetricRecord,
    RelationshipRecord,
    RepositoryRecord,
    ReviewDecisionRecord,
    ReviewEventRecord,
    SnapshotRecord,
    SymbolRecord,
)

DATABASE_SCHEMA_VERSION = 6
SYMBOL_SORT_COLUMNS: dict[str, str] = {
    "qualified_name": "qualified_name",
    "kind": "kind",
    "signature": "signature",
    "module": "module_name",
    "file": "relative_path",
    "line": "start_line",
    "visibility": "visibility",
}
FINDING_SORT_COLUMNS: dict[str, str] = {
    "severity": "CASE o.severity WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END",
    "family": "o.family",
    "status": "effective_status",
    "first_seen": "f.first_seen_snapshot_id",
    "last_seen": "f.last_seen_snapshot_id",
    "qualified_subject": "o.subject_keys_json",
    "finding_id": "o.finding_id",
}
FINDING_FAMILIES = frozenset(
    {
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
)
FINDING_QUEUE_PRESET_VERSION = "1"
FINDING_QUEUE_PRESETS = frozenset({"all", "high-signal-v1"})
RECONCILIATION_SKIP_REASONS = frozenset(
    {
        "truncated-scan",
        "parse-gaps",
        "superseded-by-newer-analysis",
        "analysis-status-unavailable",
    }
)
_HIGH_SIGNAL_CYCLE_FAMILIES = frozenset({"dependency-cycle", "inheritance-cycle"})
_HIGH_SIGNAL_MEASURED_FAMILIES = frozenset(
    {"oversized", "complexity", "nesting", "parameters", "coupling", "inheritance"}
)
REVIEW_STATUSES = frozenset({"new", "reviewed", "needs-action", "accepted", "dismissed"})
REASON_CODES = frozenset(
    {
        "intentional-design",
        "false-positive",
        "accepted-risk",
        "planned-refactor",
        "needs-investigation",
        "other",
    }
)
_FINDING_SELECT = """
SELECT
    o.finding_id AS o_finding_id,
    o.rule_id AS o_rule_id,
    o.rule_version AS o_rule_version,
    o.family AS o_family,
    o.title AS o_title,
    o.explanation AS o_explanation,
    o.suggested_action AS o_suggested_action,
    o.severity AS o_severity,
    o.confidence AS o_confidence,
    o.subject_type AS o_subject_type,
    o.subject_keys_json AS o_subject_keys_json,
    o.affected_node_ids_json AS o_affected_node_ids_json,
    o.relative_path AS o_relative_path,
    o.line AS o_line,
    o.metric_evidence_json AS o_metric_evidence_json,
    o.threshold_evidence_json AS o_threshold_evidence_json,
    f.repository_id AS f_repository_id,
    f.first_seen_snapshot_id AS f_first_seen_snapshot_id,
    f.last_seen_snapshot_id AS f_last_seen_snapshot_id,
    f.evidence_state AS f_evidence_state,
    f.resolved_snapshot_id AS f_resolved_snapshot_id,
    r.review_status AS r_review_status,
    r.note AS r_note,
    r.reason_code AS r_reason_code,
    r.version AS r_version,
    r.decided_at AS r_decided_at,
    r.updated_at AS r_updated_at,
    CASE
        WHEN f.evidence_state = 'resolved' THEN 'resolved'
        ELSE r.review_status
    END AS effective_status
FROM finding_occurrences o
JOIN findings f USING (finding_id)
JOIN finding_reviews r USING (finding_id)
"""


@dataclass(frozen=True, slots=True)
class SymbolPage:
    """A bounded page of symbols returned by an allowlisted query."""

    items: tuple[SymbolRecord, ...]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True, slots=True)
class RelationshipPage:
    """A bounded page of relationship evidence."""

    items: tuple[RelationshipRecord, ...]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True, slots=True)
class GraphNodePage:
    """A bounded page of graph nodes returned by an allowlisted query."""

    items: tuple[GraphNodeRecord, ...]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True, slots=True)
class StoredFindingRecord:
    """Combined immutable evidence, lifecycle, and current review decision."""

    evidence: FindingEvidenceRecord
    lifecycle: FindingLifecycleRecord
    review: ReviewDecisionRecord


@dataclass(frozen=True, slots=True)
class FindingPage:
    """A bounded page of findings returned by allowlisted filters."""

    items: tuple[StoredFindingRecord, ...]
    total: int
    page: int
    page_size: int
    preset: str


@dataclass(frozen=True, slots=True)
class AnalysisStatusRecord:
    """Persisted state for an in-process analysis job."""

    analysis_id: str
    repository_id: str
    state: AnalysisState
    progress_completed: int
    progress_total: int
    progress_phase: str
    message: str | None
    started_at: str
    completed_at: str | None
    snapshot_id: str | None
    repository_generation: int
    lifecycle_reconciled: bool
    reconciliation_skip_reason: str | None


@dataclass(frozen=True, slots=True)
class SnapshotEvidenceFacts:
    """Lightweight exact-snapshot facts used by status and comparison presentation."""

    snapshot: SnapshotRecord
    observed_state_known: bool
    observed_branch: str | None
    observed_git_sha: str | None
    observed_dirty: bool | None
    observed_staged: bool | None
    observed_untracked: bool | None
    lifecycle_reconciled: bool
    reconciliation_skip_reason: str | None


@dataclass(frozen=True, slots=True)
class ComparisonSnapshotEvidence:
    """Exact immutable evidence loaded for one transient comparison."""

    repository: RepositoryRecord
    snapshot: SnapshotRecord
    observed_state_known: bool
    observed_branch: str | None
    observed_git_sha: str | None
    observed_dirty: bool | None
    observed_staged: bool | None
    observed_untracked: bool | None
    lifecycle_reconciled: bool
    reconciliation_skip_reason: str | None
    files: tuple[FileRecord, ...]
    symbols: tuple[SymbolRecord, ...]
    graph_nodes: tuple[GraphNodeRecord, ...]
    relationships: tuple[RelationshipRecord, ...]
    cycles: tuple[CycleGroupRecord, ...]
    metrics: tuple[MetricRecord, ...]
    findings: tuple[FindingEvidenceRecord, ...]


class SnapshotNotFoundError(LookupError):
    """Raised when a completed snapshot cannot be found."""


class ReviewConflictError(RuntimeError):
    """Raised when an optimistic review update uses a stale version."""

    def __init__(self, current: StoredFindingRecord) -> None:
        super().__init__("Finding review version conflict.")
        self.current = current


class SavedHandoffIntegrityError(ValueError):
    """Raised when persisted rendered handoff bytes fail their format digest."""


class SnapshotStore:
    """Persist metadata-only evidence through explicit SQLite transactions."""

    def __init__(self, data_directory: Path | None = None) -> None:
        self.data_directory = resolve_app_data_directory(data_directory)
        self.data_directory.mkdir(parents=True, exist_ok=True)
        self.database_path = self.data_directory / "repository-review.sqlite3"
        self._initialize()

    def register_repository(self, repository: RepositoryRecord) -> None:
        with self._transaction() as connection:
            self._upsert_repository(connection, repository)

    def allocate_analysis_id(self) -> str:
        """Allocate a process-independent internal job identifier."""

        with self._transaction() as connection:
            cursor = connection.execute("INSERT INTO analysis_sequence DEFAULT VALUES")
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return an analysis sequence identifier.")
            value = cursor.lastrowid
        return f"analysis-{value:08d}"

    def begin_analysis(
        self,
        *,
        analysis_id: str,
        repository: RepositoryRecord,
        started_at: str,
    ) -> None:
        with self._transaction() as connection:
            self._upsert_repository(connection, repository)
            connection.execute(
                """
                UPDATE repositories
                SET latest_analysis_generation = latest_analysis_generation + 1
                WHERE repository_id = ?
                """,
                (repository.repository_id,),
            )
            generation_row = connection.execute(
                """
                SELECT latest_analysis_generation
                FROM repositories
                WHERE repository_id = ?
                """,
                (repository.repository_id,),
            ).fetchone()
            if generation_row is None:
                raise RuntimeError("Repository disappeared before analysis generation allocation.")
            connection.execute(
                """
                INSERT INTO analyses (
                    analysis_id, repository_id, state, progress_completed,
                    progress_total, progress_phase, message, started_at,
                    completed_at, snapshot_id, repository_generation,
                    lifecycle_reconciled, reconciliation_skip_reason
                ) VALUES (?, ?, ?, 0, 0, 'discovery', NULL, ?, NULL, NULL, ?, 0, NULL)
                """,
                (
                    analysis_id,
                    repository.repository_id,
                    AnalysisState.STARTED.value,
                    started_at,
                    int(generation_row["latest_analysis_generation"]),
                ),
            )

    def update_analysis_progress(
        self,
        analysis_id: str,
        *,
        completed: int,
        total: int,
        phase: str,
    ) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE analyses
                SET progress_completed = ?, progress_total = ?, progress_phase = ?
                WHERE analysis_id = ?
                """,
                (completed, total, phase, analysis_id),
            )

    def finish_analysis(
        self,
        analysis_id: str,
        *,
        state: AnalysisState,
        completed_at: str,
        message: str | None = None,
    ) -> None:
        if state not in {AnalysisState.CANCELLED, AnalysisState.FAILED}:
            raise ValueError("finish_analysis is reserved for cancelled or failed attempts.")
        with self._transaction() as connection:
            connection.execute(
                """
                UPDATE analyses
                SET state = ?, message = ?, completed_at = ?, progress_phase = ?
                WHERE analysis_id = ?
                """,
                (state.value, message, completed_at, state.value, analysis_id),
            )

    def save_completed_snapshot(self, analysis_id: str, evidence: AnalysisEvidence) -> None:
        """Atomically promote one completed evidence set and its child rows."""

        if evidence.snapshot.state is not AnalysisState.COMPLETED:
            raise ValueError("Only completed snapshots may be promoted.")
        with self._transaction() as connection:
            self._upsert_repository(connection, evidence.repository)
            analysis = connection.execute(
                """
                SELECT a.repository_id, a.repository_generation,
                       r.latest_analysis_generation
                FROM analyses a
                JOIN repositories r USING (repository_id)
                WHERE a.analysis_id = ?
                """,
                (analysis_id,),
            ).fetchone()
            if analysis is None:
                raise RuntimeError("Analysis state disappeared before atomic snapshot promotion.")
            if str(analysis["repository_id"]) != evidence.repository.repository_id:
                raise RuntimeError("Analysis repository changed before atomic snapshot promotion.")
            existing = connection.execute(
                "SELECT 1 FROM snapshots WHERE snapshot_id = ?",
                (evidence.snapshot.snapshot_id,),
            ).fetchone()
            if existing is None:
                self._insert_snapshot(connection, evidence)
            authoritative = int(analysis["repository_generation"]) == int(
                analysis["latest_analysis_generation"]
            )
            reconciliation_skip_reason: str | None
            if not authoritative:
                reconciliation_skip_reason = "superseded-by-newer-analysis"
            elif evidence.snapshot.truncated:
                reconciliation_skip_reason = "truncated-scan"
            elif evidence.snapshot.parse_gap_count > 0:
                reconciliation_skip_reason = "parse-gaps"
            else:
                reconciliation_skip_reason = None
            if authoritative:
                self._reconcile_findings(
                    connection,
                    evidence,
                    resolve_missing=reconciliation_skip_reason is None,
                )
            updated = connection.execute(
                """
                UPDATE analyses
                SET state = ?, progress_completed = ?, progress_total = ?,
                    progress_phase = 'completed', message = NULL,
                    completed_at = ?, snapshot_id = ?,
                    lifecycle_reconciled = ?,
                    reconciliation_skip_reason = ?
                WHERE analysis_id = ?
                """,
                (
                    AnalysisState.COMPLETED.value,
                    evidence.snapshot.included_file_count,
                    evidence.snapshot.included_file_count,
                    evidence.snapshot.completed_at,
                    evidence.snapshot.snapshot_id,
                    int(authoritative),
                    reconciliation_skip_reason,
                    analysis_id,
                ),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Analysis state disappeared before atomic snapshot promotion.")

    def get_analysis(self, analysis_id: str) -> AnalysisStatusRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM analyses WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()
        return _analysis_from_row(row) if row is not None else None

    def list_repositories(self) -> tuple[RepositoryRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT repositories.*
                FROM repositories
                WHERE EXISTS (
                    SELECT 1 FROM snapshots
                    WHERE snapshots.repository_id = repositories.repository_id
                      AND snapshots.state = 'completed'
                )
                ORDER BY display_name COLLATE NOCASE, repository_id
                """
            ).fetchall()
        return tuple(_repository_from_row(row) for row in rows)

    def get_repository(self, repository_id: str) -> RepositoryRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM repositories WHERE repository_id = ?",
                (repository_id,),
            ).fetchone()
        return _repository_from_row(row) if row is not None else None

    def list_snapshots(self, repository_id: str) -> tuple[SnapshotRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM snapshots
                WHERE repository_id = ? AND state = 'completed'
                ORDER BY completed_at DESC, snapshot_id
                """,
                (repository_id,),
            ).fetchall()
        return tuple(_snapshot_from_row(row) for row in rows)

    def get_snapshot(self, snapshot_id: str) -> SnapshotRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM snapshots WHERE snapshot_id = ? AND state = 'completed'",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise SnapshotNotFoundError("Completed snapshot was not found.")
        return _snapshot_from_row(row)

    def get_snapshot_repository(self, snapshot_id: str) -> RepositoryRecord:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT repositories.*
                FROM repositories
                JOIN snapshots USING (repository_id)
                WHERE snapshots.snapshot_id = ? AND snapshots.state = 'completed'
                """,
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise SnapshotNotFoundError("Completed snapshot was not found.")
        return _repository_from_row(row)

    def snapshot_evidence_facts(self, snapshot_id: str) -> SnapshotEvidenceFacts:
        """Load bounded presentation facts linked to one exact completed snapshot."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT snapshots.*,
                       analyses.analysis_id AS linked_analysis_id,
                       analyses.lifecycle_reconciled AS linked_lifecycle_reconciled,
                       analyses.reconciliation_skip_reason AS linked_skip_reason
                FROM snapshots
                LEFT JOIN analyses ON analyses.analysis_id = (
                    SELECT candidate.analysis_id
                    FROM analyses AS candidate
                    WHERE candidate.snapshot_id = snapshots.snapshot_id
                      AND candidate.state = 'completed'
                    ORDER BY candidate.repository_generation DESC,
                             candidate.analysis_id DESC
                    LIMIT 1
                )
                WHERE snapshots.snapshot_id = ? AND snapshots.state = 'completed'
                """,
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise SnapshotNotFoundError("Completed snapshot was not found.")
        analysis_available = row["linked_analysis_id"] is not None
        lifecycle_reconciled = bool(row["linked_lifecycle_reconciled"]) if analysis_available else False
        raw_reason = str(row["linked_skip_reason"]) if row["linked_skip_reason"] is not None else None
        if raw_reason not in RECONCILIATION_SKIP_REASONS:
            raw_reason = None
        if not analysis_available or (not lifecycle_reconciled and raw_reason is None):
            raw_reason = "analysis-status-unavailable"
        observed_state_known = bool(row["observed_state_known"])
        return SnapshotEvidenceFacts(
            snapshot=_snapshot_from_row(row),
            observed_state_known=observed_state_known,
            observed_branch=(
                str(row["observed_branch"])
                if observed_state_known and row["observed_branch"] is not None
                else None
            ),
            observed_git_sha=(
                str(row["observed_git_sha"])
                if observed_state_known and row["observed_git_sha"] is not None
                else None
            ),
            observed_dirty=bool(row["observed_dirty"]) if observed_state_known else None,
            observed_staged=bool(row["observed_staged"]) if observed_state_known else None,
            observed_untracked=bool(row["observed_untracked"]) if observed_state_known else None,
            lifecycle_reconciled=lifecycle_reconciled,
            reconciliation_skip_reason=raw_reason,
        )

    def list_symbols(
        self,
        snapshot_id: str,
        *,
        search: str = "",
        kind: str | None = None,
        module: str | None = None,
        visibility: str | None = None,
        sort: str = "qualified_name",
        direction: str = "asc",
        page: int = 1,
        page_size: int = 50,
    ) -> SymbolPage:
        if sort not in SYMBOL_SORT_COLUMNS:
            raise ValueError("Unsupported symbol sort field.")
        if direction not in {"asc", "desc"}:
            raise ValueError("Sort direction must be 'asc' or 'desc'.")
        if page < 1 or page_size < 1 or page_size > 200:
            raise ValueError("Symbol pagination is outside the supported range.")
        self.get_snapshot(snapshot_id)
        clauses = ["snapshot_id = ?"]
        parameters: list[object] = [snapshot_id]
        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            clauses.append("(qualified_name LIKE ? ESCAPE '\\' OR signature LIKE ? ESCAPE '\\')")
            parameters.extend((f"%{escaped}%", f"%{escaped}%"))
        for column, value in (("kind", kind), ("module_name", module), ("visibility", visibility)):
            if value:
                clauses.append(f"{column} = ?")
                parameters.append(value)
        where = " AND ".join(clauses)
        order_column = SYMBOL_SORT_COLUMNS[sort]
        offset = (page - 1) * page_size
        with self._connect() as connection:
            total = int(
                connection.execute(
                    # Clauses are assembled only from fixed column fragments above.
                    f"SELECT COUNT(*) FROM symbols WHERE {where}",  # nosec B608
                    parameters,
                ).fetchone()[0]
            )
            # All interpolated clauses, columns, and direction tokens are allowlisted.
            symbol_query = (
                f"SELECT * FROM symbols WHERE {where} "  # nosec B608
                f"ORDER BY {order_column} {direction.upper()}, symbol_id ASC "  # nosec B608
                "LIMIT ? OFFSET ?"
            )
            rows = connection.execute(
                symbol_query,
                (*parameters, page_size, offset),
            ).fetchall()
        return SymbolPage(
            items=tuple(_symbol_from_row(row) for row in rows),
            total=total,
            page=page,
            page_size=page_size,
        )

    def list_symbol_filters(self, snapshot_id: str) -> dict[str, tuple[str, ...]]:
        self.get_snapshot(snapshot_id)
        with self._connect() as connection:
            result: dict[str, tuple[str, ...]] = {}
            for public_name, column in (
                ("kinds", "kind"),
                ("modules", "module_name"),
                ("visibilities", "visibility"),
            ):
                # The column token comes only from the fixed internal tuple above.
                filter_query = (
                    f"SELECT DISTINCT {column} FROM symbols "  # nosec B608
                    "WHERE snapshot_id = ? "
                    f"ORDER BY {column} COLLATE NOCASE"  # nosec B608
                )
                rows = connection.execute(
                    filter_query,
                    (snapshot_id,),
                ).fetchall()
                result[public_name] = tuple(str(row[0]) for row in rows)
        return result

    def overview_counts(self, snapshot_id: str) -> dict[str, int]:
        """Return exact aggregate counts without loading full symbol rows."""

        self.get_snapshot(snapshot_id)
        with self._connect() as connection:
            symbol_rows = connection.execute(
                """
                SELECT kind, COUNT(*) AS count
                FROM symbols
                WHERE snapshot_id = ?
                GROUP BY kind
                """,
                (snapshot_id,),
            ).fetchall()
            package_count = int(
                connection.execute(
                    """
                    SELECT COUNT(DISTINCT package_name)
                    FROM modules
                    WHERE snapshot_id = ? AND package_name <> ''
                    """,
                    (snapshot_id,),
                ).fetchone()[0]
            )
        counts = {str(row["kind"]): int(row["count"]) for row in symbol_rows}
        counts["packages"] = package_count
        return counts

    def relationship_overview_counts(self, snapshot_id: str) -> dict[str, int | bool]:
        snapshot = self.get_snapshot(snapshot_id)
        supported = _version_at_least(snapshot.schema_version, 2)
        if not supported:
            return {
                "relationship_analysis_supported": False,
                "resolved_import_edges": 0,
                "inheritance_edges": 0,
                "cycle_groups": 0,
                "largest_cycle_size": 0,
            }
        with self._connect() as connection:
            resolved_imports = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM relationships
                    WHERE snapshot_id = ? AND relationship_type = 'imports'
                      AND target_id IS NOT NULL
                      AND resolution_status IN ('resolved-static', 'probable-static')
                    """,
                    (snapshot_id,),
                ).fetchone()[0]
            )
            inheritance_edges = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM relationships
                    WHERE snapshot_id = ? AND relationship_type = 'inherits'
                      AND target_id IS NOT NULL
                      AND resolution_status IN ('resolved-static', 'probable-static')
                    """,
                    (snapshot_id,),
                ).fetchone()[0]
            )
            cycle_row = connection.execute(
                """
                SELECT COUNT(DISTINCT cycle_id) AS count,
                       COALESCE(MAX(member_count), 0) AS largest
                FROM (
                    SELECT cycle_id, COUNT(*) AS member_count
                    FROM cycle_members
                    WHERE snapshot_id = ?
                    GROUP BY cycle_id
                )
                """,
                (snapshot_id,),
            ).fetchone()
        return {
            "relationship_analysis_supported": True,
            "resolved_import_edges": resolved_imports,
            "inheritance_edges": inheritance_edges,
            "cycle_groups": int(cycle_row["count"]),
            "largest_cycle_size": int(cycle_row["largest"]),
        }

    def list_graph_nodes(self, snapshot_id: str) -> tuple[GraphNodeRecord, ...]:
        self.get_snapshot(snapshot_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM graph_nodes
                WHERE snapshot_id = ?
                ORDER BY qualified_name COLLATE NOCASE, node_id
                """,
                (snapshot_id,),
            ).fetchall()
        return tuple(_graph_node_from_row(row) for row in rows)

    def query_graph_nodes(
        self,
        snapshot_id: str,
        *,
        mode: str,
        search: str = "",
        node_ids: tuple[str, ...] = (),
        page: int = 1,
        page_size: int = 100,
    ) -> GraphNodePage:
        self.get_snapshot(snapshot_id)
        mode_clauses = {
            "modules": "node_type = 'module'",
            "packages": "node_type = 'package'",
            "inheritance": "node_type = 'symbol' AND symbol_kind = 'class'",
            "containment": "node_type IN ('package', 'module', 'symbol')",
            "types": "node_type = 'symbol'",
        }
        if mode not in mode_clauses:
            raise ValueError("Unsupported relationship graph mode.")
        normalized_search = search.strip()
        if len(normalized_search) > 200:
            raise ValueError("Graph node search is outside the supported range.")
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("Graph node pagination is outside the supported range.")
        if len(node_ids) > 100 or any(not 16 <= len(node_id) <= 128 for node_id in node_ids):
            raise ValueError("Graph node identifiers are outside the supported range.")

        clauses = ["snapshot_id = ?", mode_clauses[mode]]
        parameters: list[object] = [snapshot_id]
        if normalized_search:
            clauses.append("instr(lower(qualified_name), lower(?)) > 0")
            parameters.append(normalized_search)
        if node_ids:
            placeholders = ", ".join("?" for _ in node_ids)
            clauses.append(f"node_id IN ({placeholders})")  # nosec B608
            parameters.extend(node_ids)
        where = " AND ".join(clauses)
        offset = (page - 1) * page_size
        with self._connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM graph_nodes WHERE {where}",  # nosec B608
                    parameters,
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT * FROM graph_nodes
                WHERE {where}
                ORDER BY qualified_name COLLATE NOCASE, qualified_name, node_id
                LIMIT ? OFFSET ?
                """,  # nosec B608
                (*parameters, page_size, offset),
            ).fetchall()
        return GraphNodePage(
            items=tuple(_graph_node_from_row(row) for row in rows),
            total=total,
            page=page,
            page_size=page_size,
        )

    def list_relationships(
        self,
        snapshot_id: str,
        *,
        relationship_type: str | None = None,
        resolution_status: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> RelationshipPage:
        self.get_snapshot(snapshot_id)
        if relationship_type is not None and relationship_type not in {
            "contains",
            "imports",
            "inherits",
            "references-type",
        }:
            raise ValueError("Unsupported relationship type.")
        if resolution_status is not None and resolution_status not in {
            "resolved-static",
            "probable-static",
            "ambiguous",
            "unresolved-dynamic",
        }:
            raise ValueError("Unsupported relationship resolution status.")
        if page < 1 or page_size < 1 or page_size > 200:
            raise ValueError("Relationship pagination is outside the supported range.")
        clauses = ["snapshot_id = ?"]
        parameters: list[object] = [snapshot_id]
        if relationship_type is not None:
            clauses.append("relationship_type = ?")
            parameters.append(relationship_type)
        if resolution_status is not None:
            clauses.append("resolution_status = ?")
            parameters.append(resolution_status)
        where = " AND ".join(clauses)
        offset = (page - 1) * page_size
        with self._connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM relationships WHERE {where}",  # nosec B608
                    parameters,
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT * FROM relationships
                WHERE {where}
                ORDER BY relationship_type, source_id,
                         COALESCE(target_id, unresolved_target, ''),
                         relative_path, line, column_number, relationship_id
                LIMIT ? OFFSET ?
                """,  # nosec B608
                (*parameters, page_size, offset),
            ).fetchall()
        return RelationshipPage(
            items=tuple(_relationship_from_row(row) for row in rows),
            total=total,
            page=page,
            page_size=page_size,
        )

    def all_relationships(self, snapshot_id: str) -> tuple[RelationshipRecord, ...]:
        self.get_snapshot(snapshot_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM relationships
                WHERE snapshot_id = ?
                ORDER BY relationship_type, source_id,
                         COALESCE(target_id, unresolved_target, ''),
                         relative_path, line, column_number, relationship_id
                """,
                (snapshot_id,),
            ).fetchall()
        return tuple(_relationship_from_row(row) for row in rows)

    def list_cycles(
        self,
        snapshot_id: str,
        *,
        relationship_type: str | None = None,
        limit: int = 100,
    ) -> tuple[CycleGroupRecord, ...]:
        self.get_snapshot(snapshot_id)
        if relationship_type is not None and relationship_type not in {"imports", "inherits"}:
            raise ValueError("Unsupported cycle relationship type.")
        if limit < 1 or limit > 200:
            raise ValueError("Cycle result limit is outside the supported range.")
        clauses = ["snapshot_id = ?"]
        parameters: list[object] = [snapshot_id]
        if relationship_type is not None:
            clauses.append("relationship_type = ?")
            parameters.append(relationship_type)
        where = " AND ".join(clauses)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM cycle_groups
                WHERE {where}
                ORDER BY cycle_id
                LIMIT ?
                """,  # nosec B608
                (*parameters, limit),
            ).fetchall()
            groups: list[CycleGroupRecord] = []
            for row in rows:
                members = connection.execute(
                    """
                    SELECT node_id FROM cycle_members
                    WHERE snapshot_id = ? AND cycle_id = ?
                    ORDER BY node_id
                    """,
                    (snapshot_id, row["cycle_id"]),
                ).fetchall()
                edges = connection.execute(
                    """
                    SELECT relationship_id FROM cycle_edges
                    WHERE snapshot_id = ? AND cycle_id = ?
                    ORDER BY relationship_id
                    """,
                    (snapshot_id, row["cycle_id"]),
                ).fetchall()
                groups.append(
                    CycleGroupRecord(
                        cycle_id=str(row["cycle_id"]),
                        relationship_type=str(row["relationship_type"]),
                        member_node_ids=tuple(str(item["node_id"]) for item in members),
                        edge_ids=tuple(str(item["relationship_id"]) for item in edges),
                    )
                )
        return tuple(groups)

    def finding_overview_counts(self, snapshot_id: str) -> dict[str, int]:
        snapshot = self.get_snapshot(snapshot_id)
        if not _version_at_least(snapshot.schema_version, 3):
            return {
                "active_findings": 0,
                "needs_action_findings": 0,
                "resolved_since_last_scan": 0,
                "high_confidence_high_severity_findings": 0,
            }
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    SUM(f.evidence_state = 'active') AS active_findings,
                    SUM(f.evidence_state = 'active' AND r.review_status = 'needs-action')
                        AS needs_action_findings,
                    SUM(f.resolved_snapshot_id = ?) AS resolved_since_last_scan,
                    SUM(
                        f.evidence_state = 'active'
                        AND o.severity = 'high'
                        AND o.confidence = 'high'
                    ) AS high_confidence_high_severity_findings
                FROM findings f
                JOIN finding_reviews r USING (finding_id)
                JOIN finding_occurrences o
                  ON o.finding_id = f.finding_id
                 AND o.snapshot_id = f.last_seen_snapshot_id
                WHERE f.repository_id = ?
                """,
                (snapshot_id, snapshot.repository_id),
            ).fetchone()
        return {
            key: int(row[key] or 0)
            for key in (
                "active_findings",
                "needs_action_findings",
                "resolved_since_last_scan",
                "high_confidence_high_severity_findings",
            )
        }

    def finding_summary(self, snapshot_id: str) -> dict[str, object]:
        snapshot = self.get_snapshot(snapshot_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT f.evidence_state, r.review_status, o.severity, o.confidence, o.family
                FROM findings f
                JOIN finding_reviews r USING (finding_id)
                JOIN finding_occurrences o
                  ON o.finding_id = f.finding_id
                 AND o.snapshot_id = f.last_seen_snapshot_id
                WHERE f.repository_id = ?
                """,
                (snapshot.repository_id,),
            ).fetchall()
            reconciliation = connection.execute(
                """
                SELECT lifecycle_reconciled, reconciliation_skip_reason
                FROM analyses
                WHERE repository_id = ? AND state = 'completed'
                ORDER BY repository_generation DESC, completed_at DESC, analysis_id DESC
                LIMIT 1
                """,
                (snapshot.repository_id,),
            ).fetchone()
        severity = {"high": 0, "medium": 0, "low": 0}
        families = {family: 0 for family in sorted(FINDING_FAMILIES)}
        active = resolved = needs_action = accepted = dismissed = low_confidence = 0
        for row in rows:
            state = str(row["evidence_state"])
            if state == "active":
                active += 1
                status = str(row["review_status"])
                if status == "needs-action":
                    needs_action += 1
                elif status == "accepted":
                    accepted += 1
                elif status == "dismissed":
                    dismissed += 1
            else:
                resolved += 1
            severity[str(row["severity"])] += 1
            families[str(row["family"])] += 1
            if str(row["confidence"]) == "low":
                low_confidence += 1
        return {
            "active": active,
            "resolved": resolved,
            "needs_action": needs_action,
            "accepted": accepted,
            "dismissed": dismissed,
            "severity": severity,
            "families": families,
            "low_confidence": low_confidence,
            "reconciliation_complete": (
                reconciliation is not None
                and bool(reconciliation["lifecycle_reconciled"])
                and reconciliation["reconciliation_skip_reason"] is None
            ),
            "lifecycle_reconciled": (
                bool(reconciliation["lifecycle_reconciled"]) if reconciliation is not None else False
            ),
            "reconciliation_skip_reason": (
                str(reconciliation["reconciliation_skip_reason"])
                if reconciliation is not None and reconciliation["reconciliation_skip_reason"] is not None
                else ("analysis-status-unavailable" if reconciliation is None else None)
            ),
        }

    def list_findings(
        self,
        snapshot_id: str,
        *,
        preset: str = "all",
        family: str | None = None,
        severity: str | None = None,
        confidence: str | None = None,
        effective_status: str | None = None,
        evidence_state: str | None = None,
        search: str = "",
        sort: str = "severity",
        direction: str = "desc",
        page: int = 1,
        page_size: int = 50,
    ) -> FindingPage:
        if preset not in FINDING_QUEUE_PRESETS:
            raise ValueError("Unsupported finding queue preset.")
        if family is not None and family not in FINDING_FAMILIES:
            raise ValueError("Unsupported finding family.")
        if severity is not None and severity not in {"high", "medium", "low"}:
            raise ValueError("Unsupported finding severity.")
        if confidence is not None and confidence not in {"high", "medium", "low"}:
            raise ValueError("Unsupported finding confidence.")
        if effective_status is not None and effective_status not in {*REVIEW_STATUSES, "resolved"}:
            raise ValueError("Unsupported effective finding status.")
        if evidence_state is not None and evidence_state not in {"active", "resolved"}:
            raise ValueError("Unsupported finding evidence state.")
        if sort not in FINDING_SORT_COLUMNS or direction not in {"asc", "desc"}:
            raise ValueError("Unsupported finding sort.")
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("Finding pagination is outside the supported range.")
        if len(search) > 200:
            raise ValueError("Finding search is too long.")
        snapshot = self.get_snapshot(snapshot_id)
        conditions = [
            "f.repository_id = ?",
            "o.snapshot_id = f.last_seen_snapshot_id",
        ]
        parameters: list[object] = [snapshot.repository_id]
        if preset == "high-signal-v1":
            cycle_placeholders = ", ".join("?" for _ in _HIGH_SIGNAL_CYCLE_FAMILIES)
            measured_placeholders = ", ".join("?" for _ in _HIGH_SIGNAL_MEASURED_FAMILIES)
            conditions.append(
                f"""
                (
                    o.family IN ({cycle_placeholders})
                    OR (
                        o.family IN ({measured_placeholders})
                        AND o.severity IN ('high', 'medium')
                        AND o.confidence IN ('high', 'medium')
                    )
                )
                """
            )
            parameters.extend(sorted(_HIGH_SIGNAL_CYCLE_FAMILIES))
            parameters.extend(sorted(_HIGH_SIGNAL_MEASURED_FAMILIES))
        if family is not None:
            conditions.append("o.family = ?")
            parameters.append(family)
        if severity is not None:
            conditions.append("o.severity = ?")
            parameters.append(severity)
        if confidence is not None:
            conditions.append("o.confidence = ?")
            parameters.append(confidence)
        if effective_status is not None:
            conditions.append(
                "(CASE WHEN f.evidence_state = 'resolved' THEN 'resolved' ELSE r.review_status END) = ?"
            )
            parameters.append(effective_status)
        if evidence_state is not None:
            conditions.append("f.evidence_state = ?")
            parameters.append(evidence_state)
        if search:
            conditions.append(
                "(instr(lower(o.title), lower(?)) > 0 OR instr(lower(o.subject_keys_json), lower(?)) > 0)"
            )
            parameters.extend((search, search))
        where = " AND ".join(f"({item})" for item in conditions)
        with self._connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM ({_FINDING_SELECT} WHERE {where})",  # nosec B608
                    parameters,
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                {_FINDING_SELECT}
                WHERE {where}
                ORDER BY {FINDING_SORT_COLUMNS[sort]} {direction.upper()},
                         o.finding_id ASC
                LIMIT ? OFFSET ?
                """,  # nosec B608
                (*parameters, page_size, (page - 1) * page_size),
            ).fetchall()
        return FindingPage(
            items=tuple(_stored_finding_from_row(row) for row in rows),
            total=total,
            page=page,
            page_size=page_size,
            preset=preset,
        )

    def get_finding(
        self,
        finding_id: str,
        *,
        snapshot_id: str | None = None,
    ) -> StoredFindingRecord | None:
        with self._connect() as connection:
            return _get_finding_in_connection(connection, finding_id, snapshot_id)

    def finding_history(
        self,
        finding_id: str,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[tuple[ReviewEventRecord, ...], int]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("Finding history pagination is outside the supported range.")
        with self._connect() as connection:
            total = int(
                connection.execute(
                    "SELECT COUNT(*) FROM finding_review_events WHERE finding_id = ?",
                    (finding_id,),
                ).fetchone()[0]
            )
            rows = connection.execute(
                """
                SELECT * FROM finding_review_events
                WHERE finding_id = ?
                ORDER BY event_id DESC
                LIMIT ? OFFSET ?
                """,
                (finding_id, page_size, (page - 1) * page_size),
            ).fetchall()
        return tuple(_review_event_from_row(row) for row in rows), total

    def update_finding_review(
        self,
        finding_id: str,
        *,
        expected_version: int,
        review_status: str,
        note: str,
        reason_code: str | None,
        updated_at: str,
    ) -> StoredFindingRecord:
        if review_status not in REVIEW_STATUSES:
            raise ValueError("Unsupported review status.")
        if reason_code is not None and reason_code not in REASON_CODES:
            raise ValueError("Unsupported review reason.")
        if len(note) > 2_000:
            raise ValueError("Finding review note exceeds 2,000 characters.")
        if expected_version < 0:
            raise ValueError("Expected review version is invalid.")
        with self._transaction() as connection:
            current = _get_finding_in_connection(connection, finding_id, None)
            if current is None:
                raise LookupError("Finding was not found.")
            if current.review.version != expected_version:
                raise ReviewConflictError(current)
            updated = connection.execute(
                """
                UPDATE finding_reviews
                SET review_status = ?, note = ?, reason_code = ?,
                    version = version + 1, decided_at = ?, updated_at = ?
                WHERE finding_id = ? AND version = ?
                """,
                (
                    review_status,
                    note,
                    reason_code,
                    updated_at,
                    updated_at,
                    finding_id,
                    expected_version,
                ),
            )
            if updated.rowcount != 1:
                current = _get_finding_in_connection(connection, finding_id, None)
                if current is None:
                    raise LookupError("Finding was not found.")
                raise ReviewConflictError(current)
            connection.execute(
                """
                INSERT INTO finding_review_events (
                    finding_id, event_type, snapshot_id, review_status,
                    reason_code, note, review_version, event_at
                ) VALUES (?, 'review-decision-changed', NULL, ?, ?, ?, ?, ?)
                """,
                (
                    finding_id,
                    review_status,
                    reason_code,
                    note,
                    expected_version + 1,
                    updated_at,
                ),
            )
            result = _get_finding_in_connection(connection, finding_id, None)
            if result is None:
                raise RuntimeError("Updated finding disappeared.")
            return result

    def comparison_snapshot(self, snapshot_id: str) -> ComparisonSnapshotEvidence:
        """Load exact immutable comparison evidence without current lifecycle substitution."""

        facts = self.snapshot_evidence_facts(snapshot_id)
        snapshot = facts.snapshot
        repository = self.get_snapshot_repository(snapshot_id)
        with self._connect() as connection:
            file_rows = connection.execute(
                """
                SELECT * FROM files
                WHERE snapshot_id = ?
                ORDER BY relative_path, file_id
                """,
                (snapshot_id,),
            ).fetchall()
            symbol_rows = connection.execute(
                """
                SELECT * FROM symbols
                WHERE snapshot_id = ?
                ORDER BY language, kind, qualified_name, symbol_id
                """,
                (snapshot_id,),
            ).fetchall()
            node_rows = connection.execute(
                """
                SELECT * FROM graph_nodes
                WHERE snapshot_id = ?
                ORDER BY node_type, qualified_name, node_id
                """,
                (snapshot_id,),
            ).fetchall()
            relationship_rows = connection.execute(
                """
                SELECT * FROM relationships
                WHERE snapshot_id = ?
                ORDER BY relationship_type, source_id,
                         COALESCE(target_id, unresolved_target, ''),
                         relative_path, line, column_number, relationship_id
                """,
                (snapshot_id,),
            ).fetchall()
            cycle_rows = connection.execute(
                """
                SELECT * FROM cycle_groups
                WHERE snapshot_id = ?
                ORDER BY relationship_type, cycle_id
                """,
                (snapshot_id,),
            ).fetchall()
            cycle_member_rows = connection.execute(
                """
                SELECT cycle_id, node_id FROM cycle_members
                WHERE snapshot_id = ?
                ORDER BY cycle_id, node_id
                """,
                (snapshot_id,),
            ).fetchall()
            cycle_edge_rows = connection.execute(
                """
                SELECT cycle_id, relationship_id FROM cycle_edges
                WHERE snapshot_id = ?
                ORDER BY cycle_id, relationship_id
                """,
                (snapshot_id,),
            ).fetchall()
            metric_rows = connection.execute(
                """
                SELECT * FROM metrics
                WHERE snapshot_id = ?
                ORDER BY subject_type, subject_id, metric_name, metric_id
                """,
                (snapshot_id,),
            ).fetchall()
            finding_rows = connection.execute(
                """
                SELECT * FROM finding_occurrences
                WHERE snapshot_id = ?
                ORDER BY rule_id, subject_keys_json, finding_id
                """,
                (snapshot_id,),
            ).fetchall()
        members: dict[str, list[str]] = {}
        for row in cycle_member_rows:
            members.setdefault(str(row["cycle_id"]), []).append(str(row["node_id"]))
        edges: dict[str, list[str]] = {}
        for row in cycle_edge_rows:
            edges.setdefault(str(row["cycle_id"]), []).append(str(row["relationship_id"]))
        cycles = tuple(
            CycleGroupRecord(
                cycle_id=str(row["cycle_id"]),
                relationship_type=str(row["relationship_type"]),
                member_node_ids=tuple(members.get(str(row["cycle_id"]), ())),
                edge_ids=tuple(edges.get(str(row["cycle_id"]), ())),
            )
            for row in cycle_rows
        )
        return ComparisonSnapshotEvidence(
            repository=repository,
            snapshot=snapshot,
            observed_state_known=facts.observed_state_known,
            observed_branch=facts.observed_branch,
            observed_git_sha=facts.observed_git_sha,
            observed_dirty=facts.observed_dirty,
            observed_staged=facts.observed_staged,
            observed_untracked=facts.observed_untracked,
            lifecycle_reconciled=facts.lifecycle_reconciled,
            reconciliation_skip_reason=facts.reconciliation_skip_reason,
            files=tuple(_file_from_row(row) for row in file_rows),
            symbols=tuple(_symbol_from_row(row) for row in symbol_rows),
            graph_nodes=tuple(_graph_node_from_row(row) for row in node_rows),
            relationships=tuple(_relationship_from_row(row) for row in relationship_rows),
            cycles=cycles,
            metrics=tuple(_metric_from_row(row) for row in metric_rows),
            findings=tuple(_finding_evidence_from_row(row) for row in finding_rows),
        )

    def current_findings(
        self,
        repository_id: str,
        finding_ids: tuple[str, ...],
    ) -> tuple[StoredFindingRecord, ...]:
        """Load bounded current lifecycle/review state separately from occurrences."""

        if len(finding_ids) > 50:
            raise ValueError("Current finding selection exceeds 50 items.")
        if not finding_ids:
            return ()
        placeholders = ",".join("?" for _ in finding_ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                {_FINDING_SELECT}
                WHERE f.repository_id = ?
                  AND o.snapshot_id = f.last_seen_snapshot_id
                  AND o.finding_id IN ({placeholders})
                ORDER BY o.finding_id
                """,  # nosec B608 - placeholders only, with a fixed maximum.
                (repository_id, *finding_ids),
            ).fetchall()
        return tuple(_stored_finding_from_row(row) for row in rows)

    def save_handoff(self, record: SavedHandoffRecord) -> SavedHandoffRecord:
        """Persist one immutable local handoff after validating snapshot ownership."""

        _validate_saved_handoff_integrity(record)
        if len(record.task_objective) > 4_000:
            raise ValueError("Handoff objective exceeds 4,000 characters.")
        if len(record.selection_json.encode("utf-8")) > 500_000:
            raise ValueError("Handoff selection exceeds the storage budget.")
        if len(record.rendered_markdown) > 100_000:
            raise ValueError("Handoff Markdown exceeds the storage budget.")
        if len(record.rendered_json.encode("utf-8")) > 500_000:
            raise ValueError("Handoff JSON exceeds the storage budget.")
        with self._transaction() as connection:
            target = connection.execute(
                "SELECT repository_id FROM snapshots WHERE snapshot_id = ?",
                (record.target_snapshot_id,),
            ).fetchone()
            if target is None:
                raise SnapshotNotFoundError("Target snapshot was not found.")
            if str(target["repository_id"]) != record.repository_id:
                raise ValueError("Target snapshot belongs to another repository.")
            if record.baseline_snapshot_id is not None:
                baseline = connection.execute(
                    "SELECT repository_id FROM snapshots WHERE snapshot_id = ?",
                    (record.baseline_snapshot_id,),
                ).fetchone()
                if baseline is None:
                    raise SnapshotNotFoundError("Baseline snapshot was not found.")
                if str(baseline["repository_id"]) != record.repository_id:
                    raise ValueError("Baseline snapshot belongs to another repository.")
            connection.execute(
                """
                INSERT INTO saved_handoffs (
                    handoff_id, repository_id, target_snapshot_id,
                    baseline_snapshot_id, comparison_id, selection_json,
                    task_objective, format_version, rendered_digest,
                    rendered_markdown, rendered_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.handoff_id,
                    record.repository_id,
                    record.target_snapshot_id,
                    record.baseline_snapshot_id,
                    record.comparison_id,
                    record.selection_json,
                    record.task_objective,
                    record.format_version,
                    record.rendered_digest,
                    record.rendered_markdown,
                    record.rendered_json,
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def list_handoffs(
        self,
        *,
        repository_id: str | None = None,
        limit: int = 100,
    ) -> tuple[SavedHandoffRecord, ...]:
        if limit < 1 or limit > 100:
            raise ValueError("Saved handoff limit is outside the supported range.")
        clauses = ""
        parameters: tuple[object, ...] = ()
        if repository_id is not None:
            clauses = "WHERE repository_id = ?"
            parameters = (repository_id,)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM saved_handoffs
                {clauses}
                ORDER BY created_at DESC, handoff_id
                LIMIT ?
                """,  # nosec B608 - optional clause is fixed above.
                (*parameters, limit),
            ).fetchall()
        return tuple(_saved_handoff_from_row(row) for row in rows)

    def get_handoff(self, handoff_id: str) -> SavedHandoffRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM saved_handoffs WHERE handoff_id = ?",
                (handoff_id,),
            ).fetchone()
        if row is None:
            return None
        record = _saved_handoff_from_row(row)
        _validate_saved_handoff_integrity(record)
        return record

    def get_file(self, snapshot_id: str, relative_path: str) -> FileRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM files
                WHERE snapshot_id = ? AND relative_path = ?
                """,
                (snapshot_id, relative_path),
            ).fetchone()
        return _file_from_row(row) if row is not None else None

    def list_diagnostics(self, snapshot_id: str) -> tuple[DiagnosticRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM diagnostics
                WHERE snapshot_id = ?
                ORDER BY COALESCE(relative_path, ''), COALESCE(line, 0), diagnostic_id
                """,
                (snapshot_id,),
            ).fetchall()
        return tuple(_diagnostic_from_row(row) for row in rows)

    def _initialize(self) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER NOT NULL
                )
                """
            )
            row = connection.execute("SELECT version FROM schema_version").fetchone()
            if row is None:
                connection.execute("INSERT INTO schema_version (version) VALUES (0)")
                current = 0
            else:
                current = int(row[0])
            if current > DATABASE_SCHEMA_VERSION:
                raise RuntimeError("Repository-review database schema is newer than this application.")
            self._migrate(connection, current)

    @staticmethod
    def _migrate(connection: sqlite3.Connection, current: int) -> None:
        if current < 1:
            _execute_schema(connection, _SCHEMA_V1)
            connection.execute("UPDATE schema_version SET version = 1")
        if current < 2:
            _execute_schema(connection, _SCHEMA_V2)
            connection.execute("UPDATE schema_version SET version = 2")
        if current < 3:
            _execute_schema(connection, _SCHEMA_V3)
            connection.execute("UPDATE schema_version SET version = 3")
        if current < 4:
            _execute_schema(connection, _SCHEMA_V4)
            connection.execute(
                """
                UPDATE analyses AS current_analysis
                SET repository_generation = (
                    SELECT COUNT(*)
                    FROM analyses AS ordered_analysis
                    WHERE ordered_analysis.repository_id = current_analysis.repository_id
                      AND (
                          ordered_analysis.started_at < current_analysis.started_at
                          OR (
                              ordered_analysis.started_at = current_analysis.started_at
                              AND ordered_analysis.analysis_id <= current_analysis.analysis_id
                          )
                      )
                )
                """
            )
            connection.execute(
                """
                UPDATE repositories
                SET latest_analysis_generation = COALESCE(
                    (
                        SELECT MAX(repository_generation)
                        FROM analyses
                        WHERE analyses.repository_id = repositories.repository_id
                    ),
                    0
                )
                """
            )
            connection.execute(
                """
                UPDATE analyses
                SET lifecycle_reconciled = 1
                WHERE state = 'completed'
                """
            )
            connection.execute("UPDATE schema_version SET version = 4")
        if current < 5:
            _execute_schema(connection, _SCHEMA_V5)
            connection.execute("UPDATE schema_version SET version = 5")
        if current < 6:
            _execute_schema(connection, _SCHEMA_V6)
            connection.execute("UPDATE schema_version SET version = 6")

    @staticmethod
    def _upsert_repository(
        connection: sqlite3.Connection,
        repository: RepositoryRecord,
    ) -> None:
        connection.execute(
            """
            INSERT INTO repositories (
                repository_id, display_name, canonical_path, git_root, branch,
                git_sha, dirty, staged, untracked, configuration_digest,
                source_roots_json, test_roots_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(repository_id) DO UPDATE SET
                display_name = excluded.display_name,
                canonical_path = excluded.canonical_path,
                git_root = excluded.git_root,
                branch = excluded.branch,
                git_sha = excluded.git_sha,
                dirty = excluded.dirty,
                staged = excluded.staged,
                untracked = excluded.untracked,
                configuration_digest = excluded.configuration_digest,
                source_roots_json = excluded.source_roots_json,
                test_roots_json = excluded.test_roots_json
            """,
            (
                repository.repository_id,
                repository.display_name,
                repository.canonical_path,
                repository.git_root,
                repository.branch,
                repository.git_sha,
                int(repository.dirty),
                int(repository.staged),
                int(repository.untracked),
                repository.configuration_digest,
                json.dumps(repository.source_roots, separators=(",", ":")),
                json.dumps(repository.test_roots, separators=(",", ":")),
            ),
        )

    @staticmethod
    def _insert_snapshot(connection: sqlite3.Connection, evidence: AnalysisEvidence) -> None:
        snapshot = evidence.snapshot
        connection.execute(
            """
            INSERT INTO snapshots (
                snapshot_id, repository_id, analyzer_version, schema_version,
                rule_set_version, state, source_fingerprint, file_count,
                included_file_count, module_count, symbol_count, started_at,
                completed_at, duration_ms, truncated, parse_gap_count,
                observed_state_known, observed_branch, observed_git_sha, observed_dirty,
                observed_staged, observed_untracked
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.snapshot_id,
                snapshot.repository_id,
                snapshot.analyzer_version,
                snapshot.schema_version,
                snapshot.rule_set_version,
                snapshot.state.value,
                snapshot.source_fingerprint,
                snapshot.file_count,
                snapshot.included_file_count,
                snapshot.module_count,
                snapshot.symbol_count,
                snapshot.started_at,
                snapshot.completed_at,
                snapshot.duration_ms,
                int(snapshot.truncated),
                snapshot.parse_gap_count,
                1,
                evidence.repository.branch,
                evidence.repository.git_sha,
                int(evidence.repository.dirty),
                int(evidence.repository.staged),
                int(evidence.repository.untracked),
            ),
        )
        connection.executemany(
            """
            INSERT INTO files (
                snapshot_id, file_id, relative_path, content_hash, language,
                size_bytes, included, exclusion_reason, parse_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot.snapshot_id,
                    item.file_id,
                    item.relative_path,
                    item.content_hash,
                    item.language,
                    item.size_bytes,
                    int(item.included),
                    item.exclusion_reason,
                    item.parse_status,
                )
                for item in evidence.files
            ],
        )
        connection.executemany(
            """
            INSERT INTO modules (
                snapshot_id, module_id, module_name, package_name, file_id,
                relative_path, public_exports_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot.snapshot_id,
                    item.module_id,
                    item.module_name,
                    item.package,
                    item.file_id,
                    item.relative_path,
                    json.dumps(item.public_exports, separators=(",", ":")),
                )
                for item in evidence.modules
            ],
        )
        imports = [
            (
                snapshot.snapshot_id,
                module.module_id,
                item.module,
                item.imported_name,
                item.alias,
                item.level,
                item.line,
                item.column,
            )
            for module in evidence.modules
            for item in module.imports
        ]
        if imports:
            connection.executemany(
                """
                INSERT INTO module_imports (
                    snapshot_id, module_id, imported_module, imported_name, alias, level,
                    line, column_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                imports,
            )
        connection.executemany(
            """
            INSERT INTO symbols (
                snapshot_id, symbol_id, language, kind, qualified_name,
                display_name, module_name, file_id, relative_path, start_line,
                start_column, end_line, end_column, parent_symbol_id, visibility,
                signature, annotations_json, decorators_json, docstring_present,
                async_flag, content_fingerprint, bases_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot.snapshot_id,
                    item.symbol_id,
                    item.language,
                    item.kind,
                    item.qualified_name,
                    item.display_name,
                    item.module_name,
                    item.file_id,
                    item.relative_path,
                    item.start_line,
                    item.start_column,
                    item.end_line,
                    item.end_column,
                    item.parent_symbol_id,
                    item.visibility,
                    item.signature,
                    json.dumps(item.annotations, separators=(",", ":")),
                    json.dumps(item.decorators, separators=(",", ":")),
                    int(item.docstring_present),
                    int(item.async_flag),
                    item.content_fingerprint,
                    json.dumps(item.bases, separators=(",", ":")),
                )
                for item in evidence.symbols
            ],
        )
        connection.executemany(
            """
            INSERT INTO diagnostics (
                snapshot_id, diagnostic_id, code, severity, message,
                relative_path, line, column_number, category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot.snapshot_id,
                    item.diagnostic_id,
                    item.code,
                    item.severity,
                    item.message,
                    item.relative_path,
                    item.line,
                    item.column,
                    item.category,
                )
                for item in evidence.diagnostics
            ],
        )
        connection.executemany(
            """
            INSERT INTO metrics (
                snapshot_id, metric_id, subject_id, subject_type, metric_name,
                numeric_value, unit, analyzer_version, relative_path, line
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot.snapshot_id,
                    item.metric_id,
                    item.subject_id,
                    item.subject_type,
                    item.metric_name,
                    item.numeric_value,
                    item.unit,
                    item.analyzer_version,
                    item.relative_path,
                    item.line,
                )
                for item in evidence.metrics
            ],
        )
        connection.executemany(
            """
            INSERT INTO finding_occurrences (
                snapshot_id, finding_id, rule_id, rule_version, family, title,
                explanation, suggested_action, severity, confidence, subject_type,
                subject_keys_json, affected_node_ids_json, relative_path, line,
                metric_evidence_json, threshold_evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot.snapshot_id,
                    item.finding_id,
                    item.rule_id,
                    item.rule_version,
                    item.family,
                    item.title,
                    item.explanation,
                    item.suggested_action,
                    item.severity,
                    item.confidence,
                    item.subject_type,
                    json.dumps(item.subject_keys, separators=(",", ":")),
                    json.dumps(item.affected_node_ids, separators=(",", ":")),
                    item.relative_path,
                    item.line,
                    json.dumps(item.metric_evidence, separators=(",", ":")),
                    json.dumps(item.threshold_evidence, separators=(",", ":")),
                )
                for item in evidence.findings
            ],
        )
        connection.executemany(
            """
            INSERT INTO graph_nodes (
                snapshot_id, node_id, node_type, display_name, qualified_name,
                relative_path, symbol_kind
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot.snapshot_id,
                    item.node_id,
                    item.node_type,
                    item.display_name,
                    item.qualified_name,
                    item.relative_path,
                    item.symbol_kind,
                )
                for item in evidence.graph_nodes
            ],
        )
        connection.executemany(
            """
            INSERT INTO relationships (
                snapshot_id, relationship_id, relationship_type, source_id,
                target_id, unresolved_target, resolution_status, confidence,
                relative_path, line, column_number, analyzer_version, evidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    snapshot.snapshot_id,
                    item.relationship_id,
                    item.relationship_type,
                    item.source_id,
                    item.target_id,
                    item.unresolved_target,
                    item.resolution_status,
                    item.confidence,
                    item.relative_path,
                    item.line,
                    item.column,
                    item.analyzer_version,
                    item.evidence,
                )
                for item in evidence.relationships
            ],
        )
        connection.executemany(
            """
            INSERT INTO cycle_groups (
                snapshot_id, cycle_id, relationship_type
            ) VALUES (?, ?, ?)
            """,
            [(snapshot.snapshot_id, item.cycle_id, item.relationship_type) for item in evidence.cycles],
        )
        connection.executemany(
            """
            INSERT INTO cycle_members (snapshot_id, cycle_id, node_id)
            VALUES (?, ?, ?)
            """,
            [
                (snapshot.snapshot_id, cycle.cycle_id, node_id)
                for cycle in evidence.cycles
                for node_id in cycle.member_node_ids
            ],
        )
        connection.executemany(
            """
            INSERT INTO cycle_edges (snapshot_id, cycle_id, relationship_id)
            VALUES (?, ?, ?)
            """,
            [
                (snapshot.snapshot_id, cycle.cycle_id, relationship_id)
                for cycle in evidence.cycles
                for relationship_id in cycle.edge_ids
            ],
        )

    @staticmethod
    def _reconcile_findings(
        connection: sqlite3.Connection,
        evidence: AnalysisEvidence,
        *,
        resolve_missing: bool,
    ) -> None:
        snapshot = evidence.snapshot
        observed = {item.finding_id for item in evidence.findings}
        for item in evidence.findings:
            existing = connection.execute(
                """
                SELECT evidence_state, last_seen_snapshot_id
                FROM findings WHERE finding_id = ?
                """,
                (item.finding_id,),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO findings (
                        finding_id, repository_id, first_seen_snapshot_id,
                        last_seen_snapshot_id, evidence_state, resolved_snapshot_id
                    ) VALUES (?, ?, ?, ?, 'active', NULL)
                    """,
                    (
                        item.finding_id,
                        snapshot.repository_id,
                        snapshot.snapshot_id,
                        snapshot.snapshot_id,
                    ),
                )
                event_type = "finding-first-seen"
                connection.execute(
                    """
                    INSERT INTO finding_reviews (
                        finding_id, review_status, note, reason_code, version,
                        decided_at, updated_at
                    ) VALUES (?, 'new', '', NULL, 0, ?, ?)
                    """,
                    (item.finding_id, snapshot.completed_at, snapshot.completed_at),
                )
            else:
                if (
                    str(existing["evidence_state"]) == "active"
                    and str(existing["last_seen_snapshot_id"]) == snapshot.snapshot_id
                ):
                    continue
                event_type = (
                    "finding-reactivated"
                    if str(existing["evidence_state"]) == "resolved"
                    else "finding-evidence-updated"
                )
                connection.execute(
                    """
                    UPDATE findings
                    SET last_seen_snapshot_id = ?, evidence_state = 'active',
                        resolved_snapshot_id = NULL
                    WHERE finding_id = ? AND repository_id = ?
                    """,
                    (snapshot.snapshot_id, item.finding_id, snapshot.repository_id),
                )
            connection.execute(
                """
                INSERT INTO finding_review_events (
                    finding_id, event_type, snapshot_id, review_status,
                    reason_code, note, review_version, event_at
                ) VALUES (?, ?, ?, NULL, NULL, '', NULL, ?)
                """,
                (item.finding_id, event_type, snapshot.snapshot_id, snapshot.completed_at),
            )

        if not resolve_missing:
            return

        active_rows = connection.execute(
            """
            SELECT finding_id FROM findings
            WHERE repository_id = ? AND evidence_state = 'active'
            ORDER BY finding_id
            """,
            (snapshot.repository_id,),
        ).fetchall()
        for row in active_rows:
            finding_id = str(row["finding_id"])
            if finding_id in observed:
                continue
            connection.execute(
                """
                UPDATE findings
                SET evidence_state = 'resolved', resolved_snapshot_id = ?
                WHERE finding_id = ?
                """,
                (snapshot.snapshot_id, finding_id),
            )
            connection.execute(
                """
                INSERT INTO finding_review_events (
                    finding_id, event_type, snapshot_id, review_status,
                    reason_code, note, review_version, event_at
                ) VALUES (?, 'finding-resolved', ?, NULL, NULL, '', NULL, ?)
                """,
                (finding_id, snapshot.snapshot_id, snapshot.completed_at),
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()


def resolve_app_data_directory(override: Path | None = None) -> Path:
    """Return the platform-appropriate storage root, honoring test overrides."""

    if override is not None:
        return override.expanduser().resolve()
    environment_override = os.environ.get("ZCRIPTS_DATA_DIR")
    if environment_override:
        return Path(environment_override).expanduser().resolve()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "Zscripts"
        return Path.home() / "AppData" / "Local" / "Zscripts"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Zscripts"
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "zscripts"
    return Path.home() / ".local" / "share" / "zscripts"


def _repository_from_row(row: sqlite3.Row) -> RepositoryRecord:
    return RepositoryRecord(
        repository_id=str(row["repository_id"]),
        display_name=str(row["display_name"]),
        canonical_path=str(row["canonical_path"]),
        git_root=str(row["git_root"]) if row["git_root"] is not None else None,
        branch=str(row["branch"]) if row["branch"] is not None else None,
        git_sha=str(row["git_sha"]) if row["git_sha"] is not None else None,
        dirty=bool(row["dirty"]),
        staged=bool(row["staged"]),
        untracked=bool(row["untracked"]),
        configuration_digest=str(row["configuration_digest"]),
        source_roots=tuple(json.loads(str(row["source_roots_json"]))),
        test_roots=tuple(json.loads(str(row["test_roots_json"]))),
    )


def _snapshot_from_row(row: sqlite3.Row) -> SnapshotRecord:
    return SnapshotRecord(
        snapshot_id=str(row["snapshot_id"]),
        repository_id=str(row["repository_id"]),
        analyzer_version=str(row["analyzer_version"]),
        schema_version=str(row["schema_version"]),
        rule_set_version=str(row["rule_set_version"]),
        state=AnalysisState(str(row["state"])),
        source_fingerprint=str(row["source_fingerprint"]),
        file_count=int(row["file_count"]),
        included_file_count=int(row["included_file_count"]),
        module_count=int(row["module_count"]),
        symbol_count=int(row["symbol_count"]),
        started_at=str(row["started_at"]),
        completed_at=str(row["completed_at"]) if row["completed_at"] is not None else None,
        duration_ms=int(row["duration_ms"]),
        truncated=bool(row["truncated"]),
        parse_gap_count=int(row["parse_gap_count"]),
    )


def _analysis_from_row(row: sqlite3.Row) -> AnalysisStatusRecord:
    return AnalysisStatusRecord(
        analysis_id=str(row["analysis_id"]),
        repository_id=str(row["repository_id"]),
        state=AnalysisState(str(row["state"])),
        progress_completed=int(row["progress_completed"]),
        progress_total=int(row["progress_total"]),
        progress_phase=str(row["progress_phase"]),
        message=str(row["message"]) if row["message"] is not None else None,
        started_at=str(row["started_at"]),
        completed_at=str(row["completed_at"]) if row["completed_at"] is not None else None,
        snapshot_id=str(row["snapshot_id"]) if row["snapshot_id"] is not None else None,
        repository_generation=int(row["repository_generation"]),
        lifecycle_reconciled=bool(row["lifecycle_reconciled"]),
        reconciliation_skip_reason=(
            str(row["reconciliation_skip_reason"]) if row["reconciliation_skip_reason"] is not None else None
        ),
    )


def _file_from_row(row: sqlite3.Row) -> FileRecord:
    return FileRecord(
        file_id=str(row["file_id"]),
        relative_path=str(row["relative_path"]),
        content_hash=str(row["content_hash"]) if row["content_hash"] is not None else None,
        language=str(row["language"]),
        size_bytes=int(row["size_bytes"]),
        included=bool(row["included"]),
        exclusion_reason=(str(row["exclusion_reason"]) if row["exclusion_reason"] is not None else None),
        parse_status=str(row["parse_status"]),
    )


def _symbol_from_row(row: sqlite3.Row) -> SymbolRecord:
    return SymbolRecord(
        symbol_id=str(row["symbol_id"]),
        language=str(row["language"]),
        kind=str(row["kind"]),
        qualified_name=str(row["qualified_name"]),
        display_name=str(row["display_name"]),
        module_name=str(row["module_name"]),
        file_id=str(row["file_id"]),
        relative_path=str(row["relative_path"]),
        start_line=int(row["start_line"]),
        start_column=int(row["start_column"]),
        end_line=int(row["end_line"]),
        end_column=int(row["end_column"]),
        parent_symbol_id=(str(row["parent_symbol_id"]) if row["parent_symbol_id"] is not None else None),
        visibility=str(row["visibility"]),
        signature=str(row["signature"]),
        annotations=tuple(json.loads(str(row["annotations_json"]))),
        decorators=tuple(json.loads(str(row["decorators_json"]))),
        docstring_present=bool(row["docstring_present"]),
        async_flag=bool(row["async_flag"]),
        content_fingerprint=str(row["content_fingerprint"]),
        bases=tuple(json.loads(str(row["bases_json"]))),
    )


def _diagnostic_from_row(row: sqlite3.Row) -> DiagnosticRecord:
    return DiagnosticRecord(
        diagnostic_id=str(row["diagnostic_id"]),
        code=str(row["code"]),
        severity=str(row["severity"]),
        message=str(row["message"]),
        relative_path=(str(row["relative_path"]) if row["relative_path"] is not None else None),
        line=int(row["line"]) if row["line"] is not None else None,
        column=int(row["column_number"]) if row["column_number"] is not None else None,
        category=str(row["category"]),
    )


def _graph_node_from_row(row: sqlite3.Row) -> GraphNodeRecord:
    return GraphNodeRecord(
        node_id=str(row["node_id"]),
        node_type=str(row["node_type"]),
        display_name=str(row["display_name"]),
        qualified_name=str(row["qualified_name"]),
        relative_path=str(row["relative_path"]) if row["relative_path"] is not None else None,
        symbol_kind=str(row["symbol_kind"]) if row["symbol_kind"] is not None else None,
    )


def _relationship_from_row(row: sqlite3.Row) -> RelationshipRecord:
    return RelationshipRecord(
        relationship_id=str(row["relationship_id"]),
        relationship_type=str(row["relationship_type"]),
        source_id=str(row["source_id"]),
        target_id=str(row["target_id"]) if row["target_id"] is not None else None,
        unresolved_target=(str(row["unresolved_target"]) if row["unresolved_target"] is not None else None),
        resolution_status=str(row["resolution_status"]),
        confidence=str(row["confidence"]),
        relative_path=str(row["relative_path"]),
        line=int(row["line"]),
        column=int(row["column_number"]),
        analyzer_version=str(row["analyzer_version"]),
        evidence=str(row["evidence"]),
    )


def _metric_from_row(row: sqlite3.Row) -> MetricRecord:
    return MetricRecord(
        metric_id=str(row["metric_id"]),
        subject_id=str(row["subject_id"]),
        subject_type=str(row["subject_type"]),
        metric_name=str(row["metric_name"]),
        numeric_value=float(row["numeric_value"]),
        unit=str(row["unit"]),
        analyzer_version=str(row["analyzer_version"]),
        relative_path=str(row["relative_path"]) if row["relative_path"] is not None else None,
        line=int(row["line"]) if row["line"] is not None else None,
    )


def _finding_evidence_from_row(row: sqlite3.Row) -> FindingEvidenceRecord:
    return FindingEvidenceRecord(
        finding_id=str(row["finding_id"]),
        rule_id=str(row["rule_id"]),
        rule_version=str(row["rule_version"]),
        family=str(row["family"]),
        title=str(row["title"]),
        explanation=str(row["explanation"]),
        suggested_action=str(row["suggested_action"]),
        severity=str(row["severity"]),
        confidence=str(row["confidence"]),
        subject_type=str(row["subject_type"]),
        subject_keys=tuple(str(item) for item in json.loads(str(row["subject_keys_json"]))),
        affected_node_ids=tuple(str(item) for item in json.loads(str(row["affected_node_ids_json"]))),
        relative_path=str(row["relative_path"]) if row["relative_path"] is not None else None,
        line=int(row["line"]) if row["line"] is not None else None,
        metric_evidence=tuple(
            (str(name), float(value)) for name, value in json.loads(str(row["metric_evidence_json"]))
        ),
        threshold_evidence=tuple(
            (str(name), float(value)) for name, value in json.loads(str(row["threshold_evidence_json"]))
        ),
    )


def _stored_finding_from_row(row: sqlite3.Row) -> StoredFindingRecord:
    evidence = FindingEvidenceRecord(
        finding_id=str(row["o_finding_id"]),
        rule_id=str(row["o_rule_id"]),
        rule_version=str(row["o_rule_version"]),
        family=str(row["o_family"]),
        title=str(row["o_title"]),
        explanation=str(row["o_explanation"]),
        suggested_action=str(row["o_suggested_action"]),
        severity=str(row["o_severity"]),
        confidence=str(row["o_confidence"]),
        subject_type=str(row["o_subject_type"]),
        subject_keys=tuple(str(item) for item in json.loads(str(row["o_subject_keys_json"]))),
        affected_node_ids=tuple(str(item) for item in json.loads(str(row["o_affected_node_ids_json"]))),
        relative_path=(str(row["o_relative_path"]) if row["o_relative_path"] is not None else None),
        line=int(row["o_line"]) if row["o_line"] is not None else None,
        metric_evidence=tuple(
            (str(name), float(value)) for name, value in json.loads(str(row["o_metric_evidence_json"]))
        ),
        threshold_evidence=tuple(
            (str(name), float(value)) for name, value in json.loads(str(row["o_threshold_evidence_json"]))
        ),
    )
    lifecycle = FindingLifecycleRecord(
        finding_id=evidence.finding_id,
        repository_id=str(row["f_repository_id"]),
        first_seen_snapshot_id=str(row["f_first_seen_snapshot_id"]),
        last_seen_snapshot_id=str(row["f_last_seen_snapshot_id"]),
        evidence_state=str(row["f_evidence_state"]),
        resolved_snapshot_id=(
            str(row["f_resolved_snapshot_id"]) if row["f_resolved_snapshot_id"] is not None else None
        ),
    )
    review = ReviewDecisionRecord(
        finding_id=evidence.finding_id,
        review_status=str(row["r_review_status"]),
        note=str(row["r_note"]),
        reason_code=str(row["r_reason_code"]) if row["r_reason_code"] is not None else None,
        version=int(row["r_version"]),
        decided_at=str(row["r_decided_at"]),
        updated_at=str(row["r_updated_at"]),
    )
    return StoredFindingRecord(evidence=evidence, lifecycle=lifecycle, review=review)


def _saved_handoff_from_row(row: sqlite3.Row) -> SavedHandoffRecord:
    return SavedHandoffRecord(
        handoff_id=str(row["handoff_id"]),
        repository_id=str(row["repository_id"]),
        target_snapshot_id=str(row["target_snapshot_id"]),
        baseline_snapshot_id=(
            str(row["baseline_snapshot_id"]) if row["baseline_snapshot_id"] is not None else None
        ),
        comparison_id=str(row["comparison_id"]) if row["comparison_id"] is not None else None,
        selection_json=str(row["selection_json"]),
        task_objective=str(row["task_objective"]),
        format_version=str(row["format_version"]),
        rendered_digest=str(row["rendered_digest"]),
        rendered_markdown=str(row["rendered_markdown"]),
        rendered_json=str(row["rendered_json"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        local_only=True,
    )


def _validate_saved_handoff_integrity(record: SavedHandoffRecord) -> None:
    if record.format_version != HANDOFF_FORMAT_VERSION:
        raise SavedHandoffIntegrityError("Saved handoff format is unsupported.")
    try:
        selection_payload = json.loads(record.selection_json)
        maximum_json_bytes = selection_payload["budget_policy"]["maximum_json_bytes"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise SavedHandoffIntegrityError("Saved handoff selection is invalid.") from exc
    if (
        isinstance(maximum_json_bytes, bool)
        or not isinstance(maximum_json_bytes, int)
        or maximum_json_bytes < 1
        or maximum_json_bytes > 500_000
    ):
        raise SavedHandoffIntegrityError("Saved handoff selection is invalid.")
    if len(record.rendered_json.encode("utf-8")) > maximum_json_bytes:
        raise SavedHandoffIntegrityError("Saved handoff JSON exceeds its rendered budget.")
    expected = rendered_output_digest(
        record.format_version,
        record.rendered_markdown,
        record.rendered_json,
    )
    if record.rendered_digest != expected:
        raise SavedHandoffIntegrityError("Saved handoff rendered output failed integrity validation.")


def _get_finding_in_connection(
    connection: sqlite3.Connection,
    finding_id: str,
    snapshot_id: str | None,
) -> StoredFindingRecord | None:
    if snapshot_id is None:
        row = connection.execute(
            f"""
            {_FINDING_SELECT}
            WHERE o.finding_id = ? AND o.snapshot_id = f.last_seen_snapshot_id
            """,  # nosec B608
            (finding_id,),
        ).fetchone()
    else:
        row = connection.execute(
            f"""
            {_FINDING_SELECT}
            WHERE o.finding_id = ?
              AND o.snapshot_id = f.last_seen_snapshot_id
              AND f.repository_id = (
                  SELECT repository_id
                  FROM snapshots
                  WHERE snapshot_id = ?
              )
            """,  # nosec B608
            (finding_id, snapshot_id),
        ).fetchone()
    return _stored_finding_from_row(row) if row is not None else None


def _review_event_from_row(row: sqlite3.Row) -> ReviewEventRecord:
    return ReviewEventRecord(
        event_id=int(row["event_id"]),
        finding_id=str(row["finding_id"]),
        event_type=str(row["event_type"]),
        snapshot_id=str(row["snapshot_id"]) if row["snapshot_id"] is not None else None,
        review_status=(str(row["review_status"]) if row["review_status"] is not None else None),
        reason_code=str(row["reason_code"]) if row["reason_code"] is not None else None,
        note=str(row["note"]),
        review_version=(int(row["review_version"]) if row["review_version"] is not None else None),
        event_at=str(row["event_at"]),
    )


def _version_at_least(value: str, minimum: int) -> bool:
    try:
        return int(value) >= minimum
    except ValueError:
        return False


def _execute_schema(connection: sqlite3.Connection, schema: str) -> None:
    """Execute simple DDL statements without ``executescript``'s implicit commit."""

    for statement in schema.split(";"):
        if normalized := statement.strip():
            connection.execute(normalized)


_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS analysis_sequence (
    id INTEGER PRIMARY KEY AUTOINCREMENT
);

CREATE TABLE IF NOT EXISTS repositories (
    repository_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    canonical_path TEXT NOT NULL,
    git_root TEXT,
    branch TEXT,
    git_sha TEXT,
    dirty INTEGER NOT NULL CHECK (dirty IN (0, 1)),
    staged INTEGER NOT NULL CHECK (staged IN (0, 1)),
    untracked INTEGER NOT NULL CHECK (untracked IN (0, 1)),
    configuration_digest TEXT NOT NULL,
    source_roots_json TEXT NOT NULL,
    test_roots_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    analysis_id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL REFERENCES repositories(repository_id),
    state TEXT NOT NULL CHECK (state IN ('started', 'completed', 'cancelled', 'failed')),
    progress_completed INTEGER NOT NULL,
    progress_total INTEGER NOT NULL,
    progress_phase TEXT NOT NULL,
    message TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    snapshot_id TEXT
    ,FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id)
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL REFERENCES repositories(repository_id),
    analyzer_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    rule_set_version TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state = 'completed'),
    source_fingerprint TEXT NOT NULL,
    file_count INTEGER NOT NULL,
    included_file_count INTEGER NOT NULL,
    module_count INTEGER NOT NULL,
    symbol_count INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    truncated INTEGER NOT NULL CHECK (truncated IN (0, 1)),
    parse_gap_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
    file_id TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    content_hash TEXT,
    language TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    included INTEGER NOT NULL CHECK (included IN (0, 1)),
    exclusion_reason TEXT,
    parse_status TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, file_id),
    UNIQUE (snapshot_id, relative_path)
);

CREATE TABLE IF NOT EXISTS modules (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
    module_id TEXT NOT NULL,
    module_name TEXT NOT NULL,
    package_name TEXT NOT NULL,
    file_id TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    public_exports_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, module_id),
    FOREIGN KEY (snapshot_id, file_id) REFERENCES files(snapshot_id, file_id)
);

CREATE TABLE IF NOT EXISTS module_imports (
    snapshot_id TEXT NOT NULL,
    module_id TEXT NOT NULL,
    imported_module TEXT,
    imported_name TEXT,
    alias TEXT,
    level INTEGER NOT NULL,
    FOREIGN KEY (snapshot_id, module_id)
        REFERENCES modules(snapshot_id, module_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS symbols (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
    symbol_id TEXT NOT NULL,
    language TEXT NOT NULL,
    kind TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    module_name TEXT NOT NULL,
    file_id TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    start_column INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    end_column INTEGER NOT NULL,
    parent_symbol_id TEXT,
    visibility TEXT NOT NULL,
    signature TEXT NOT NULL,
    annotations_json TEXT NOT NULL,
    decorators_json TEXT NOT NULL,
    docstring_present INTEGER NOT NULL CHECK (docstring_present IN (0, 1)),
    async_flag INTEGER NOT NULL CHECK (async_flag IN (0, 1)),
    content_fingerprint TEXT NOT NULL,
    bases_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, symbol_id),
    FOREIGN KEY (snapshot_id, file_id) REFERENCES files(snapshot_id, file_id)
);

CREATE TABLE IF NOT EXISTS diagnostics (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
    diagnostic_id TEXT NOT NULL,
    code TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    relative_path TEXT,
    line INTEGER,
    column_number INTEGER,
    category TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, diagnostic_id)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_repository
    ON snapshots(repository_id, completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_symbols_snapshot_qualified
    ON symbols(snapshot_id, qualified_name);
CREATE INDEX IF NOT EXISTS idx_symbols_snapshot_filters
    ON symbols(snapshot_id, kind, module_name, visibility);
CREATE INDEX IF NOT EXISTS idx_files_snapshot_path
    ON files(snapshot_id, relative_path);
"""


_SCHEMA_V2 = """
ALTER TABLE module_imports ADD COLUMN line INTEGER NOT NULL DEFAULT 1;
ALTER TABLE module_imports ADD COLUMN column_number INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS graph_nodes (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,
    node_type TEXT NOT NULL CHECK (node_type IN ('package', 'module', 'symbol')),
    display_name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    relative_path TEXT,
    symbol_kind TEXT,
    PRIMARY KEY (snapshot_id, node_id)
);

CREATE TABLE IF NOT EXISTS relationships (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
    relationship_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL
        CHECK (relationship_type IN ('contains', 'imports', 'inherits', 'references-type')),
    source_id TEXT NOT NULL,
    target_id TEXT,
    unresolved_target TEXT,
    resolution_status TEXT NOT NULL
        CHECK (
            resolution_status IN (
                'resolved-static', 'probable-static', 'ambiguous', 'unresolved-dynamic'
            )
        ),
    confidence TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    relative_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    column_number INTEGER NOT NULL,
    analyzer_version TEXT NOT NULL,
    evidence TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, relationship_id),
    FOREIGN KEY (snapshot_id, source_id)
        REFERENCES graph_nodes(snapshot_id, node_id) ON DELETE CASCADE,
    FOREIGN KEY (snapshot_id, target_id)
        REFERENCES graph_nodes(snapshot_id, node_id) ON DELETE CASCADE,
    CHECK (
        (target_id IS NOT NULL AND unresolved_target IS NULL
            AND resolution_status IN ('resolved-static', 'probable-static'))
        OR
        (target_id IS NULL AND unresolved_target IS NOT NULL
            AND resolution_status IN ('ambiguous', 'unresolved-dynamic'))
    )
);

CREATE TABLE IF NOT EXISTS cycle_groups (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
    cycle_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL CHECK (relationship_type IN ('imports', 'inherits')),
    PRIMARY KEY (snapshot_id, cycle_id)
);

CREATE TABLE IF NOT EXISTS cycle_members (
    snapshot_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, cycle_id, node_id),
    FOREIGN KEY (snapshot_id, cycle_id)
        REFERENCES cycle_groups(snapshot_id, cycle_id) ON DELETE CASCADE,
    FOREIGN KEY (snapshot_id, node_id)
        REFERENCES graph_nodes(snapshot_id, node_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cycle_edges (
    snapshot_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    relationship_id TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, cycle_id, relationship_id),
    FOREIGN KEY (snapshot_id, cycle_id)
        REFERENCES cycle_groups(snapshot_id, cycle_id) ON DELETE CASCADE,
    FOREIGN KEY (snapshot_id, relationship_id)
        REFERENCES relationships(snapshot_id, relationship_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_graph_nodes_snapshot_name
    ON graph_nodes(snapshot_id, qualified_name);
CREATE INDEX IF NOT EXISTS idx_relationships_snapshot_type
    ON relationships(snapshot_id, relationship_type, resolution_status);
CREATE INDEX IF NOT EXISTS idx_relationships_snapshot_source
    ON relationships(snapshot_id, source_id);
CREATE INDEX IF NOT EXISTS idx_relationships_snapshot_target
    ON relationships(snapshot_id, target_id);
"""

_SCHEMA_V3 = """
CREATE TABLE IF NOT EXISTS metrics (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
    metric_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    subject_type TEXT NOT NULL CHECK (subject_type IN ('module', 'symbol')),
    metric_name TEXT NOT NULL,
    numeric_value REAL NOT NULL,
    unit TEXT NOT NULL,
    analyzer_version TEXT NOT NULL,
    relative_path TEXT,
    line INTEGER,
    PRIMARY KEY (snapshot_id, metric_id)
);

CREATE TABLE IF NOT EXISTS finding_occurrences (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
    finding_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    family TEXT NOT NULL,
    title TEXT NOT NULL,
    explanation TEXT NOT NULL,
    suggested_action TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('high', 'medium', 'low')),
    confidence TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    subject_type TEXT NOT NULL,
    subject_keys_json TEXT NOT NULL,
    affected_node_ids_json TEXT NOT NULL,
    relative_path TEXT,
    line INTEGER,
    metric_evidence_json TEXT NOT NULL,
    threshold_evidence_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, finding_id)
);

CREATE TABLE IF NOT EXISTS findings (
    finding_id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL REFERENCES repositories(repository_id),
    first_seen_snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
    last_seen_snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
    evidence_state TEXT NOT NULL CHECK (evidence_state IN ('active', 'resolved')),
    resolved_snapshot_id TEXT REFERENCES snapshots(snapshot_id)
);

CREATE TABLE IF NOT EXISTS finding_reviews (
    finding_id TEXT PRIMARY KEY REFERENCES findings(finding_id) ON DELETE CASCADE,
    review_status TEXT NOT NULL
        CHECK (review_status IN ('new', 'reviewed', 'needs-action', 'accepted', 'dismissed')),
    note TEXT NOT NULL CHECK (length(note) <= 2000),
    reason_code TEXT
        CHECK (
            reason_code IS NULL OR reason_code IN (
                'intentional-design', 'false-positive', 'accepted-risk',
                'planned-refactor', 'needs-investigation', 'other'
            )
        ),
    version INTEGER NOT NULL CHECK (version >= 0),
    decided_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS finding_review_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id TEXT NOT NULL REFERENCES findings(finding_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL
        CHECK (
            event_type IN (
                'finding-first-seen', 'finding-evidence-updated',
                'review-decision-changed', 'finding-resolved', 'finding-reactivated'
            )
        ),
    snapshot_id TEXT REFERENCES snapshots(snapshot_id),
    review_status TEXT,
    reason_code TEXT,
    note TEXT NOT NULL CHECK (length(note) <= 2000),
    review_version INTEGER,
    event_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metrics_snapshot_subject
    ON metrics(snapshot_id, subject_id, metric_name);
CREATE INDEX IF NOT EXISTS idx_occurrences_snapshot_filters
    ON finding_occurrences(snapshot_id, family, severity, confidence);
CREATE INDEX IF NOT EXISTS idx_findings_repository_state
    ON findings(repository_id, evidence_state, last_seen_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_review_events_finding
    ON finding_review_events(finding_id, event_id DESC);
"""

_SCHEMA_V4 = """
ALTER TABLE repositories
    ADD COLUMN latest_analysis_generation INTEGER NOT NULL DEFAULT 0;
ALTER TABLE analyses
    ADD COLUMN repository_generation INTEGER NOT NULL DEFAULT 0;
ALTER TABLE analyses
    ADD COLUMN lifecycle_reconciled INTEGER NOT NULL DEFAULT 0
        CHECK (lifecycle_reconciled IN (0, 1));
ALTER TABLE analyses
    ADD COLUMN reconciliation_skip_reason TEXT;
CREATE INDEX IF NOT EXISTS idx_analyses_repository_generation
    ON analyses(repository_id, repository_generation DESC);
"""

_SCHEMA_V5 = """
ALTER TABLE snapshots ADD COLUMN observed_branch TEXT;
ALTER TABLE snapshots ADD COLUMN observed_git_sha TEXT;
ALTER TABLE snapshots
    ADD COLUMN observed_dirty INTEGER NOT NULL DEFAULT 0 CHECK (observed_dirty IN (0, 1));
ALTER TABLE snapshots
    ADD COLUMN observed_staged INTEGER NOT NULL DEFAULT 0 CHECK (observed_staged IN (0, 1));
ALTER TABLE snapshots
    ADD COLUMN observed_untracked INTEGER NOT NULL DEFAULT 0 CHECK (observed_untracked IN (0, 1));
CREATE TABLE IF NOT EXISTS saved_handoffs (
    handoff_id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL REFERENCES repositories(repository_id),
    target_snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
    baseline_snapshot_id TEXT REFERENCES snapshots(snapshot_id),
    comparison_id TEXT,
    selection_json TEXT NOT NULL CHECK (length(selection_json) <= 500000),
    task_objective TEXT NOT NULL CHECK (length(task_objective) <= 4000),
    format_version TEXT NOT NULL,
    rendered_digest TEXT NOT NULL,
    rendered_markdown TEXT NOT NULL CHECK (length(rendered_markdown) <= 100000),
    rendered_json TEXT NOT NULL CHECK (length(rendered_json) <= 500000),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_saved_handoffs_repository_created
    ON saved_handoffs(repository_id, created_at DESC, handoff_id);
"""

_SCHEMA_V6 = """
ALTER TABLE snapshots
    ADD COLUMN observed_state_known INTEGER NOT NULL DEFAULT 0
        CHECK (observed_state_known IN (0, 1));
"""


__all__ = [
    "AnalysisStatusRecord",
    "ComparisonSnapshotEvidence",
    "DATABASE_SCHEMA_VERSION",
    "FINDING_FAMILIES",
    "FINDING_QUEUE_PRESETS",
    "FINDING_QUEUE_PRESET_VERSION",
    "FindingPage",
    "GraphNodePage",
    "ReviewConflictError",
    "SnapshotEvidenceFacts",
    "SavedHandoffIntegrityError",
    "RelationshipPage",
    "SnapshotNotFoundError",
    "SnapshotStore",
    "StoredFindingRecord",
    "SymbolPage",
    "resolve_app_data_directory",
]
