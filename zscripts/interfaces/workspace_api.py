"""Typed localhost-only FastAPI surface for repository review."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator

from zscripts.application.repository_review import (
    AnalysisJobView,
    RepositoryReviewJobManager,
    RepositoryReviewService,
    SourceEvidenceError,
    public_finding,
    public_repository,
    public_snapshot,
    public_symbol,
)
from zscripts.domain.repository_comparison import (
    DEFAULT_HANDOFF_BUDGET,
    HandoffSelection,
)
from zscripts.domain.repository_review import AnalysisState
from zscripts.infrastructure.handoff_rendering import (
    HANDOFF_BUDGET_ERROR_MESSAGE,
    HandoffBudgetError,
)
from zscripts.infrastructure.snapshot_store import (
    ReviewConflictError,
    SavedHandoffIntegrityError,
    SnapshotNotFoundError,
)

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
    active_findings: int
    needs_action_findings: int
    resolved_since_last_scan: int
    high_confidence_high_severity_findings: int


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


class GraphNodePageResponse(_StrictModel):
    supported: bool
    items: list[GraphNodeResponse]
    total: int
    page: int
    page_size: int
    truncated: bool


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


class FindingResponse(_StrictModel):
    finding_id: str
    rule_id: str
    rule_version: str
    family: str
    title: str
    explanation: str
    suggested_action: str
    severity: Literal["high", "medium", "low"]
    confidence: Literal["high", "medium", "low"]
    subject_type: str
    subject_keys: list[str]
    affected_node_ids: list[str]
    relative_path: str | None
    line: int | None
    metric_evidence: list[tuple[str, float]]
    threshold_evidence: list[tuple[str, float]]
    repository_id: str
    first_seen_snapshot_id: str
    last_seen_snapshot_id: str
    evidence_state: Literal["active", "resolved"]
    resolved_snapshot_id: str | None
    review_status: Literal["new", "reviewed", "needs-action", "accepted", "dismissed"]
    effective_status: Literal["new", "reviewed", "needs-action", "accepted", "dismissed", "resolved"]
    note: str
    reason_code: str | None
    review_version: int
    decided_at: str
    updated_at: str


class FindingSummaryResponse(_StrictModel):
    supported: bool
    active: int
    resolved: int
    needs_action: int
    accepted: int
    dismissed: int
    severity: dict[str, int]
    low_confidence: int
    reconciliation_complete: bool
    lifecycle_reconciled: bool
    reconciliation_skip_reason: str | None


class FindingPageResponse(_StrictModel):
    supported: bool
    items: list[FindingResponse]
    total: int
    page: int
    page_size: int


class FindingReviewRequest(_StrictModel):
    expected_version: int = Field(ge=0)
    review_status: Literal["new", "reviewed", "needs-action", "accepted", "dismissed"]
    note: str = Field(max_length=2_000)
    reason_code: (
        Literal[
            "intentional-design",
            "false-positive",
            "accepted-risk",
            "planned-refactor",
            "needs-investigation",
            "other",
        ]
        | None
    ) = None


class FindingEventResponse(_StrictModel):
    event_id: int
    finding_id: str
    event_type: str
    snapshot_id: str | None
    review_status: str | None
    reason_code: str | None
    note: str
    review_version: int | None
    event_at: str


class FindingHistoryResponse(_StrictModel):
    items: list[FindingEventResponse]
    total: int
    page: int
    page_size: int


class FindingRuleResponse(_StrictModel):
    rule_id: str
    rule_version: str
    family: str
    title: str
    experimental: bool
    thresholds: dict[str, int]


class FindingRulesResponse(_StrictModel):
    rules: list[FindingRuleResponse]


class ComparisonSnapshotResponse(SnapshotResponse):
    observed_state_known: bool
    branch: str | None
    git_sha: str | None
    dirty: bool | None
    staged: bool | None
    untracked: bool | None
    lifecycle_reconciled: bool
    reconciliation_skip_reason: str | None


class ComparisonSnapshotListResponse(_StrictModel):
    repository: RepositoryResponse
    snapshots: list[ComparisonSnapshotResponse]


class ComparisonIdentityResponse(_StrictModel):
    comparison_id: str
    repository_id: str
    baseline_snapshot_id: str
    target_snapshot_id: str
    comparison_format_version: str


class ComparisonSectionCompatibilityResponse(_StrictModel):
    section: Literal["files", "symbols", "relationships", "cycles", "metrics", "findings"]
    status: Literal["supported", "partial", "unavailable"]
    reason_codes: list[str]


class ComparisonCompatibilityResponse(_StrictModel):
    same_repository: bool
    baseline_analyzer_version: str
    target_analyzer_version: str
    baseline_schema_version: str
    target_schema_version: str
    baseline_rule_set_version: str
    target_rule_set_version: str
    baseline_truncated: bool
    target_truncated: bool
    baseline_parse_gap_count: int
    target_parse_gap_count: int
    baseline_lifecycle_reconciled: bool
    target_lifecycle_reconciled: bool
    baseline_reconciliation_skip_reason: str | None
    target_reconciliation_skip_reason: str | None
    sections: list[ComparisonSectionCompatibilityResponse]


class ComparisonSummaryResponse(_StrictModel):
    identity: ComparisonIdentityResponse
    compatibility: ComparisonCompatibilityResponse
    counts: dict[str, int]
    equal_snapshots: bool


class CurrentFindingStateResponse(_StrictModel):
    evidence_state: Literal["active", "resolved"]
    review_status: Literal["new", "reviewed", "needs-action", "accepted", "dismissed"]
    severity: Literal["high", "medium", "low"]
    confidence: Literal["high", "medium", "low"]


class ComparisonItemResponse(_StrictModel):
    delta_id: str
    change_type: Literal[
        "added",
        "removed",
        "not-observed-in-baseline",
        "not-observed-in-target",
        "changed",
    ]
    logical_key: str
    label: str
    relative_path: str | None = None
    baseline: dict[str, Any] | None = None
    target: dict[str, Any] | None = None
    relationship_type: str | None = None
    source: str | None = None
    target_name: str | None = None
    members: list[str] | None = None
    baseline_cycle_id: str | None = None
    target_cycle_id: str | None = None
    subject: str | None = None
    metric_name: str | None = None
    unit: str | None = None
    baseline_value: float | None = None
    target_value: float | None = None
    absolute_delta: float | None = None
    direction: str | None = None
    percentage_delta: float | None = None
    rule_id: str | None = None
    subject_keys: list[str] | None = None
    baseline_finding_id: str | None = None
    target_finding_id: str | None = None
    baseline_rule_version: str | None = None
    target_rule_version: str | None = None
    occurrence_state: str | None = None
    current_state: CurrentFindingStateResponse | None = None


class ComparisonPageResponse(_StrictModel):
    comparison_id: str
    section: Literal["files", "symbols", "relationships", "cycles", "metrics", "findings"]
    section_status: Literal["supported", "partial", "unavailable"]
    reason_codes: list[str]
    items: list[ComparisonItemResponse]
    total: int
    page: int
    page_size: int
    truncated: bool


class ComparisonSummaryQuery(_StrictModel):
    baseline_snapshot_id: str = Field(min_length=1, max_length=128)
    target_snapshot_id: str = Field(min_length=1, max_length=128)


class ComparisonItemsQuery(ComparisonSummaryQuery):
    section: Literal["files", "symbols", "relationships", "cycles", "metrics", "findings"]
    change_type: (
        Literal[
            "added",
            "removed",
            "not-observed-in-baseline",
            "not-observed-in-target",
            "changed",
        ]
        | None
    ) = None
    search: str = Field(default="", max_length=200)
    sort: Literal["logical_key", "label", "change_type"] = "logical_key"
    direction: Literal["asc", "desc"] = "asc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


HandoffSelectionId = Annotated[str, Field(min_length=1, max_length=128)]


class HandoffSelectionRequest(_StrictModel):
    target_snapshot_id: str = Field(min_length=1, max_length=128)
    baseline_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    comparison_id: str | None = Field(default=None, min_length=1, max_length=128)
    enabled_sections: list[
        Literal[
            "comparison",
            "files",
            "symbols",
            "relationships",
            "cycles",
            "metrics",
            "findings",
            "task-objective",
        ]
    ] = Field(max_length=8)
    selected_delta_ids: list[HandoffSelectionId] = Field(default_factory=list, max_length=400)
    selected_finding_ids: list[HandoffSelectionId] = Field(default_factory=list, max_length=200)
    selected_cycle_ids: list[HandoffSelectionId] = Field(default_factory=list, max_length=100)
    include_current_review_status: bool = False
    explicit_review_note_finding_ids: list[HandoffSelectionId] = Field(
        default_factory=list,
        max_length=20,
    )
    task_objective: str = Field(default="", max_length=4_000)


class HandoffPreviewResponse(_StrictModel):
    handoff_format_version: str
    markdown: str
    normalized_json: str
    json_payload: dict[str, Any]
    rendered_digest: str
    truncated: bool
    omitted_counts: dict[str, int]
    warnings: list[str]
    markdown_character_count: int
    json_byte_count: int


class SavedHandoffResponse(_StrictModel):
    handoff_id: str
    repository_id: str
    target_snapshot_id: str
    baseline_snapshot_id: str | None
    comparison_id: str | None
    selection: dict[str, Any]
    task_objective: str
    format_version: str
    rendered_digest: str
    markdown_character_count: int
    json_byte_count: int
    created_at: str
    updated_at: str
    local_only: bool
    markdown: str | None = None
    normalized_json: str | None = None
    json_payload: dict[str, Any] | None = None


class SavedHandoffListResponse(_StrictModel):
    items: list[SavedHandoffResponse]


class HealthResponse(_StrictModel):
    status: Literal["ok"]
    service: Literal["repository-review"]
    schema_version: Literal["4"]


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
        return {"status": "ok", "service": "repository-review", "schema_version": "4"}

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

    @app.get(
        "/api/repositories/{repository_id}/comparison-snapshots",
        response_model=ComparisonSnapshotListResponse,
    )
    def comparison_snapshots(repository_id: str) -> dict[str, object]:
        try:
            return review_service.comparison_snapshots(repository_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Repository was not found.") from exc

    @app.get("/api/comparisons/summary", response_model=ComparisonSummaryResponse)
    def comparison_summary(
        query: Annotated[ComparisonSummaryQuery, Query()],
    ) -> dict[str, object]:
        try:
            return review_service.comparison_summary(
                query.baseline_snapshot_id,
                query.target_snapshot_id,
            )
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Snapshot was not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Comparison is invalid.") from exc

    @app.get("/api/comparisons/items", response_model=ComparisonPageResponse)
    def comparison_items(
        query: Annotated[ComparisonItemsQuery, Query()],
    ) -> dict[str, object]:
        try:
            return review_service.comparison_items(
                query.baseline_snapshot_id,
                query.target_snapshot_id,
                section=query.section,
                change_type=query.change_type,
                search=query.search,
                sort=query.sort,
                direction=query.direction,
                page=query.page,
                page_size=query.page_size,
            )
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Snapshot was not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Comparison query is invalid.") from exc

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
        "/api/snapshots/{snapshot_id}/relationships/nodes",
        response_model=GraphNodePageResponse,
    )
    def relationship_nodes(
        snapshot_id: str,
        mode: Literal["modules", "packages", "inheritance", "containment", "types"] = "modules",
        search: Annotated[str, Query(max_length=200)] = "",
        node_ids: Annotated[list[str] | None, Query()] = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 100,
    ) -> dict[str, object]:
        try:
            return review_service.relationship_nodes(
                snapshot_id,
                mode=mode,
                search=search,
                node_ids=tuple(node_ids or ()),
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

    @app.get(
        "/api/snapshots/{snapshot_id}/findings/summary",
        response_model=FindingSummaryResponse,
    )
    def finding_summary(snapshot_id: str) -> dict[str, object]:
        try:
            return review_service.finding_summary(snapshot_id)
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Snapshot was not found.") from exc

    @app.get(
        "/api/snapshots/{snapshot_id}/findings",
        response_model=FindingPageResponse,
    )
    def findings(
        snapshot_id: str,
        family: Annotated[str | None, Query(max_length=64)] = None,
        severity: Literal["high", "medium", "low"] | None = None,
        confidence: Literal["high", "medium", "low"] | None = None,
        effective_status: Literal["new", "reviewed", "needs-action", "accepted", "dismissed", "resolved"]
        | None = None,
        evidence_state: Literal["active", "resolved"] | None = None,
        search: Annotated[str, Query(max_length=200)] = "",
        sort: Literal[
            "severity",
            "family",
            "status",
            "first_seen",
            "last_seen",
            "qualified_subject",
            "finding_id",
        ] = "severity",
        direction: Literal["asc", "desc"] = "desc",
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> dict[str, object]:
        try:
            return review_service.findings(
                snapshot_id,
                family=family,
                severity=severity,
                confidence=confidence,
                effective_status=effective_status,
                evidence_state=evidence_state,
                search=search,
                sort=sort,
                direction=direction,
                page=page,
                page_size=page_size,
            )
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Snapshot was not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Finding query is invalid.") from exc

    @app.get("/api/findings/{finding_id}", response_model=FindingResponse)
    def finding_detail(
        finding_id: str,
        snapshot_id: Annotated[str | None, Query(min_length=16, max_length=128)] = None,
    ) -> dict[str, object]:
        try:
            return review_service.finding_detail(finding_id, snapshot_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Finding was not found.") from exc

    @app.get(
        "/api/findings/{finding_id}/history",
        response_model=FindingHistoryResponse,
    )
    def finding_history(
        finding_id: str,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> dict[str, object]:
        try:
            return review_service.finding_history(
                finding_id,
                page=page,
                page_size=page_size,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Finding history query is invalid.") from exc

    @app.patch("/api/findings/{finding_id}/review", response_model=FindingResponse)
    def update_finding_review(
        finding_id: str,
        request: FindingReviewRequest,
    ) -> Any:
        try:
            return review_service.update_finding_review(
                finding_id,
                expected_version=request.expected_version,
                review_status=request.review_status,
                note=request.note,
                reason_code=request.reason_code,
            )
        except ReviewConflictError as exc:
            return JSONResponse(
                status_code=409,
                content={
                    "detail": "Finding review version conflict.",
                    "current": public_finding(exc.current),
                },
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Finding was not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Finding review is invalid.") from exc

    @app.get("/api/finding-rules", response_model=FindingRulesResponse)
    def finding_rule_catalog() -> dict[str, object]:
        return {"rules": list(review_service.finding_rules())}

    @app.post("/api/handoffs/preview", response_model=HandoffPreviewResponse)
    def preview_handoff(request: HandoffSelectionRequest) -> dict[str, object]:
        try:
            return review_service.preview_handoff(_handoff_selection(request))
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Snapshot was not found.") from exc
        except HandoffBudgetError as exc:
            raise HTTPException(status_code=400, detail=HANDOFF_BUDGET_ERROR_MESSAGE) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Handoff selection is invalid.") from exc

    @app.post("/api/handoffs", response_model=SavedHandoffResponse, status_code=201)
    def save_handoff(request: HandoffSelectionRequest) -> dict[str, object]:
        try:
            return review_service.save_handoff(_handoff_selection(request))
        except SnapshotNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Snapshot was not found.") from exc
        except HandoffBudgetError as exc:
            raise HTTPException(status_code=400, detail=HANDOFF_BUDGET_ERROR_MESSAGE) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Handoff selection is invalid.") from exc

    @app.get("/api/handoffs", response_model=SavedHandoffListResponse)
    def saved_handoffs(
        repository_id: Annotated[str | None, Query(min_length=16, max_length=128)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ) -> dict[str, object]:
        try:
            return review_service.list_handoffs(
                repository_id=repository_id,
                limit=limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Handoff query is invalid.") from exc

    @app.get("/api/handoffs/{handoff_id}", response_model=SavedHandoffResponse)
    def saved_handoff(handoff_id: str) -> dict[str, object]:
        try:
            return review_service.get_handoff(handoff_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Saved handoff was not found.") from exc
        except SavedHandoffIntegrityError as exc:
            raise HTTPException(
                status_code=409,
                detail="Saved handoff failed integrity validation.",
            ) from exc

    @app.get("/api/handoffs/{handoff_id}/markdown")
    def saved_handoff_markdown(handoff_id: str) -> Response:
        try:
            content = review_service.handoff_markdown(handoff_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Saved handoff was not found.") from exc
        except SavedHandoffIntegrityError as exc:
            raise HTTPException(
                status_code=409,
                detail="Saved handoff failed integrity validation.",
            ) from exc
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": (f'attachment; filename="{_download_name(handoff_id, "md")}"')},
        )

    @app.get("/api/handoffs/{handoff_id}/json")
    def saved_handoff_json(handoff_id: str) -> Response:
        try:
            content = review_service.handoff_json(handoff_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Saved handoff was not found.") from exc
        except SavedHandoffIntegrityError as exc:
            raise HTTPException(
                status_code=409,
                detail="Saved handoff failed integrity validation.",
            ) from exc
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": (f'attachment; filename="{_download_name(handoff_id, "json")}"')},
        )

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


def _handoff_selection(request: HandoffSelectionRequest) -> HandoffSelection:
    return HandoffSelection(
        target_snapshot_id=request.target_snapshot_id,
        baseline_snapshot_id=request.baseline_snapshot_id,
        comparison_id=request.comparison_id,
        enabled_sections=tuple(request.enabled_sections),
        selected_delta_ids=tuple(request.selected_delta_ids),
        selected_finding_ids=tuple(request.selected_finding_ids),
        selected_cycle_ids=tuple(request.selected_cycle_ids),
        include_current_review_status=request.include_current_review_status,
        explicit_review_note_finding_ids=tuple(request.explicit_review_note_finding_ids),
        task_objective=request.task_objective,
        budget_policy=DEFAULT_HANDOFF_BUDGET,
    )


def _download_name(handoff_id: str, extension: str) -> str:
    safe_id = "".join(
        character
        for character in handoff_id
        if character.isascii() and (character.isalnum() or character in {"-", "_"})
    )[:80]
    return f"repository-handoff-{safe_id or 'local'}.{extension}"


__all__ = [
    "LOCALHOST",
    "create_workspace_app",
    "run_workspace",
    "validate_workspace_host",
]
