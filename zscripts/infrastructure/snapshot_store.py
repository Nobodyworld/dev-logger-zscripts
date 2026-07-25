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

from zscripts.domain.repository_review import (
    AnalysisEvidence,
    AnalysisState,
    DiagnosticRecord,
    FileRecord,
    RepositoryRecord,
    SnapshotRecord,
    SymbolRecord,
)

DATABASE_SCHEMA_VERSION = 1
SYMBOL_SORT_COLUMNS: dict[str, str] = {
    "qualified_name": "qualified_name",
    "kind": "kind",
    "signature": "signature",
    "module": "module_name",
    "file": "relative_path",
    "line": "start_line",
    "visibility": "visibility",
}


@dataclass(frozen=True, slots=True)
class SymbolPage:
    """A bounded page of symbols returned by an allowlisted query."""

    items: tuple[SymbolRecord, ...]
    total: int
    page: int
    page_size: int


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


class SnapshotNotFoundError(LookupError):
    """Raised when a completed snapshot cannot be found."""


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
                INSERT INTO analyses (
                    analysis_id, repository_id, state, progress_completed,
                    progress_total, progress_phase, message, started_at,
                    completed_at, snapshot_id
                ) VALUES (?, ?, ?, 0, 0, 'discovery', NULL, ?, NULL, NULL)
                """,
                (analysis_id, repository.repository_id, AnalysisState.STARTED.value, started_at),
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
            existing = connection.execute(
                "SELECT 1 FROM snapshots WHERE snapshot_id = ?",
                (evidence.snapshot.snapshot_id,),
            ).fetchone()
            if existing is None:
                self._insert_snapshot(connection, evidence)
            updated = connection.execute(
                """
                UPDATE analyses
                SET state = ?, progress_completed = ?, progress_total = ?,
                    progress_phase = 'completed', message = NULL,
                    completed_at = ?, snapshot_id = ?
                WHERE analysis_id = ?
                """,
                (
                    AnalysisState.COMPLETED.value,
                    evidence.snapshot.included_file_count,
                    evidence.snapshot.included_file_count,
                    evidence.snapshot.completed_at,
                    evidence.snapshot.snapshot_id,
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
            connection.executescript(_SCHEMA_V1)
            connection.execute("UPDATE schema_version SET version = 1")

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
                completed_at, duration_ms, truncated, parse_gap_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            )
            for module in evidence.modules
            for item in module.imports
        ]
        if imports:
            connection.executemany(
                """
                INSERT INTO module_imports (
                    snapshot_id, module_id, imported_module, imported_name, alias, level
                ) VALUES (?, ?, ?, ?, ?, ?)
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


__all__ = [
    "AnalysisStatusRecord",
    "DATABASE_SCHEMA_VERSION",
    "SnapshotNotFoundError",
    "SnapshotStore",
    "SymbolPage",
    "resolve_app_data_directory",
]
