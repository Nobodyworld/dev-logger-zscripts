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

export type ViewName = "overview" | "symbols";
