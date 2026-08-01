import type {
    AnalysisJob,
    Overview,
    CycleList,
    Finding,
    FindingQueuePreset,
    FindingHistory,
    FindingPage,
    FindingSummary,
    ComparisonPage,
    ComparisonSection,
    ComparisonSnapshot,
    ComparisonSummary,
    GraphMode,
    GraphNodePage,
    RelationshipNeighborhood,
    RelationshipSummary,
    Repository,
    HandoffPreview,
    HandoffSelectionRequest,
    SavedHandoff,
    Snapshot,
    SnapshotEvidenceStatus,
    EvidenceStatusSurface,
    SourceEvidence,
    SymbolPage,
} from "./types";

export class ApiError extends Error {
    status: number;
    currentFinding: Finding | null;

    constructor(message: string, status = 0, currentFinding: Finding | null = null) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.currentFinding = currentFinding;
    }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, {
        ...init,
        headers: {
            "Content-Type": "application/json",
            ...init?.headers,
        },
    });
    if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as {
            detail?: string;
            current?: Finding;
        } | null;
        throw new ApiError(
            payload?.detail ?? "The local workspace request failed.",
            response.status,
            payload?.current ?? null,
        );
    }
    return (await response.json()) as T;
}

export async function listRepositories(): Promise<Repository[]> {
    const payload = await request<{ repositories: Repository[] }>("/api/repositories");
    return payload.repositories;
}

export async function startAnalysis(input: {
    repository_path?: string;
    repository_id?: string;
}): Promise<AnalysisJob> {
    return request<AnalysisJob>("/api/repositories/analyze", {
        method: "POST",
        body: JSON.stringify(input),
    });
}

export function getAnalysis(analysisId: string): Promise<AnalysisJob> {
    return request<AnalysisJob>(`/api/analyses/${encodeURIComponent(analysisId)}`);
}

export function cancelAnalysis(analysisId: string): Promise<AnalysisJob> {
    return request<AnalysisJob>(`/api/analyses/${encodeURIComponent(analysisId)}/cancel`, {
        method: "POST",
    });
}

export async function listSnapshots(repositoryId: string): Promise<Snapshot[]> {
    const payload = await request<{ snapshots: Snapshot[] }>(
        `/api/repositories/${encodeURIComponent(repositoryId)}/snapshots`,
    );
    return payload.snapshots;
}

export function getOverview(snapshotId: string): Promise<Overview> {
    return request<Overview>(`/api/snapshots/${encodeURIComponent(snapshotId)}/overview`);
}

export function getSnapshotEvidenceStatus(
    snapshotId: string,
    surface: EvidenceStatusSurface = "generic",
    signal?: AbortSignal,
): Promise<SnapshotEvidenceStatus> {
    const parameters = new URLSearchParams({ surface });
    return request<SnapshotEvidenceStatus>(
        `/api/snapshots/${encodeURIComponent(snapshotId)}/evidence-status?${parameters.toString()}`,
        { signal },
    );
}

export interface SymbolQuery {
    search: string;
    kind: string;
    module: string;
    visibility: string;
    sort: string;
    direction: "asc" | "desc";
    page: number;
    pageSize: number;
}

export function getSymbols(snapshotId: string, query: SymbolQuery): Promise<SymbolPage> {
    const parameters = new URLSearchParams({
        search: query.search,
        sort: query.sort,
        direction: query.direction,
        page: String(query.page),
        page_size: String(query.pageSize),
    });
    if (query.kind) parameters.set("kind", query.kind);
    if (query.module) parameters.set("module", query.module);
    if (query.visibility) parameters.set("visibility", query.visibility);
    return request<SymbolPage>(
        `/api/snapshots/${encodeURIComponent(snapshotId)}/symbols?${parameters.toString()}`,
    );
}

export function getSource(
    snapshotId: string,
    path: string,
    startLine: number,
    endLine: number,
): Promise<SourceEvidence> {
    const parameters = new URLSearchParams({
        path,
        start_line: String(startLine),
        end_line: String(endLine),
    });
    return request<SourceEvidence>(
        `/api/snapshots/${encodeURIComponent(snapshotId)}/source?${parameters.toString()}`,
    );
}

export function getRelationshipSummary(
    snapshotId: string,
    maxNodes = 200,
): Promise<RelationshipSummary> {
    const parameters = new URLSearchParams({ max_nodes: String(maxNodes) });
    return request<RelationshipSummary>(
        `/api/snapshots/${encodeURIComponent(snapshotId)}/relationships/summary?${parameters.toString()}`,
    );
}

export function getRelationshipNodes(
    snapshotId: string,
    query: {
        mode: GraphMode;
        search?: string;
        page?: number;
        pageSize?: number;
        nodeIds?: string[];
    },
): Promise<GraphNodePage> {
    const parameters = new URLSearchParams({
        mode: query.mode,
        page: String(query.page ?? 1),
        page_size: String(query.pageSize ?? 100),
    });
    if (query.search) parameters.set("search", query.search);
    for (const nodeId of query.nodeIds ?? []) parameters.append("node_ids", nodeId);
    return request<GraphNodePage>(
        `/api/snapshots/${encodeURIComponent(snapshotId)}/relationships/nodes?${parameters.toString()}`,
    );
}

export function getRelationshipNeighborhood(
    snapshotId: string,
    query: {
        focusId: string;
        mode: GraphMode;
        depth: number;
        relationshipType: string;
        resolutionStatus: string;
        maxNodes: number;
        maxEdges: number;
    },
): Promise<RelationshipNeighborhood> {
    const parameters = new URLSearchParams({
        focus_id: query.focusId,
        mode: query.mode,
        depth: String(query.depth),
        max_nodes: String(query.maxNodes),
        max_edges: String(query.maxEdges),
    });
    if (query.relationshipType) {
        parameters.set("relationship_type", query.relationshipType);
    }
    if (query.resolutionStatus) {
        parameters.set("resolution_status", query.resolutionStatus);
    }
    return request<RelationshipNeighborhood>(
        `/api/snapshots/${encodeURIComponent(snapshotId)}/relationships/neighborhood?${parameters.toString()}`,
    );
}

export function getCycles(snapshotId: string): Promise<CycleList> {
    return request<CycleList>(
        `/api/snapshots/${encodeURIComponent(snapshotId)}/cycles?max_results=100`,
    );
}

export function getFindingSummary(snapshotId: string): Promise<FindingSummary> {
    return request<FindingSummary>(
        `/api/snapshots/${encodeURIComponent(snapshotId)}/findings/summary`,
    );
}

export interface FindingQuery {
    preset?: FindingQueuePreset;
    search: string;
    family: string;
    severity: string;
    confidence: string;
    effectiveStatus: string;
    evidenceState: string;
    sort: string;
    direction: "asc" | "desc";
    page: number;
    pageSize: number;
}

export function getFindings(
    snapshotId: string,
    query: FindingQuery,
    signal?: AbortSignal,
): Promise<FindingPage> {
    const parameters = new URLSearchParams({
        search: query.search,
        sort: query.sort,
        direction: query.direction,
        page: String(query.page),
        page_size: String(query.pageSize),
    });
    if (query.preset) parameters.set("preset", query.preset);
    if (query.family) parameters.set("family", query.family);
    if (query.severity) parameters.set("severity", query.severity);
    if (query.confidence) parameters.set("confidence", query.confidence);
    if (query.effectiveStatus) parameters.set("effective_status", query.effectiveStatus);
    if (query.evidenceState) parameters.set("evidence_state", query.evidenceState);
    return request<FindingPage>(
        `/api/snapshots/${encodeURIComponent(snapshotId)}/findings?${parameters.toString()}`,
        { signal },
    );
}

export async function getComparisonSnapshots(
    repositoryId: string,
    signal?: AbortSignal,
): Promise<{ repository: Repository; snapshots: ComparisonSnapshot[] }> {
    return request<{ repository: Repository; snapshots: ComparisonSnapshot[] }>(
        `/api/repositories/${encodeURIComponent(repositoryId)}/comparison-snapshots`,
        { signal },
    );
}

export function getComparisonSummary(
    baselineSnapshotId: string,
    targetSnapshotId: string,
    signal?: AbortSignal,
): Promise<ComparisonSummary> {
    const parameters = new URLSearchParams({
        baseline_snapshot_id: baselineSnapshotId,
        target_snapshot_id: targetSnapshotId,
    });
    return request<ComparisonSummary>(`/api/comparisons/summary?${parameters.toString()}`, {
        signal,
    });
}

export function getComparisonItems(
    query: {
        baselineSnapshotId: string;
        targetSnapshotId: string;
        section: ComparisonSection;
        changeType: string;
        search: string;
        sort: "logical_key" | "label" | "change_type";
        direction: "asc" | "desc";
        page: number;
        pageSize: number;
    },
    signal?: AbortSignal,
): Promise<ComparisonPage> {
    const parameters = new URLSearchParams({
        baseline_snapshot_id: query.baselineSnapshotId,
        target_snapshot_id: query.targetSnapshotId,
        section: query.section,
        search: query.search,
        sort: query.sort,
        direction: query.direction,
        page: String(query.page),
        page_size: String(query.pageSize),
    });
    if (query.changeType) parameters.set("change_type", query.changeType);
    return request<ComparisonPage>(`/api/comparisons/items?${parameters.toString()}`, {
        signal,
    });
}

export function previewHandoff(
    selection: HandoffSelectionRequest,
    signal?: AbortSignal,
): Promise<HandoffPreview> {
    return request<HandoffPreview>("/api/handoffs/preview", {
        method: "POST",
        signal,
        body: JSON.stringify(selection),
    });
}

export function saveHandoff(
    selection: HandoffSelectionRequest,
    signal?: AbortSignal,
): Promise<SavedHandoff> {
    return request<SavedHandoff>("/api/handoffs", {
        method: "POST",
        signal,
        body: JSON.stringify(selection),
    });
}

export async function listHandoffs(
    repositoryId: string,
    signal?: AbortSignal,
): Promise<SavedHandoff[]> {
    const parameters = new URLSearchParams({ repository_id: repositoryId, limit: "100" });
    const payload = await request<{ items: SavedHandoff[] }>(
        `/api/handoffs?${parameters.toString()}`,
        { signal },
    );
    return payload.items;
}

export function getSavedHandoff(handoffId: string, signal?: AbortSignal): Promise<SavedHandoff> {
    return request<SavedHandoff>(`/api/handoffs/${encodeURIComponent(handoffId)}`, {
        signal,
    });
}

export function getFinding(
    findingId: string,
    snapshotId: string,
    signal?: AbortSignal,
): Promise<Finding> {
    const parameters = new URLSearchParams({ snapshot_id: snapshotId });
    return request<Finding>(
        `/api/findings/${encodeURIComponent(findingId)}?${parameters.toString()}`,
        { signal },
    );
}

export function getFindingHistory(
    findingId: string,
    signal?: AbortSignal,
): Promise<FindingHistory> {
    return request<FindingHistory>(
        `/api/findings/${encodeURIComponent(findingId)}/history?page=1&page_size=50`,
        { signal },
    );
}

export function updateFindingReview(
    findingId: string,
    input: {
        expectedVersion: number;
        reviewStatus: string;
        note: string;
        reasonCode: string;
    },
    signal?: AbortSignal,
): Promise<Finding> {
    return request<Finding>(`/api/findings/${encodeURIComponent(findingId)}/review`, {
        method: "PATCH",
        signal,
        body: JSON.stringify({
            expected_version: input.expectedVersion,
            review_status: input.reviewStatus,
            note: input.note,
            reason_code: input.reasonCode || null,
        }),
    });
}
