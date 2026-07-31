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
export type FindingQueuePreset = "all" | "high-signal-v1";
export type FindingFamily =
    | "dependency-cycle"
    | "inheritance-cycle"
    | "duplicate-name-candidate"
    | "oversized"
    | "complexity"
    | "nesting"
    | "parameters"
    | "coupling"
    | "inheritance"
    | "documentation"
    | "test-evidence-candidate"
    | "orphan-candidate";

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
    families: Record<FindingFamily, number>;
    low_confidence: number;
    reconciliation_complete: boolean;
    lifecycle_reconciled: boolean;
    reconciliation_skip_reason: string | null;
}

export interface FindingPage {
    supported: boolean;
    preset: FindingQueuePreset;
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

export interface ComparisonSnapshot extends Snapshot {
    observed_state_known: boolean;
    branch: string | null;
    git_sha: string | null;
    dirty: boolean | null;
    staged: boolean | null;
    untracked: boolean | null;
    lifecycle_reconciled: boolean;
    reconciliation_skip_reason: string | null;
}

export type ComparisonSection =
    "files" | "symbols" | "relationships" | "cycles" | "metrics" | "findings";

export type ComparisonChangeType =
    "added" | "removed" | "not-observed-in-baseline" | "not-observed-in-target" | "changed";

export interface ComparisonSectionCompatibility {
    section: ComparisonSection;
    status: "supported" | "partial" | "unavailable";
    reason_codes: string[];
}

export interface ComparisonSummary {
    identity: {
        comparison_id: string;
        repository_id: string;
        baseline_snapshot_id: string;
        target_snapshot_id: string;
        comparison_format_version: string;
    };
    compatibility: {
        same_repository: boolean;
        baseline_analyzer_version: string;
        target_analyzer_version: string;
        baseline_schema_version: string;
        target_schema_version: string;
        baseline_rule_set_version: string;
        target_rule_set_version: string;
        baseline_truncated: boolean;
        target_truncated: boolean;
        baseline_parse_gap_count: number;
        target_parse_gap_count: number;
        baseline_lifecycle_reconciled: boolean;
        target_lifecycle_reconciled: boolean;
        baseline_reconciliation_skip_reason: string | null;
        target_reconciliation_skip_reason: string | null;
        sections: ComparisonSectionCompatibility[];
    };
    counts: Record<string, number>;
    equal_snapshots: boolean;
}

export interface ComparisonItem {
    delta_id: string;
    change_type: ComparisonChangeType;
    logical_key: string;
    label: string;
    relative_path: string | null;
    baseline?: Record<string, unknown> | null;
    target?: Record<string, unknown> | null;
    relationship_type?: string | null;
    source?: string | null;
    target_name?: string | null;
    members?: string[] | null;
    baseline_cycle_id?: string | null;
    target_cycle_id?: string | null;
    subject?: string | null;
    metric_name?: string | null;
    unit?: string | null;
    baseline_value?: number | null;
    target_value?: number | null;
    absolute_delta?: number | null;
    direction?: string | null;
    percentage_delta?: number | null;
    rule_id?: string | null;
    subject_keys?: string[] | null;
    baseline_finding_id?: string | null;
    target_finding_id?: string | null;
    baseline_rule_version?: string | null;
    target_rule_version?: string | null;
    occurrence_state?: string | null;
    current_state?: {
        evidence_state: "active" | "resolved";
        review_status: ReviewStatus;
        severity: "high" | "medium" | "low";
        confidence: "high" | "medium" | "low";
    } | null;
}

export interface ComparisonPage {
    comparison_id: string;
    section: ComparisonSection;
    section_status: "supported" | "partial" | "unavailable";
    reason_codes: string[];
    items: ComparisonItem[];
    total: number;
    page: number;
    page_size: number;
    truncated: boolean;
}

export interface HandoffSelectionRequest {
    target_snapshot_id: string;
    baseline_snapshot_id: string | null;
    comparison_id: string | null;
    enabled_sections: string[];
    selected_delta_ids: string[];
    selected_finding_ids: string[];
    selected_cycle_ids: string[];
    include_current_review_status: boolean;
    explicit_review_note_finding_ids: string[];
    task_objective: string;
}

export interface HandoffPreview {
    handoff_format_version: string;
    markdown: string;
    normalized_json: string;
    json_payload: Record<string, unknown>;
    rendered_digest: string;
    truncated: boolean;
    omitted_counts: Record<string, number>;
    warnings: string[];
    markdown_character_count: number;
    json_byte_count: number;
}

export interface SavedHandoff {
    handoff_id: string;
    repository_id: string;
    target_snapshot_id: string;
    baseline_snapshot_id: string | null;
    comparison_id: string | null;
    selection: HandoffSelectionRequest;
    task_objective: string;
    format_version: string;
    rendered_digest: string;
    markdown_character_count: number;
    json_byte_count: number;
    created_at: string;
    updated_at: string;
    local_only: boolean;
    markdown?: string | null;
    normalized_json?: string | null;
    json_payload?: Record<string, unknown> | null;
}

export type ViewName =
    "overview" | "symbols" | "relationships" | "findings" | "compare" | "handoff";
