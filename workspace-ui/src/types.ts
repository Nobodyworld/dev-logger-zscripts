export type AnalysisState = "started" | "completed" | "cancelled" | "failed";

export interface Repository {
    repository_id: string;
    display_name: string;
    branch: string | null;
    git_sha: string | null;
    dirty: boolean;
    staged: boolean;
    untracked: boolean;
    configuration_digest: string;
    source_roots: string[];
    test_roots: string[];
}

export interface Snapshot {
    snapshot_id: string;
    repository_id: string;
    analyzer_version: string;
    schema_version: string;
    rule_set_version: string;
    state: "completed";
    source_fingerprint: string;
    file_count: number;
    included_file_count: number;
    module_count: number;
    symbol_count: number;
    started_at: string;
    completed_at: string | null;
    duration_ms: number;
    truncated: boolean;
    parse_gap_count: number;
}

export interface Overview {
    repository: Repository;
    snapshot: Snapshot;
    counts: {
        files_analyzed: number;
        files_excluded: number;
        packages: number;
        modules: number;
        classes: number;
        functions: number;
        methods: number;
        parse_gaps: number;
        relationship_analysis_supported: boolean;
        resolved_import_edges: number;
        inheritance_edges: number;
        cycle_groups: number;
        largest_cycle_size: number;
        active_findings: number;
        needs_action_findings: number;
        resolved_since_last_scan: number;
        high_confidence_high_severity_findings: number;
    };
}

export interface AnalysisJob {
    analysis_id: string;
    state: AnalysisState;
    phase: string;
    completed: number;
    total: number;
    current_file: string;
    repository_id: string | null;
    snapshot_id: string | null;
    message: string | null;
}

export interface SymbolRecord {
    symbol_id: string;
    language: string;
    kind: string;
    qualified_name: string;
    display_name: string;
    module_name: string;
    relative_path: string;
    start_line: number;
    start_column: number;
    end_line: number;
    end_column: number;
    parent_symbol_id: string | null;
    visibility: string;
    signature: string;
    annotations: string[];
    decorators: string[];
    docstring_present: boolean;
    async_flag: boolean;
    content_fingerprint: string;
    bases: string[];
}

export interface SymbolPage {
    items: SymbolRecord[];
    total: number;
    page: number;
    page_size: number;
    filters: {
        kinds: string[];
        modules: string[];
        visibilities: string[];
    };
}

export interface SourceEvidence {
    relative_path: string;
    start_line: number;
    end_line: number;
    lines: Array<{ number: number; text: string }>;
    truncated: boolean;
    content_hash: string;
}

export type GraphMode = "modules" | "packages" | "inheritance" | "containment" | "types";

export interface GraphNode {
    node_id: string;
    node_type: "package" | "module" | "symbol";
    display_name: string;
    qualified_name: string;
    relative_path: string | null;
    symbol_kind: string | null;
}

export interface Relationship {
    relationship_id: string;
    relationship_type: "contains" | "imports" | "inherits" | "references-type";
    source_id: string;
    target_id: string | null;
    unresolved_target: string | null;
    resolution_status: "resolved-static" | "probable-static" | "ambiguous" | "unresolved-dynamic";
    confidence: "high" | "medium" | "low";
    relative_path: string;
    line: number;
    column: number;
    analyzer_version: string;
    evidence: string;
}

export interface RelationshipSummary {
    supported: boolean;
    analyzer_version: string;
    schema_version: string;
    node_count: number;
    relationship_count: number;
    cycle_count: number;
    largest_cycle_size: number;
    truncated: boolean;
    nodes: GraphNode[];
    relationship_types: Record<string, number>;
    resolution_statuses: Record<string, number>;
    fan_in: Record<string, number>;
    fan_out: Record<string, number>;
    inheritance_depth: Record<string, number | null>;
}

export interface GraphNodePage {
    supported: boolean;
    items: GraphNode[];
    total: number;
    page: number;
    page_size: number;
    truncated: boolean;
}

export interface RelationshipNeighborhood {
    supported: boolean;
    focus_id: string;
    mode: GraphMode;
    depth: number;
    nodes: GraphNode[];
    relationships: Relationship[];
    distances: Record<string, number>;
    truncated: boolean;
}

export interface CycleGroup {
    cycle_id: string;
    relationship_type: "imports" | "inherits";
    member_node_ids: string[];
    edge_ids: string[];
}

export interface CycleList {
    supported: boolean;
    items: CycleGroup[];
    truncated: boolean;
}

export type ReviewStatus = "new" | "reviewed" | "needs-action" | "accepted" | "dismissed";

export interface Finding {
    finding_id: string;
    rule_id: string;
    rule_version: string;
    family: string;
    title: string;
    explanation: string;
    suggested_action: string;
    severity: "high" | "medium" | "low";
    confidence: "high" | "medium" | "low";
    subject_type: string;
    subject_keys: string[];
    affected_node_ids: string[];
    relative_path: string | null;
    line: number | null;
    metric_evidence: Array<[string, number]>;
    threshold_evidence: Array<[string, number]>;
    repository_id: string;
    first_seen_snapshot_id: string;
    last_seen_snapshot_id: string;
    evidence_state: "active" | "resolved";
    resolved_snapshot_id: string | null;
    review_status: ReviewStatus;
    effective_status: ReviewStatus | "resolved";
    note: string;
    reason_code: string | null;
    review_version: number;
    decided_at: string;
    updated_at: string;
}

export interface FindingSummary {
    supported: boolean;
    active: number;
    resolved: number;
    needs_action: number;
    accepted: number;
    dismissed: number;
    severity: Record<string, number>;
    low_confidence: number;
    reconciliation_complete: boolean;
    lifecycle_reconciled: boolean;
    reconciliation_skip_reason: string | null;
}

export interface FindingPage {
    supported: boolean;
    items: Finding[];
    total: number;
    page: number;
    page_size: number;
}

export interface FindingHistory {
    items: Array<{
        event_id: number;
        finding_id: string;
        event_type: string;
        snapshot_id: string | null;
        review_status: string | null;
        reason_code: string | null;
        note: string;
        review_version: number | null;
        event_at: string;
    }>;
    total: number;
    page: number;
    page_size: number;
}

export type ViewName = "overview" | "symbols" | "relationships" | "findings";
