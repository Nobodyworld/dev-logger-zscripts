import type { Overview, Repository, Snapshot, SymbolRecord } from "../types";

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
    analyzer_version: "1",
    schema_version: "1",
    rule_set_version: "1",
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

export function response(payload: object, status = 200): Response {
    return new Response(JSON.stringify(payload), {
        status,
        headers: { "Content-Type": "application/json" },
    });
}
