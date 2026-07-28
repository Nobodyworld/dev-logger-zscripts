import { useEffect, useRef, useState } from "react";

import { ApiError, getComparisonItems, getComparisonSnapshots, getComparisonSummary } from "../api";
import type {
    ComparisonItem,
    ComparisonPage,
    ComparisonSection,
    ComparisonSnapshot,
    ComparisonSummary,
} from "../types";

interface CompareViewProps {
    repositoryId: string;
    targetSnapshotId: string;
}

const SECTIONS: ComparisonSection[] = [
    "files",
    "symbols",
    "relationships",
    "cycles",
    "metrics",
    "findings",
];

export function CompareView({ repositoryId, targetSnapshotId }: CompareViewProps) {
    const [snapshots, setSnapshots] = useState<ComparisonSnapshot[]>([]);
    const [baselineId, setBaselineId] = useState("");
    const [targetId, setTargetId] = useState(targetSnapshotId);
    const [section, setSection] = useState<ComparisonSection>("files");
    const [changeType, setChangeType] = useState("");
    const [search, setSearch] = useState("");
    const [sort, setSort] = useState<"logical_key" | "label" | "change_type">("logical_key");
    const [direction, setDirection] = useState<"asc" | "desc">("asc");
    const [pageNumber, setPageNumber] = useState(1);
    const [summary, setSummary] = useState<ComparisonSummary | null>(null);
    const [page, setPage] = useState<ComparisonPage | null>(null);
    const [selected, setSelected] = useState<ComparisonItem | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const requestGeneration = useRef(0);

    useEffect(() => {
        const controller = new AbortController();
        const generation = ++requestGeneration.current;
        void (async () => {
            setLoading(true);
            setError(null);
            try {
                const result = await getComparisonSnapshots(repositoryId, controller.signal);
                if (generation !== requestGeneration.current) return;
                setSnapshots(result.snapshots);
                const targetIndex = Math.max(
                    result.snapshots.findIndex((item) => item.snapshot_id === targetSnapshotId),
                    0,
                );
                const nextTarget = result.snapshots[targetIndex]?.snapshot_id ?? "";
                const nextBaseline = result.snapshots[targetIndex + 1]?.snapshot_id ?? nextTarget;
                setTargetId(nextTarget);
                setBaselineId(nextBaseline);
                setLoading(false);
            } catch (caught) {
                if (controller.signal.aborted || generation !== requestGeneration.current) return;
                setLoading(false);
                setError(messageFrom(caught, "Comparison snapshots could not be loaded."));
            }
        })();
        return () => {
            controller.abort();
            requestGeneration.current += 1;
        };
    }, [repositoryId, targetSnapshotId]);

    useEffect(() => {
        if (!baselineId || !targetId) return;
        const controller = new AbortController();
        const generation = ++requestGeneration.current;
        void (async () => {
            setLoading(true);
            setError(null);
            setPage(null);
            setSelected(null);
            try {
                const [nextSummary, nextPage] = await Promise.all([
                    getComparisonSummary(baselineId, targetId, controller.signal),
                    getComparisonItems(
                        {
                            baselineSnapshotId: baselineId,
                            targetSnapshotId: targetId,
                            section,
                            changeType,
                            search,
                            sort,
                            direction,
                            page: pageNumber,
                            pageSize: 50,
                        },
                        controller.signal,
                    ),
                ]);
                if (generation !== requestGeneration.current) return;
                setSummary(nextSummary);
                setPage(nextPage);
                setSelected(nextPage.items[0] ?? null);
                setLoading(false);
            } catch (caught) {
                if (controller.signal.aborted || generation !== requestGeneration.current) return;
                setLoading(false);
                setError(messageFrom(caught, "The comparison could not be loaded."));
            }
        })();
        return () => {
            controller.abort();
        };
    }, [baselineId, changeType, direction, pageNumber, search, section, sort, targetId]);

    const targetSnapshot = snapshots.find((item) => item.snapshot_id === targetId);
    const baselineSnapshot = snapshots.find((item) => item.snapshot_id === baselineId);
    const sectionCompatibility = summary?.compatibility.sections.find(
        (item) => item.section === section,
    );

    return (
        <section className="review-view compare-view" aria-labelledby="compare-title">
            <div className="view-heading">
                <div>
                    <p className="eyebrow">Deterministic snapshot evidence</p>
                    <h1 id="compare-title">Compare</h1>
                    <p>
                        Logical matching only. Renames remain a removed subject plus an added
                        subject.
                    </p>
                </div>
                {summary ? (
                    <span className="status-chip">
                        Format {summary.identity.comparison_format_version}
                    </span>
                ) : null}
            </div>

            <div className="snapshot-pair" aria-label="Comparison snapshots">
                <SnapshotSelect
                    label="Baseline"
                    value={baselineId}
                    snapshots={snapshots}
                    onChange={(value) => {
                        setBaselineId(value);
                        setPageNumber(1);
                    }}
                />
                <SnapshotSelect
                    label="Target"
                    value={targetId}
                    snapshots={snapshots}
                    onChange={(value) => {
                        setTargetId(value);
                        setPageNumber(1);
                    }}
                />
            </div>
            <div className="snapshot-context">
                <SnapshotFacts label="Baseline" snapshot={baselineSnapshot} />
                <SnapshotFacts label="Target" snapshot={targetSnapshot} />
            </div>

            {summary?.equal_snapshots ? (
                <p className="notice-banner" role="status">
                    Baseline and target are the same snapshot. No changes are expected.
                </p>
            ) : null}
            {sectionCompatibility && sectionCompatibility.status !== "supported" ? (
                <p className="notice-banner notice-banner--warning" role="status">
                    {sectionLabel(section)} evidence is {sectionCompatibility.status}:{" "}
                    {sectionCompatibility.reason_codes.join(", ") || "not available"}.
                </p>
            ) : null}

            {summary ? <ComparisonCounts summary={summary} /> : null}

            <div className="section-tabs" role="tablist" aria-label="Comparison section">
                {SECTIONS.map((item) => (
                    <button
                        key={item}
                        type="button"
                        role="tab"
                        aria-selected={section === item}
                        className={
                            section === item ? "section-tab section-tab--active" : "section-tab"
                        }
                        onClick={() => {
                            setSection(item);
                            setPageNumber(1);
                        }}
                    >
                        {sectionLabel(item)}
                    </button>
                ))}
            </div>

            <div className="comparison-toolbar">
                <label>
                    Search
                    <input
                        value={search}
                        maxLength={200}
                        onChange={(event) => {
                            setSearch(event.target.value);
                            setPageNumber(1);
                        }}
                        placeholder={`Search ${section}`}
                    />
                </label>
                <label>
                    Change
                    <select
                        value={changeType}
                        onChange={(event) => {
                            setChangeType(event.target.value);
                            setPageNumber(1);
                        }}
                    >
                        <option value="">All changes</option>
                        <option value="added">Added</option>
                        <option value="removed">Removed</option>
                        <option value="not-observed">Not observed</option>
                        <option value="changed">Changed</option>
                    </select>
                </label>
                <label>
                    Sort
                    <select
                        value={sort}
                        onChange={(event) => {
                            setSort(event.target.value as "logical_key" | "label" | "change_type");
                            setPageNumber(1);
                        }}
                    >
                        <option value="logical_key">Logical key</option>
                        <option value="label">Label</option>
                        <option value="change_type">Change type</option>
                    </select>
                </label>
                <button
                    type="button"
                    className="secondary-button compact-button"
                    onClick={() => setDirection((current) => (current === "asc" ? "desc" : "asc"))}
                >
                    {direction === "asc" ? "Ascending" : "Descending"}
                </button>
            </div>

            {error ? (
                <p className="global-error" role="alert">
                    {error}
                </p>
            ) : null}
            {loading ? <p className="loading-state">Loading bounded comparison…</p> : null}
            {!loading && page?.items.length === 0 ? (
                <p className="empty-panel">No matching changes in this section.</p>
            ) : null}

            {page && page.items.length > 0 ? (
                <div className="comparison-layout">
                    <div
                        className="comparison-list"
                        aria-label={`${sectionLabel(section)} changes`}
                    >
                        {page.items.map((item) => (
                            <button
                                type="button"
                                key={item.delta_id}
                                className={
                                    selected?.delta_id === item.delta_id
                                        ? "comparison-row comparison-row--selected"
                                        : "comparison-row"
                                }
                                aria-pressed={selected?.delta_id === item.delta_id}
                                onClick={() => setSelected(item)}
                            >
                                <span className={`change-badge change-badge--${item.change_type}`}>
                                    {item.change_type}
                                </span>
                                <strong>{item.label}</strong>
                                <small>{item.relative_path ?? item.logical_key}</small>
                            </button>
                        ))}
                    </div>
                    <ComparisonDetails item={selected} />
                </div>
            ) : null}

            {page ? (
                <div className="pagination-row" aria-label="Comparison pagination">
                    <span>
                        Page {page.page} · {page.total} changes
                    </span>
                    <div>
                        <button
                            type="button"
                            className="secondary-button compact-button"
                            disabled={page.page <= 1}
                            onClick={() => setPageNumber((current) => Math.max(1, current - 1))}
                        >
                            Previous
                        </button>
                        <button
                            type="button"
                            className="secondary-button compact-button"
                            disabled={!page.truncated}
                            onClick={() => setPageNumber((current) => current + 1)}
                        >
                            Next
                        </button>
                    </div>
                </div>
            ) : null}
        </section>
    );
}

function SnapshotSelect({
    label,
    value,
    snapshots,
    onChange,
}: {
    label: string;
    value: string;
    snapshots: ComparisonSnapshot[];
    onChange: (value: string) => void;
}) {
    return (
        <label>
            {label}
            <select value={value} onChange={(event) => onChange(event.target.value)}>
                {snapshots.map((snapshot) => (
                    <option key={snapshot.snapshot_id} value={snapshot.snapshot_id}>
                        {snapshot.completed_at ?? "Incomplete time"} ·{" "}
                        {snapshot.git_sha?.slice(0, 8) ?? "no Git SHA"}
                    </option>
                ))}
            </select>
        </label>
    );
}

function SnapshotFacts({
    label,
    snapshot,
}: {
    label: string;
    snapshot: ComparisonSnapshot | undefined;
}) {
    if (!snapshot) return <div className="snapshot-facts">{label}: unavailable</div>;
    return (
        <div className="snapshot-facts">
            <strong>{label}</strong>
            <span>
                {snapshot.branch ?? "detached"} · {snapshot.git_sha?.slice(0, 12) ?? "no Git SHA"}
            </span>
            <span>
                {snapshot.dirty ? "dirty" : "clean"} · {snapshot.staged ? "staged" : "unstaged"} ·{" "}
                {snapshot.untracked ? "untracked files" : "no untracked files"}
            </span>
            <span>{snapshot.completed_at ?? "scan completion unavailable"}</span>
            <span>
                analyzer {snapshot.analyzer_version} · schema {snapshot.schema_version} · rules{" "}
                {snapshot.rule_set_version}
            </span>
            <span>
                {snapshot.truncated ? "truncated" : "complete"} · {snapshot.parse_gap_count} parse
                gaps
            </span>
        </div>
    );
}

function ComparisonCounts({ summary }: { summary: ComparisonSummary }) {
    const visible = Object.entries(summary.counts).filter(([, count]) => count > 0);
    const limitedSections = summary.compatibility.sections.filter(
        (section) => section.status !== "supported",
    );
    return (
        <div className="comparison-counts" aria-label="Comparison summary">
            {visible.length ? (
                visible.map(([name, count]) => (
                    <div key={name}>
                        <strong>{count}</strong>
                        <span>{name.replaceAll("_", " ")}</span>
                    </div>
                ))
            ) : (
                <div>
                    <strong>0</strong>
                    <span>detected changes</span>
                </div>
            )}
            {limitedSections.map((section) => (
                <div key={section.section}>
                    <strong>{section.status}</strong>
                    <span>{section.section} evidence</span>
                </div>
            ))}
        </div>
    );
}

function ComparisonDetails({ item }: { item: ComparisonItem | null }) {
    if (!item) return <aside className="comparison-details">Select a change for evidence.</aside>;
    return (
        <aside className="comparison-details" aria-live="polite">
            <p className="eyebrow">Selected evidence</p>
            <h2>{item.label}</h2>
            <dl>
                <dt>Change</dt>
                <dd>{item.change_type}</dd>
                <dt>Logical key</dt>
                <dd className="mono-wrap">{item.logical_key}</dd>
                {item.relative_path ? (
                    <>
                        <dt>Repository-relative path</dt>
                        <dd>{item.relative_path}</dd>
                    </>
                ) : null}
                {item.occurrence_state ? (
                    <>
                        <dt>Occurrence at target snapshot</dt>
                        <dd>{item.occurrence_state}</dd>
                    </>
                ) : null}
                {item.current_state ? (
                    <>
                        <dt>Current lifecycle state</dt>
                        <dd>{item.current_state.evidence_state}</dd>
                        <dt>Current review status</dt>
                        <dd>{item.current_state.review_status}</dd>
                    </>
                ) : null}
            </dl>
            {item.baseline ? <EvidenceFields heading="Baseline" value={item.baseline} /> : null}
            {item.target ? <EvidenceFields heading="Target" value={item.target} /> : null}
        </aside>
    );
}

function EvidenceFields({ heading, value }: { heading: string; value: Record<string, unknown> }) {
    return (
        <div className="evidence-fields">
            <h3>{heading}</h3>
            <dl>
                {Object.entries(value).map(([name, field]) => (
                    <div key={name}>
                        <dt>{name.replaceAll("_", " ")}</dt>
                        <dd>{String(field ?? "none")}</dd>
                    </div>
                ))}
            </dl>
        </div>
    );
}

function sectionLabel(section: ComparisonSection): string {
    return section.charAt(0).toUpperCase() + section.slice(1);
}

function messageFrom(error: unknown, fallback: string): string {
    return error instanceof ApiError ? error.message : fallback;
}
