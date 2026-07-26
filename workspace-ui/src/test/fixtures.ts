import type {
    CycleGroup,
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

export function response(payload: object, status = 200): Response {
    return new Response(JSON.stringify(payload), {
        status,
        headers: { "Content-Type": "application/json" },
    });
}
