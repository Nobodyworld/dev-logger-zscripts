"""Application services shared by repository-review CLI and API surfaces."""

from __future__ import annotations

import hashlib
import io
import threading
import time
import tokenize
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from zscripts.domain.repository_review import (
    ANALYZER_VERSION,
    RULE_SET_VERSION,
    SCHEMA_VERSION,
    AnalysisEvidence,
    AnalysisState,
    CycleGroupRecord,
    GraphNodeRecord,
    RelationshipRecord,
    RepositoryRecord,
    ScanLimits,
    SnapshotRecord,
    SymbolRecord,
    stable_digest,
)
from zscripts.infrastructure.python_analyzer import PythonAnalyzer
from zscripts.infrastructure.relationship_analysis import (
    RelationshipAnalyzer,
    bounded_neighborhood,
    graph_metrics,
)
from zscripts.infrastructure.repository_discovery import (
    AnalysisCancelled,
    RepositoryDiscovery,
)
from zscripts.infrastructure.snapshot_store import (
    AnalysisStatusRecord,
    SnapshotStore,
    SymbolPage,
)

ProgressCallback = Callable[["AnalysisProgress"], None]


class SourceEvidenceError(ValueError):
    """Raised when a source-evidence request cannot be served safely."""


@dataclass(frozen=True, slots=True)
class AnalysisProgress:
    """Bounded progress update for CLI and API consumers."""

    phase: str
    completed: int
    total: int
    current_file: str


@dataclass(frozen=True, slots=True)
class SourceEvidence:
    """An on-demand bounded excerpt that is never persisted by default."""

    relative_path: str
    start_line: int
    end_line: int
    lines: tuple[tuple[int, str], ...]
    truncated: bool
    content_hash: str


@dataclass(frozen=True, slots=True)
class AnalysisJobView:
    """Public in-process job state exposed by the localhost API."""

    analysis_id: str
    state: AnalysisState
    phase: str
    completed: int
    total: int
    current_file: str
    repository_id: str | None
    snapshot_id: str | None
    message: str | None


class RepositoryReviewService:
    """Coordinate discovery, AST extraction, and atomic snapshot persistence."""

    def __init__(
        self,
        *,
        data_directory: Path | None = None,
        limits: ScanLimits | None = None,
        configured_excludes: Sequence[str] = (),
        store: SnapshotStore | None = None,
        discovery: RepositoryDiscovery | None = None,
        analyzer: PythonAnalyzer | None = None,
        relationship_analyzer: RelationshipAnalyzer | None = None,
    ) -> None:
        self.limits = limits or ScanLimits()
        self.store = store or SnapshotStore(data_directory)
        self.discovery = discovery or RepositoryDiscovery(
            limits=self.limits,
            configured_excludes=configured_excludes,
        )
        self.analyzer = analyzer or PythonAnalyzer()
        self.relationship_analyzer = relationship_analyzer or RelationshipAnalyzer()

    def analyze(
        self,
        repository_path: Path,
        *,
        analysis_id: str | None = None,
        cancelled: Callable[[], bool] | None = None,
        progress: ProgressCallback | None = None,
    ) -> AnalysisEvidence:
        """Run one metadata-only scan and atomically promote its snapshot."""

        cancellation = cancelled or (lambda: False)
        job_id = analysis_id or self.store.allocate_analysis_id()
        started_at = _utc_now()
        started = time.perf_counter()
        began_persisted_analysis = False

        def report(phase: str, completed: int, total: int, current_file: str) -> None:
            update = AnalysisProgress(
                phase=phase,
                completed=completed,
                total=total,
                current_file=current_file,
            )
            if progress is not None:
                progress(update)
            if began_persisted_analysis:
                self.store.update_analysis_progress(
                    job_id,
                    completed=completed,
                    total=total,
                    phase=phase,
                )

        try:
            report("discovery", 0, 0, "")
            discovery = self.discovery.discover(
                repository_path,
                cancelled=cancellation,
                progress=lambda completed, total, current: report("discovery", completed, total, current),
            )
            self.store.begin_analysis(
                analysis_id=job_id,
                repository=discovery.repository,
                started_at=started_at,
            )
            began_persisted_analysis = True
            if cancellation():
                raise AnalysisCancelled("Repository analysis was cancelled.")
            analysis = self.analyzer.analyze(
                discovery.files,
                cancelled=cancellation,
                progress=lambda completed, total, current: report("analysis", completed, total, current),
            )
            if cancellation():
                raise AnalysisCancelled("Repository analysis was cancelled.")
            report("relationships", 0, len(analysis.modules), "")
            relationship_analysis = self.relationship_analyzer.analyze(
                analysis.modules,
                analysis.symbols,
                analysis.type_references,
            )
            if cancellation():
                raise AnalysisCancelled("Repository analysis was cancelled.")
            report("storage", len(analysis.files), len(analysis.files), "")
            diagnostics = tuple(
                sorted(
                    (*discovery.diagnostics, *analysis.diagnostics),
                    key=lambda item: item.diagnostic_id,
                )
            )
            snapshot_id = _snapshot_identifier(
                repository=discovery.repository,
                source_fingerprint=discovery.source_fingerprint,
                files=analysis.files,
                modules=analysis.modules,
                symbols=analysis.symbols,
                diagnostics=diagnostics,
                graph_nodes=relationship_analysis.nodes,
                relationships=relationship_analysis.relationships,
                cycles=relationship_analysis.cycles,
                truncated=discovery.truncated,
            )
            completed_at = _utc_now()
            snapshot = SnapshotRecord(
                snapshot_id=snapshot_id,
                repository_id=discovery.repository.repository_id,
                analyzer_version=ANALYZER_VERSION,
                schema_version=SCHEMA_VERSION,
                rule_set_version=RULE_SET_VERSION,
                state=AnalysisState.COMPLETED,
                source_fingerprint=discovery.source_fingerprint,
                file_count=len(analysis.files),
                included_file_count=sum(item.included for item in analysis.files),
                module_count=len(analysis.modules),
                symbol_count=len(analysis.symbols),
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=max(round((time.perf_counter() - started) * 1_000), 0),
                truncated=discovery.truncated,
                parse_gap_count=sum(item.category in {"parse_error", "decode_error"} for item in diagnostics),
            )
            evidence = AnalysisEvidence(
                repository=discovery.repository,
                snapshot=snapshot,
                files=analysis.files,
                modules=analysis.modules,
                symbols=analysis.symbols,
                diagnostics=diagnostics,
                graph_nodes=relationship_analysis.nodes,
                relationships=relationship_analysis.relationships,
                cycles=relationship_analysis.cycles,
            )
            self.store.save_completed_snapshot(job_id, evidence)
            report(
                "completed",
                snapshot.included_file_count,
                snapshot.included_file_count,
                "",
            )
            return evidence
        except AnalysisCancelled:
            if began_persisted_analysis:
                self.store.finish_analysis(
                    job_id,
                    state=AnalysisState.CANCELLED,
                    completed_at=_utc_now(),
                    message="Analysis cancelled.",
                )
            raise
        except Exception:
            if began_persisted_analysis:
                self.store.finish_analysis(
                    job_id,
                    state=AnalysisState.FAILED,
                    completed_at=_utc_now(),
                    message="Analysis failed.",
                )
            raise

    def list_repositories(self) -> tuple[RepositoryRecord, ...]:
        return self.store.list_repositories()

    def list_snapshots(self, repository_id: str) -> tuple[SnapshotRecord, ...]:
        return self.store.list_snapshots(repository_id)

    def get_snapshot(self, snapshot_id: str) -> SnapshotRecord:
        return self.store.get_snapshot(snapshot_id)

    def overview(self, snapshot_id: str) -> dict[str, object]:
        snapshot = self.store.get_snapshot(snapshot_id)
        repository = self.store.get_snapshot_repository(snapshot_id)
        counts = self.store.overview_counts(snapshot_id)
        relationship_counts = self.store.relationship_overview_counts(snapshot_id)
        return {
            "repository": _public_repository(repository),
            "snapshot": _public_snapshot(snapshot),
            "counts": {
                "files_analyzed": snapshot.included_file_count,
                "files_excluded": snapshot.file_count - snapshot.included_file_count,
                "packages": counts.get("packages", 0),
                "modules": snapshot.module_count,
                "classes": counts.get("class", 0),
                "functions": counts.get("function", 0),
                "methods": counts.get("method", 0),
                "parse_gaps": snapshot.parse_gap_count,
                **relationship_counts,
            },
        }

    def symbols(
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
        return self.store.list_symbols(
            snapshot_id,
            search=search,
            kind=kind,
            module=module,
            visibility=visibility,
            sort=sort,
            direction=direction,
            page=page,
            page_size=page_size,
        )

    def symbol_filters(self, snapshot_id: str) -> dict[str, tuple[str, ...]]:
        return self.store.list_symbol_filters(snapshot_id)

    def diagnostics(self, snapshot_id: str) -> tuple[object, ...]:
        return self.store.list_diagnostics(snapshot_id)

    def relationship_summary(
        self,
        snapshot_id: str,
        *,
        max_nodes: int = 200,
    ) -> dict[str, object]:
        if max_nodes < 1 or max_nodes > 500:
            raise ValueError("Relationship node limit is outside the supported range.")
        snapshot = self.store.get_snapshot(snapshot_id)
        if not _version_at_least(snapshot.schema_version, 2):
            return {
                "supported": False,
                "analyzer_version": snapshot.analyzer_version,
                "schema_version": snapshot.schema_version,
                "node_count": 0,
                "relationship_count": 0,
                "cycle_count": 0,
                "largest_cycle_size": 0,
                "truncated": False,
                "nodes": [],
                "relationship_types": {},
                "resolution_statuses": {},
                "fan_in": {},
                "fan_out": {},
                "inheritance_depth": {},
            }
        nodes = self.store.list_graph_nodes(snapshot_id)
        relationships = self.store.all_relationships(snapshot_id)
        cycles = self.store.list_cycles(snapshot_id, limit=200)
        metrics = graph_metrics(nodes, relationships)
        visible_nodes = nodes[:max_nodes]
        visible_node_ids = {item.node_id for item in visible_nodes}
        type_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for relationship in relationships:
            type_counts[relationship.relationship_type] = (
                type_counts.get(relationship.relationship_type, 0) + 1
            )
            status_counts[relationship.resolution_status] = (
                status_counts.get(relationship.resolution_status, 0) + 1
            )
        return {
            "supported": True,
            "analyzer_version": snapshot.analyzer_version,
            "schema_version": snapshot.schema_version,
            "node_count": len(nodes),
            "relationship_count": len(relationships),
            "cycle_count": len(cycles),
            "largest_cycle_size": max((len(item.member_node_ids) for item in cycles), default=0),
            "truncated": len(nodes) > max_nodes,
            "nodes": [public_graph_node(item) for item in visible_nodes],
            "relationship_types": dict(sorted(type_counts.items())),
            "resolution_statuses": dict(sorted(status_counts.items())),
            "fan_in": dict(item for item in metrics.fan_in if item[0] in visible_node_ids),
            "fan_out": dict(item for item in metrics.fan_out if item[0] in visible_node_ids),
            "inheritance_depth": dict(
                item for item in metrics.inheritance_depth if item[0] in visible_node_ids
            ),
        }

    def relationships(
        self,
        snapshot_id: str,
        *,
        relationship_type: str | None = None,
        resolution_status: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, object]:
        snapshot = self.store.get_snapshot(snapshot_id)
        if not _version_at_least(snapshot.schema_version, 2):
            return {
                "supported": False,
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
            }
        result = self.store.list_relationships(
            snapshot_id,
            relationship_type=relationship_type,
            resolution_status=resolution_status,
            page=page,
            page_size=page_size,
        )
        return {
            "supported": True,
            "items": [public_relationship(item) for item in result.items],
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        }

    def relationship_nodes(
        self,
        snapshot_id: str,
        *,
        mode: str,
        search: str = "",
        node_ids: tuple[str, ...] = (),
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, object]:
        snapshot = self.store.get_snapshot(snapshot_id)
        if not _version_at_least(snapshot.schema_version, 2):
            return {
                "supported": False,
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "truncated": False,
            }
        result = self.store.query_graph_nodes(
            snapshot_id,
            mode=mode,
            search=search,
            node_ids=node_ids,
            page=page,
            page_size=page_size,
        )
        return {
            "supported": True,
            "items": [public_graph_node(item) for item in result.items],
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "truncated": result.page * result.page_size < result.total,
        }

    def relationship_neighborhood(
        self,
        snapshot_id: str,
        *,
        focus_id: str,
        mode: str,
        depth: int,
        max_nodes: int,
        max_edges: int,
        resolution_status: str | None = None,
        relationship_type: str | None = None,
    ) -> dict[str, object]:
        if mode not in {"modules", "packages", "inheritance", "containment", "types"}:
            raise ValueError("Unsupported relationship graph mode.")
        if depth < 1 or depth > 3:
            raise ValueError("Relationship depth is outside the supported range.")
        if max_nodes < 1 or max_nodes > 100 or max_edges < 1 or max_edges > 200:
            raise ValueError("Relationship graph limits are outside the supported range.")
        snapshot = self.store.get_snapshot(snapshot_id)
        if not _version_at_least(snapshot.schema_version, 2):
            return {
                "supported": False,
                "focus_id": focus_id,
                "mode": mode,
                "depth": depth,
                "nodes": [],
                "relationships": [],
                "distances": {},
                "truncated": False,
            }
        nodes = self.store.list_graph_nodes(snapshot_id)
        relationships = self.store.all_relationships(snapshot_id)
        nodes, relationships = _select_graph_mode(nodes, relationships, mode)
        if relationship_type is not None:
            relationships = tuple(
                item for item in relationships if item.relationship_type == relationship_type
            )
        if resolution_status is not None:
            relationships = tuple(
                item for item in relationships if item.resolution_status == resolution_status
            )
        try:
            result = bounded_neighborhood(
                nodes,
                relationships,
                focus_id=focus_id,
                depth=depth,
                max_nodes=max_nodes,
                max_edges=max_edges,
            )
        except KeyError as exc:
            raise ValueError("Focus node is not available in the selected graph mode.") from exc
        return {
            "supported": True,
            "focus_id": focus_id,
            "mode": mode,
            "depth": depth,
            "nodes": [public_graph_node(item) for item in result.nodes],
            "relationships": [public_relationship(item) for item in result.relationships],
            "distances": dict(result.distances),
            "truncated": result.truncated,
        }

    def cycles(
        self,
        snapshot_id: str,
        *,
        relationship_type: str | None = None,
        max_results: int = 100,
    ) -> dict[str, object]:
        snapshot = self.store.get_snapshot(snapshot_id)
        if not _version_at_least(snapshot.schema_version, 2):
            return {"supported": False, "items": [], "truncated": False}
        requested_limit = max_results + 1
        if max_results < 1 or max_results > 100:
            raise ValueError("Cycle result limit is outside the supported range.")
        items = self.store.list_cycles(
            snapshot_id,
            relationship_type=relationship_type,
            limit=requested_limit,
        )
        return {
            "supported": True,
            "items": [public_cycle(item) for item in items[:max_results]],
            "truncated": len(items) > max_results,
        }

    def read_source(
        self,
        snapshot_id: str,
        relative_path: str,
        *,
        start_line: int,
        end_line: int,
    ) -> SourceEvidence:
        """Read a bounded current excerpt only when it still matches snapshot evidence."""

        normalized = _safe_relative_path(relative_path)
        if start_line < 1 or end_line < start_line:
            raise SourceEvidenceError("Source line range is invalid.")
        if end_line - start_line + 1 > self.limits.max_source_lines:
            end_line = start_line + self.limits.max_source_lines - 1
        file_record = self.store.get_file(snapshot_id, normalized)
        if file_record is None or not file_record.included or file_record.content_hash is None:
            raise SourceEvidenceError("Source evidence is not available for this file.")
        repository = self.store.get_snapshot_repository(snapshot_id)
        root = Path(repository.canonical_path)
        candidate = root / PurePosixPath(normalized)
        try:
            resolved = candidate.resolve(strict=True)
            resolved_root = root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise SourceEvidenceError("Source evidence path is unavailable.") from exc
        if not resolved.is_relative_to(resolved_root) or candidate.is_symlink():
            raise SourceEvidenceError("Source evidence path is outside the repository boundary.")
        try:
            content = resolved.read_bytes()
        except OSError as exc:
            raise SourceEvidenceError("Source evidence could not be read.") from exc
        current_hash = hashlib.sha256(content).hexdigest()
        if current_hash != file_record.content_hash:
            raise SourceEvidenceError("Source changed after this snapshot; run a new analysis.")
        text = _decode_python(content)
        selected: list[tuple[int, str]] = []
        byte_count = 0
        truncated = False
        for number, line in enumerate(text.splitlines(), start=1):
            if number < start_line:
                continue
            if number > end_line:
                break
            encoded = (line + "\n").encode("utf-8")
            if byte_count + len(encoded) > self.limits.max_source_bytes:
                truncated = True
                break
            selected.append((number, line))
            byte_count += len(encoded)
        actual_end = selected[-1][0] if selected else start_line
        return SourceEvidence(
            relative_path=normalized,
            start_line=start_line,
            end_line=actual_end,
            lines=tuple(selected),
            truncated=truncated,
            content_hash=current_hash,
        )


class RepositoryReviewJobManager:
    """Small in-process job manager with cooperative cancellation."""

    def __init__(self, service: RepositoryReviewService, *, max_workers: int = 2) -> None:
        self.service = service
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="zscripts-review",
        )
        self._lock = threading.Lock()
        self._jobs: dict[str, _MutableJob] = {}

    def start(self, repository_path: Path) -> AnalysisJobView:
        analysis_id = self.service.store.allocate_analysis_id()
        job = _MutableJob(analysis_id=analysis_id)
        with self._lock:
            self._jobs[analysis_id] = job
        future = self._executor.submit(self._run, job, repository_path)
        job.future = future
        return job.view()

    def cancel(self, analysis_id: str) -> AnalysisJobView | None:
        with self._lock:
            job = self._jobs.get(analysis_id)
            if job is None:
                return None
            job.cancel_event.set()
            if job.state is AnalysisState.STARTED:
                job.phase = "cancelling"
            return job.view()

    def get(self, analysis_id: str) -> AnalysisJobView | None:
        with self._lock:
            job = self._jobs.get(analysis_id)
            return job.view() if job is not None else None

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _run(self, job: "_MutableJob", repository_path: Path) -> None:
        def update(progress: AnalysisProgress) -> None:
            with self._lock:
                job.phase = progress.phase
                job.completed = progress.completed
                job.total = progress.total
                job.current_file = progress.current_file

        try:
            evidence = self.service.analyze(
                repository_path,
                analysis_id=job.analysis_id,
                cancelled=job.cancel_event.is_set,
                progress=update,
            )
        except AnalysisCancelled:
            with self._lock:
                job.state = AnalysisState.CANCELLED
                job.phase = "cancelled"
                job.current_file = ""
                job.message = "Analysis cancelled."
            return
        except Exception:
            with self._lock:
                job.state = AnalysisState.FAILED
                job.phase = "failed"
                job.current_file = ""
                job.message = "Analysis failed."
            return
        with self._lock:
            job.state = AnalysisState.COMPLETED
            job.phase = "completed"
            job.current_file = ""
            job.repository_id = evidence.repository.repository_id
            job.snapshot_id = evidence.snapshot.snapshot_id
            job.completed = evidence.snapshot.included_file_count
            job.total = evidence.snapshot.included_file_count


@dataclass(slots=True)
class _MutableJob:
    analysis_id: str
    state: AnalysisState = AnalysisState.STARTED
    phase: str = "queued"
    completed: int = 0
    total: int = 0
    current_file: str = ""
    repository_id: str | None = None
    snapshot_id: str | None = None
    message: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    future: Future[None] | None = None

    def view(self) -> AnalysisJobView:
        return AnalysisJobView(
            analysis_id=self.analysis_id,
            state=self.state,
            phase=self.phase,
            completed=self.completed,
            total=self.total,
            current_file=self.current_file,
            repository_id=self.repository_id,
            snapshot_id=self.snapshot_id,
            message=self.message,
        )


def _snapshot_identifier(
    *,
    repository: RepositoryRecord,
    source_fingerprint: str,
    files: Sequence[object],
    modules: Sequence[object],
    symbols: Sequence[SymbolRecord],
    diagnostics: Sequence[object],
    graph_nodes: Sequence[GraphNodeRecord],
    relationships: Sequence[RelationshipRecord],
    cycles: Sequence[CycleGroupRecord],
    truncated: bool,
) -> str:
    return stable_digest(
        "repository-review-snapshot",
        {
            "repository_id": repository.repository_id,
            "configuration_digest": repository.configuration_digest,
            "source_fingerprint": source_fingerprint,
            "analyzer_version": ANALYZER_VERSION,
            "schema_version": SCHEMA_VERSION,
            "rule_set_version": RULE_SET_VERSION,
            "files": [getattr(item, "file_id") for item in files],
            "modules": [getattr(item, "module_id") for item in modules],
            "symbols": [item.symbol_id for item in symbols],
            "diagnostics": [getattr(item, "diagnostic_id") for item in diagnostics],
            "graph_nodes": [item.node_id for item in graph_nodes],
            "relationships": [item.relationship_id for item in relationships],
            "cycles": [item.cycle_id for item in cycles],
            "truncated": truncated,
        },
    )


def _public_repository(repository: RepositoryRecord) -> dict[str, object]:
    return {
        "repository_id": repository.repository_id,
        "display_name": repository.display_name,
        "branch": repository.branch,
        "git_sha": repository.git_sha,
        "dirty": repository.dirty,
        "staged": repository.staged,
        "untracked": repository.untracked,
        "configuration_digest": repository.configuration_digest,
        "source_roots": repository.source_roots,
        "test_roots": repository.test_roots,
    }


def _public_snapshot(snapshot: SnapshotRecord) -> dict[str, object]:
    return {
        "snapshot_id": snapshot.snapshot_id,
        "repository_id": snapshot.repository_id,
        "analyzer_version": snapshot.analyzer_version,
        "schema_version": snapshot.schema_version,
        "rule_set_version": snapshot.rule_set_version,
        "state": snapshot.state.value,
        "source_fingerprint": snapshot.source_fingerprint,
        "file_count": snapshot.file_count,
        "included_file_count": snapshot.included_file_count,
        "module_count": snapshot.module_count,
        "symbol_count": snapshot.symbol_count,
        "started_at": snapshot.started_at,
        "completed_at": snapshot.completed_at,
        "duration_ms": snapshot.duration_ms,
        "truncated": snapshot.truncated,
        "parse_gap_count": snapshot.parse_gap_count,
    }


def public_repository(repository: RepositoryRecord) -> dict[str, object]:
    """Return a repository representation without canonical local paths."""

    return _public_repository(repository)


def public_snapshot(snapshot: SnapshotRecord) -> dict[str, object]:
    """Return a completed snapshot representation for CLI/API consumers."""

    return _public_snapshot(snapshot)


def public_symbol(symbol: SymbolRecord) -> dict[str, object]:
    """Return a JSON-compatible symbol representation."""

    return {
        "symbol_id": symbol.symbol_id,
        "language": symbol.language,
        "kind": symbol.kind,
        "qualified_name": symbol.qualified_name,
        "display_name": symbol.display_name,
        "module_name": symbol.module_name,
        "relative_path": symbol.relative_path,
        "start_line": symbol.start_line,
        "start_column": symbol.start_column,
        "end_line": symbol.end_line,
        "end_column": symbol.end_column,
        "parent_symbol_id": symbol.parent_symbol_id,
        "visibility": symbol.visibility,
        "signature": symbol.signature,
        "annotations": symbol.annotations,
        "decorators": symbol.decorators,
        "docstring_present": symbol.docstring_present,
        "async_flag": symbol.async_flag,
        "content_fingerprint": symbol.content_fingerprint,
        "bases": symbol.bases,
    }


def public_graph_node(node: GraphNodeRecord) -> dict[str, object]:
    """Return a graph node without local-only repository state."""

    return {
        "node_id": node.node_id,
        "node_type": node.node_type,
        "display_name": node.display_name,
        "qualified_name": node.qualified_name,
        "relative_path": node.relative_path,
        "symbol_kind": node.symbol_kind,
    }


def public_relationship(relationship: RelationshipRecord) -> dict[str, object]:
    """Return canonical relationship evidence using repository-relative locations."""

    return {
        "relationship_id": relationship.relationship_id,
        "relationship_type": relationship.relationship_type,
        "source_id": relationship.source_id,
        "target_id": relationship.target_id,
        "unresolved_target": relationship.unresolved_target,
        "resolution_status": relationship.resolution_status,
        "confidence": relationship.confidence,
        "relative_path": relationship.relative_path,
        "line": relationship.line,
        "column": relationship.column,
        "analyzer_version": relationship.analyzer_version,
        "evidence": relationship.evidence,
    }


def public_cycle(cycle: CycleGroupRecord) -> dict[str, object]:
    """Return deterministic cycle membership and edge evidence."""

    return {
        "cycle_id": cycle.cycle_id,
        "relationship_type": cycle.relationship_type,
        "member_node_ids": cycle.member_node_ids,
        "edge_ids": cycle.edge_ids,
    }


def _select_graph_mode(
    nodes: Sequence[GraphNodeRecord],
    relationships: Sequence[RelationshipRecord],
    mode: str,
) -> tuple[tuple[GraphNodeRecord, ...], tuple[RelationshipRecord, ...]]:
    if mode == "modules":
        selected_nodes = tuple(item for item in nodes if item.node_type == "module")
        selected_edges = tuple(item for item in relationships if item.relationship_type == "imports")
    elif mode == "packages":
        selected_nodes, selected_edges = _package_dependency_graph(nodes, relationships)
    elif mode == "inheritance":
        selected_nodes = tuple(
            item for item in nodes if item.node_type == "symbol" and item.symbol_kind == "class"
        )
        selected_edges = tuple(item for item in relationships if item.relationship_type == "inherits")
    elif mode == "types":
        selected_nodes = tuple(item for item in nodes if item.node_type == "symbol")
        selected_edges = tuple(item for item in relationships if item.relationship_type == "references-type")
    else:
        selected_nodes = tuple(nodes)
        selected_edges = tuple(item for item in relationships if item.relationship_type == "contains")
    node_ids = {item.node_id for item in selected_nodes}
    return (
        tuple(sorted(selected_nodes, key=lambda item: (item.qualified_name, item.node_id))),
        tuple(
            sorted(
                (
                    item
                    for item in selected_edges
                    if item.source_id in node_ids and (item.target_id is None or item.target_id in node_ids)
                ),
                key=lambda item: item.relationship_id,
            )
        ),
    )


def _package_dependency_graph(
    nodes: Sequence[GraphNodeRecord],
    relationships: Sequence[RelationshipRecord],
) -> tuple[tuple[GraphNodeRecord, ...], tuple[RelationshipRecord, ...]]:
    package_nodes = {item.qualified_name: item for item in nodes if item.node_type == "package"}
    module_nodes = {item.node_id: item for item in nodes if item.node_type == "module"}
    packages_by_module: dict[str, GraphNodeRecord] = {}
    for module_id, node in module_nodes.items():
        if node.relative_path and PurePosixPath(node.relative_path).name == "__init__.py":
            package_name = node.qualified_name
        else:
            package_name = node.qualified_name.rpartition(".")[0]
        package = package_nodes.get(package_name)
        if package is not None:
            packages_by_module[module_id] = package
    grouped: dict[tuple[str, str], list[RelationshipRecord]] = {}
    for relationship in relationships:
        if (
            relationship.relationship_type != "imports"
            or relationship.target_id is None
            or relationship.resolution_status not in {"resolved-static", "probable-static"}
        ):
            continue
        source = packages_by_module.get(relationship.source_id)
        target = packages_by_module.get(relationship.target_id)
        if source is None or target is None or source.node_id == target.node_id:
            continue
        grouped.setdefault((source.node_id, target.node_id), []).append(relationship)
    edges: list[RelationshipRecord] = []
    for (source_id, target_id), members in sorted(grouped.items()):
        first = min(members, key=lambda item: item.relationship_id)
        payload = {
            "source_id": source_id,
            "target_id": target_id,
            "member_edges": sorted(item.relationship_id for item in members),
        }
        edges.append(
            RelationshipRecord(
                relationship_id=stable_digest("repository-review-package-dependency", payload),
                relationship_type="imports",
                source_id=source_id,
                target_id=target_id,
                unresolved_target=None,
                resolution_status="resolved-static",
                confidence="high",
                relative_path=first.relative_path,
                line=first.line,
                column=first.column,
                analyzer_version=first.analyzer_version,
                evidence=f"{len(members)} resolved module import edge(s)",
            )
        )
    return (
        tuple(
            sorted(
                package_nodes.values(),
                key=lambda item: (item.qualified_name, item.node_id),
            )
        ),
        tuple(edges),
    )


def _version_at_least(value: str, minimum: int) -> bool:
    try:
        return int(value) >= minimum
    except ValueError:
        return False


def _safe_relative_path(value: str) -> str:
    normalized = PurePosixPath(value.replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts or not normalized.parts:
        raise SourceEvidenceError("Source evidence path must be repository-relative.")
    return normalized.as_posix()


def _decode_python(content: bytes) -> str:
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(content).readline)
        return content.decode(encoding)
    except (SyntaxError, UnicodeDecodeError, LookupError) as exc:
        raise SourceEvidenceError("Source evidence could not be decoded.") from exc


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


__all__ = [
    "AnalysisJobView",
    "AnalysisProgress",
    "AnalysisStatusRecord",
    "RepositoryReviewJobManager",
    "RepositoryReviewService",
    "SourceEvidence",
    "SourceEvidenceError",
    "public_cycle",
    "public_graph_node",
    "public_relationship",
    "public_repository",
    "public_snapshot",
    "public_symbol",
]
