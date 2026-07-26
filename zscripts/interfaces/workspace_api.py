"""Typed localhost-only FastAPI surface for repository review."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator

from zscripts.application.repository_review import (
    AnalysisJobView,
    RepositoryReviewJobManager,
    RepositoryReviewService,
    SourceEvidenceError,
    public_repository,
    public_snapshot,
    public_symbol,
)
from zscripts.domain.repository_review import AnalysisState
from zscripts.infrastructure.snapshot_store import SnapshotNotFoundError

LOCALHOST = "127.0.0.1"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalyzeRequest(_StrictModel):
    repository_path: str | None = Field(default=None, min_length=1, max_length=1_024)
    repository_id: str | None = Field(default=None, min_length=16, max_length=128)

    @model_validator(mode="after")
    def require_one_repository_selector(self) -> "AnalyzeRequest":
        if (self.repository_path is None) == (self.repository_id is None):
            raise ValueError("Provide exactly one repository selector.")
        return self


class RepositoryResponse(_StrictModel):
    repository_id: str
    display_name: str
    branch: str | None
    git_sha: str | None
    dirty: bool
    staged: bool
    untracked: bool
    configuration_digest: str
    source_roots: list[str]
    test_roots: list[str]


class SnapshotResponse(_StrictModel):
    snapshot_id: str
    repository_id: str
    analyzer_version: str
    schema_version: str
    rule_set_version: str
    state: Literal["completed"]
    source_fingerprint: str
    file_count: int
    included_file_count: int
    module_count: int
    symbol_count: int
    started_at: str
    completed_at: str | None
    duration_ms: int
    truncated: bool
    parse_gap_count: int


class AnalysisResponse(_StrictModel):
    analysis_id: str
    state: str
    phase: str
    completed: int
    total: int
    current_file: str
    repository_id: str | None
    snapshot_id: str | None
    message: str | None


class RepositoryListResponse(_StrictModel):
    repositories: list[RepositoryResponse]


class SnapshotListResponse(_StrictModel):
    snapshots: list[SnapshotResponse]


class SnapshotDetailResponse(_StrictModel):
    repository: RepositoryResponse
    snapshot: SnapshotResponse


class OverviewCounts(_StrictModel):
    files_analyzed: int
    files_excluded: int
    packages: int
    modules: int
    classes: int
    functions: int
    methods: int
    parse_gaps: int
    relationship_analysis_supported: bool
    resolved_import_edges: int
    inheritance_edges: int
    cycle_groups: int
    largest_cycle_size: int


class OverviewResponse(_StrictModel):
    repository: RepositoryResponse
    snapshot: SnapshotResponse
    counts: OverviewCounts


class SymbolResponse(_StrictModel):
    symbol_id: str
    language: str
    kind: str
    qualified_name: str
    display_name: str
    module_name: str
    relative_path: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    parent_symbol_id: str | None
    visibility: str
    signature: str
    annotations: list[str]
    decorators: list[str]
    docstring_present: bool
    async_flag: bool
    content_fingerprint: str
    bases: list[str]


class SymbolFiltersResponse(_StrictModel):
    kinds: list[str]
    modules: list[str]
    visibilities: list[str]


class SymbolPageResponse(_StrictModel):
    items: list[SymbolResponse]
    total: int
    page: int
    page_size: int
    filters: SymbolFiltersResponse


class SourceLineResponse(_StrictModel):
    number: int
    text: str


class SourceEvidenceResponse(_StrictModel):
    relative_path: str
    start_line: int
    end_line: int
    lines: list[SourceLineResponse]
    truncated: bool
    content_hash: str


class GraphNodeResponse(_StrictModel):
    node_id: str
    node_type: Literal["package", "module", "symbol"]
    display_name: str
    qualified_name: str
    relative_path: str | None
    symbol_kind: str | None


class RelationshipResponse(_StrictModel):
    relationship_id: str
    relationship_type: Literal["contains", "imports", "inherits", "references-type"]
    source_id: str
    target_id: str | None
    unresolved_target: str | None
    resolution_status: Literal["resolved-static", "probable-static", "ambiguous", "unresolved-dynamic"]
    confidence: Literal["high", "medium", "low"]
    relative_path: str
    line: int
    column: int
    analyzer_version: str
    evidence: str


class RelationshipSummaryResponse(_StrictModel):
    supported: bool
    analyzer_version: str
    schema_version: str
    node_count: int
    relationship_count: int
    cycle_count: int
    largest_cycle_size: int
    truncated: bool
    nodes: list[GraphNodeResponse]
    relationship_types: dict[str, int]
    resolution_statuses: dict[str, int]
    fan_in: dict[str, int]
    fan_out: dict[str, int]
    inheritance_depth: dict[str, int | None]


class RelationshipPageResponse(_StrictModel):
    supported: bool
    items: list[RelationshipResponse]
    total: int
    page: int
    page_size: int


class RelationshipNeighborhoodResponse(_StrictModel):
    supported: bool
    focus_id: str
    mode: Literal["modules", "packages", "inheritance", "containment", "types"]
    depth: int
    nodes: list[GraphNodeResponse]
    relationships: list[RelationshipResponse]
    distances: dict[str, int]
    truncated: bool


class CycleResponse(_StrictModel):
    cycle_id: str
    relationship_type: Literal["imports", "inherits"]
    member_node_ids: list[str]
    edge_ids: list[str]


class CycleListResponse(_StrictModel):
    supported: bool
    items: list[CycleResponse]
    truncated: bool


class HealthResponse(_StrictModel):
    status: Literal["ok"]
    service: Literal["repository-review"]
    schema_version: Literal["2"]


def create_workspace_app(
    *,
    service: RepositoryReviewService | None = None,
    data_directory: Path | None = None,
) -> FastAPI:
    """Create the same-origin API and packaged static workspace."""

    review_service = service or RepositoryReviewService(data_directory=data_directory)
    jobs = RepositoryReviewJobManager(review_service)

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        yield
        jobs.shutdown()

    app = FastAPI(
        title="Zscripts Experimental Repository Review API",
        version="0.1-experimental",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.review_service = review_service
    app.state.review_jobs = jobs

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request,  # noqa: ARG001 - FastAPI handler contract
        exc: RequestValidationError,  # noqa: ARG001 - deliberately not serialized
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": "Request validation failed."})

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "repository-review", "schema_version": "2"}

    @app.get("/api/repositories", response_model=RepositoryListResponse)
    def repositories() -> dict[str, object]:
        return {
            "repositories": [
                public_repository(repository) for repository in review_service.list_repositories()
            ]
        }

    @app.post("/api/repositories/analyze", response_model=AnalysisResponse, status_code=202)
    def analyze(request: AnalyzeRequest) -> dict[str, object]:
        if request.repository_id is not None:
            repository = review_service.store.get_repository(request.repository_id)
            if repository is None:
                raise HTTPException(status_code=404, detail="Repository was not found.")
            path = Path(repository.canonical_path)
        else:
            path = Path(request.repository_path or "")
        job = jobs.start(path)
        return _job_payload(job)

    @app.get("/api/analyses/{analysis_id}", response_model=AnalysisResponse)
    def analysis(analysis_id: str) -> dict[str, object]:
        job = jobs.get(analysis_id)
        if job is None:
            persisted = review_service.store.get_analysis(analysis_id)
            if persisted is None:
                raise HTTPException(status_code=404, detail="Analysis was not found.")
            return _persisted_job_payload(persisted)
        return _job_payload(job)

    @app.post("/api/analyses/{analysis_id}/cancel", response_model=AnalysisResponse)
    def cancel(analysis_id: str) -> dict[str, object]:
        job = jobs.cancel(analysis_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Analysis was not found.")
        return _job_payload(job)

    @app.get(
        "/api/repositories/{repository_id}/snapshots",
        response_model=SnapshotListResponse,
    )
    def repository_snapshots(repository_id: str) -> dict[str, object]:
        return {
            "snapshots": [
                public_snapshot(snapshot) for snapshot in review_service.list_snapshots(repository_id)
            ]
        }

    @app.get("/api/snapshots/{snapshot_id}", response_model=SnapshotDetailResponse)
    def snapshot(snapshot_id: str) -> dict[str, object]:
        try:
            record = review_service.get_snapshot(snapshot_id)
            repository = review_service.store.get_snapshot_repository(snapshot_id)
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Snapshot was not found.") from exc
        return {
            "repository": public_repository(repository),
            "snapshot": public_snapshot(record),
        }

    @app.get("/api/snapshots/{snapshot_id}/overview", response_model=OverviewResponse)
    def overview(snapshot_id: str) -> dict[str, object]:
        try:
            return review_service.overview(snapshot_id)
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Snapshot was not found.") from exc

    @app.get("/api/snapshots/{snapshot_id}/symbols", response_model=SymbolPageResponse)
    def symbols(
        snapshot_id: str,
        search: Annotated[str, Query(max_length=256)] = "",
        kind: Annotated[str | None, Query(max_length=64)] = None,
        module: Annotated[str | None, Query(max_length=256)] = None,
        visibility: Annotated[str | None, Query(max_length=32)] = None,
        sort: Literal[
            "qualified_name", "kind", "signature", "module", "file", "line", "visibility"
        ] = "qualified_name",
        direction: Literal["asc", "desc"] = "asc",
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> dict[str, object]:
        try:
            result = review_service.symbols(
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
            filters = review_service.symbol_filters(snapshot_id)
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Snapshot was not found.") from exc
        return {
            "items": [public_symbol(item) for item in result.items],
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "filters": filters,
        }

    @app.get("/api/snapshots/{snapshot_id}/source", response_model=SourceEvidenceResponse)
    def source(
        snapshot_id: str,
        path: Annotated[str, Query(min_length=1, max_length=1_024)],
        start_line: Annotated[int, Query(ge=1)] = 1,
        end_line: Annotated[int, Query(ge=1)] = 200,
    ) -> dict[str, object]:
        try:
            evidence = review_service.read_source(
                snapshot_id,
                path,
                start_line=start_line,
                end_line=end_line,
            )
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Snapshot was not found.") from exc
        except SourceEvidenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "relative_path": evidence.relative_path,
            "start_line": evidence.start_line,
            "end_line": evidence.end_line,
            "lines": [{"number": number, "text": text} for number, text in evidence.lines],
            "truncated": evidence.truncated,
            "content_hash": evidence.content_hash,
        }

    @app.get(
        "/api/snapshots/{snapshot_id}/relationships/summary",
        response_model=RelationshipSummaryResponse,
    )
    def relationship_summary(
        snapshot_id: str,
        max_nodes: Annotated[int, Query(ge=1, le=500)] = 200,
    ) -> dict[str, object]:
        try:
            return review_service.relationship_summary(snapshot_id, max_nodes=max_nodes)
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Snapshot was not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Relationship query is invalid.") from exc

    @app.get(
        "/api/snapshots/{snapshot_id}/relationships",
        response_model=RelationshipPageResponse,
    )
    def relationships(
        snapshot_id: str,
        relationship_type: Literal["contains", "imports", "inherits", "references-type"] | None = None,
        resolution_status: Literal["resolved-static", "probable-static", "ambiguous", "unresolved-dynamic"]
        | None = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> dict[str, object]:
        try:
            return review_service.relationships(
                snapshot_id,
                relationship_type=relationship_type,
                resolution_status=resolution_status,
                page=page,
                page_size=page_size,
            )
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Snapshot was not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Relationship query is invalid.") from exc

    @app.get(
        "/api/snapshots/{snapshot_id}/relationships/neighborhood",
        response_model=RelationshipNeighborhoodResponse,
    )
    def relationship_neighborhood(
        snapshot_id: str,
        focus_id: Annotated[str, Query(min_length=16, max_length=128)],
        mode: Literal["modules", "packages", "inheritance", "containment", "types"] = "modules",
        depth: Annotated[int, Query(ge=1, le=3)] = 1,
        resolution_status: Literal["resolved-static", "probable-static", "ambiguous", "unresolved-dynamic"]
        | None = None,
        relationship_type: Literal["contains", "imports", "inherits", "references-type"] | None = None,
        max_nodes: Annotated[int, Query(ge=1, le=100)] = 40,
        max_edges: Annotated[int, Query(ge=1, le=200)] = 80,
    ) -> dict[str, object]:
        try:
            return review_service.relationship_neighborhood(
                snapshot_id,
                focus_id=focus_id,
                mode=mode,
                depth=depth,
                max_nodes=max_nodes,
                max_edges=max_edges,
                resolution_status=resolution_status,
                relationship_type=relationship_type,
            )
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Snapshot was not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Relationship query is invalid.") from exc

    @app.get("/api/snapshots/{snapshot_id}/cycles", response_model=CycleListResponse)
    def cycles(
        snapshot_id: str,
        relationship_type: Literal["imports", "inherits"] | None = None,
        max_results: Annotated[int, Query(ge=1, le=100)] = 100,
    ) -> dict[str, object]:
        try:
            return review_service.cycles(
                snapshot_id,
                relationship_type=relationship_type,
                max_results=max_results,
            )
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Snapshot was not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Relationship query is invalid.") from exc

    static_root = Path(__file__).resolve().parents[1] / "workspace_static"
    assets = static_root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="workspace-assets")

    @app.get("/", include_in_schema=False)
    def workspace_index() -> Any:
        index = static_root / "index.html"
        if not index.is_file():
            return JSONResponse(
                status_code=503,
                content={"detail": "Packaged workspace assets are unavailable."},
            )
        return FileResponse(index)

    @app.get("/THIRD_PARTY_NOTICES.md", include_in_schema=False)
    def third_party_notices() -> Any:
        notices = static_root / "THIRD_PARTY_NOTICES.md"
        if not notices.is_file():
            raise HTTPException(status_code=404, detail="Third-party notices were not found.")
        return FileResponse(notices, media_type="text/markdown")

    @app.get("/{route:path}", include_in_schema=False)
    def workspace_route(route: str) -> Any:
        if route == "redoc" or route == "api" or route.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route was not found.")
        index = static_root / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=404, detail="Workspace route was not found.")
        return FileResponse(index)

    return app


def validate_workspace_host(host: str) -> str:
    """Reject all non-loopback binding in the MVP."""

    if host != LOCALHOST:
        raise ValueError("The experimental workspace only supports host 127.0.0.1.")
    return host


def run_workspace(
    *,
    host: str = LOCALHOST,
    port: int = 8765,
    data_directory: Path | None = None,
) -> None:
    """Start Uvicorn on the only supported loopback interface."""

    validate_workspace_host(host)
    if not 1 <= port <= 65_535:
        raise ValueError("Workspace port must be between 1 and 65535.")
    import uvicorn

    uvicorn.run(
        create_workspace_app(data_directory=data_directory),
        host=host,
        port=port,
        log_level="info",
    )


def _job_payload(job: AnalysisJobView) -> dict[str, object]:
    return {
        "analysis_id": job.analysis_id,
        "state": job.state.value,
        "phase": job.phase,
        "completed": job.completed,
        "total": job.total,
        "current_file": job.current_file,
        "repository_id": job.repository_id,
        "snapshot_id": job.snapshot_id,
        "message": job.message,
    }


def _persisted_job_payload(job: Any) -> dict[str, object]:
    state = job.state.value if isinstance(job.state, AnalysisState) else str(job.state)
    return {
        "analysis_id": job.analysis_id,
        "state": state,
        "phase": job.progress_phase,
        "completed": job.progress_completed,
        "total": job.progress_total,
        "current_file": "",
        "repository_id": job.repository_id,
        "snapshot_id": job.snapshot_id,
        "message": job.message,
    }


__all__ = [
    "LOCALHOST",
    "create_workspace_app",
    "run_workspace",
    "validate_workspace_host",
]
