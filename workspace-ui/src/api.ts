import type {
    AnalysisJob,
    Overview,
    CycleList,
    GraphMode,
    GraphNodePage,
    RelationshipNeighborhood,
    RelationshipSummary,
    Repository,
    Snapshot,
    SourceEvidence,
    SymbolPage,
} from "./types";

export class ApiError extends Error {
    constructor(message: string) {
        super(message);
        this.name = "ApiError";
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
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new ApiError(payload?.detail ?? "The local workspace request failed.");
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
