import type {
    CycleGroup,
    Finding,
    FindingHistory,
    FindingSummary,
    GraphNode,
    GraphNodePage,
    Overview,
    Relationship,
    RelationshipNeighborhood,
    RelationshipSummary,
    Repository,
    Snapshot,
    SymbolRecord,
} from "../types";

export const repository: Repository = {
    repository_id: "repository-0123456789abcdef", // pragma: allowlist secret
    display_name: "sample-repository",
    branch: "main",
    git_sha: "19ba55e1bbd76fab", // pragma: allowlist secret
    dirty: false,
    staged: false,
    untracked: false,
    configuration_digest: "config-0123456789abcdef",
    source_roots: ["src"],
    test_roots: ["tests"],
};

export const snapshot: Snapshot = {
    snapshot_id: "snapshot-0123456789abcdef",
    repository_id: repository.repository_id,
    analyzer_version: "2",
    schema_version: "2",
    rule_set_version: "2",
    state: "completed",
    source_fingerprint: "abcdef0123456789abcdef0123456789", // pragma: allowlist secret
    file_count: 12,
    included_file_count: 10,
    module_count: 4,
    symbol_count: 8,
    started_at: "2026-07-24T12:00:00.000Z",
    completed_at: "2026-07-24T12:00:01.000Z",
    duration_ms: 1_000,
    truncated: false,
    parse_gap_count: 1,
};

export const olderSnapshot: Snapshot = {
    ...snapshot,
    snapshot_id: "snapshot-fedcba9876543210",
    completed_at: "2026-07-23T12:00:01.000Z",
};

export const overview: Overview = {
    repository,
    snapshot,
    counts: {
        files_analyzed: 10,
        files_excluded: 2,
        packages: 2,
        modules: 4,
        classes: 2,
        functions: 3,
        methods: 3,
        parse_gaps: 1,
        relationship_analysis_supported: true,
        resolved_import_edges: 3,
        inheritance_edges: 1,
        cycle_groups: 1,
        largest_cycle_size: 2,
        active_findings: 4,
        needs_action_findings: 1,
        resolved_since_last_scan: 0,
        high_confidence_high_severity_findings: 1,
    },
};

export const symbol: SymbolRecord = {
    symbol_id: "symbol-0123456789abcdef",
    language: "python",
    kind: "method",
    qualified_name: "<img src=x onerror=alert(1)>",
    display_name: "analyze",
    module_name: "zscripts.application.repository_review",
    relative_path: "zscripts/application/repository_review.py",
    start_line: 42,
    start_column: 4,
    end_line: 48,
    end_column: 20,
    parent_symbol_id: null,
    visibility: "public",
    signature: "def analyze(path: Path) -> AnalysisEvidence",
    annotations: ["path: Path", "return: AnalysisEvidence"],
    decorators: [],
    docstring_present: true,
    async_flag: false,
    content_fingerprint: "fingerprint-0123456789abcdef",
    bases: [],
};

export const moduleA: GraphNode = {
    node_id: "node-module-a-0123456789abcdef",
    node_type: "module",
    display_name: "a",
    qualified_name: "pkg.a",
    relative_path: "pkg/a.py",
    symbol_kind: null,
};

export const moduleB: GraphNode = {
    node_id: "node-module-b-0123456789abcdef",
    node_type: "module",
    display_name: "b",
    qualified_name: "pkg.b",
    relative_path: "pkg/b.py",
    symbol_kind: null,
};

export const packageNode: GraphNode = {
    node_id: "node-package-0123456789abcdef",
    node_type: "package",
    display_name: "pkg",
    qualified_name: "pkg",
    relative_path: null,
    symbol_kind: null,
};

export const classNode: GraphNode = {
    node_id: "node-class-0123456789abcdef",
    node_type: "symbol",
    display_name: "Example",
    qualified_name: "pkg.models.Example",
    relative_path: "pkg/models.py",
    symbol_kind: "class",
};

export const importRelationship: Relationship = {
    relationship_id: "relationship-import-0123456789abcdef", // pragma: allowlist secret
    relationship_type: "imports",
    source_id: moduleA.node_id,
    target_id: moduleB.node_id,
    unresolved_target: null,
    resolution_status: "resolved-static",
    confidence: "high",
    relative_path: "pkg/a.py",
    line: 3,
    column: 0,
    analyzer_version: "2",
    evidence: "from pkg import b",
};

export const unresolvedRelationship: Relationship = {
    ...importRelationship,
    relationship_id: "relationship-unresolved-01234567",
    target_id: null,
    unresolved_target: "external.module",
    resolution_status: "unresolved-dynamic",
    confidence: "low",
    line: 4,
    evidence: "import external.module",
};

export const relationshipSummary: RelationshipSummary = {
    supported: true,
    analyzer_version: "2",
    schema_version: "2",
    node_count: 4,
    relationship_count: 2,
    cycle_count: 1,
    largest_cycle_size: 2,
    truncated: false,
    nodes: [moduleA, moduleB, packageNode, classNode],
    relationship_types: { imports: 2 },
    resolution_statuses: { "resolved-static": 1, "unresolved-dynamic": 1 },
    fan_in: { [moduleA.node_id]: 0, [moduleB.node_id]: 1 },
    fan_out: { [moduleA.node_id]: 1, [moduleB.node_id]: 0 },
    inheritance_depth: {},
};

export const relationshipNodePage: GraphNodePage = {
    supported: true,
    items: [moduleA, moduleB],
    total: 2,
    page: 1,
    page_size: 100,
    truncated: false,
};

export const relationshipNeighborhood: RelationshipNeighborhood = {
    supported: true,
    focus_id: moduleA.node_id,
    mode: "modules",
    depth: 1,
    nodes: [moduleA, moduleB],
    relationships: [importRelationship, unresolvedRelationship],
    distances: { [moduleA.node_id]: 0, [moduleB.node_id]: 1 },
    truncated: false,
};

export const cycleGroup: CycleGroup = {
    cycle_id: "cycle-0123456789abcdef",
    relationship_type: "imports",
    member_node_ids: [moduleA.node_id, moduleB.node_id],
    edge_ids: [importRelationship.relationship_id],
};

export const finding: Finding = {
    finding_id: "finding-0123456789abcdef",
    rule_id: "high-parameter-count",
    rule_version: "1",
    family: "parameters",
    title: "<img src=x onerror=alert(1)>",
    explanation: "Parameter count is 9; the experimental threshold is greater than 8.",
    suggested_action: "Review the measured structure.",
    severity: "low",
    confidence: "high",
    subject_type: "symbol",
    subject_keys: ["pkg.metrics.complex_target"],
    affected_node_ids: ["symbol-complex-fixture"],
    relative_path: "pkg/metrics.py",
    line: 4,
    metric_evidence: [["parameter_count", 9]],
    threshold_evidence: [["parameter_count", 8]],
    repository_id: repository.repository_id,
    first_seen_snapshot_id: snapshot.snapshot_id,
    last_seen_snapshot_id: snapshot.snapshot_id,
    evidence_state: "active",
    resolved_snapshot_id: null,
    review_status: "new",
    effective_status: "new",
    note: "",
    reason_code: null,
    review_version: 0,
    decided_at: "2026-07-24T12:00:01.000Z",
    updated_at: "2026-07-24T12:00:01.000Z",
};

export const secondFinding: Finding = {
    ...finding,
    finding_id: "finding-second-0123456789abcdef",
    rule_id: "orphan-looking-candidate",
    family: "orphan-candidate",
    title: "Orphan-looking public symbol candidate",
    confidence: "low",
    subject_keys: ["pkg.metrics.orphan_candidate"],
    affected_node_ids: ["symbol-orphan-fixture"],
    line: 20,
};

export const findingSummary: FindingSummary = {
    supported: true,
    active: 2,
    resolved: 0,
    needs_action: 0,
    accepted: 0,
    dismissed: 0,
    severity: { high: 0, medium: 0, low: 2 },
    low_confidence: 1,
};

export const findingHistory: FindingHistory = {
    items: [
        {
            event_id: 1,
            finding_id: finding.finding_id,
            event_type: "finding-first-seen",
            snapshot_id: snapshot.snapshot_id,
            review_status: null,
            reason_code: null,
            note: "",
            review_version: null,
            event_at: "2026-07-24T12:00:01.000Z",
        },
    ],
    total: 1,
    page: 1,
    page_size: 50,
};

export function response(payload: object, status = 200): Response {
    return new Response(JSON.stringify(payload), {
        status,
        headers: { "Content-Type": "application/json" },
    });
}
