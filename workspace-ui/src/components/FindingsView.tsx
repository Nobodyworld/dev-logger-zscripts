import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
    ApiError,
    getFinding,
    getFindingHistory,
    getFindings,
    getFindingSummary,
    getSource,
    updateFindingReview,
} from "../api";
import { useEvidenceStatus } from "../hooks/useEvidenceStatus";
import { SearchIcon } from "../icons";
import type {
    Finding,
    FindingFamily,
    FindingHistory,
    FindingPage,
    FindingQueuePreset,
    FindingSummary,
    ReviewStatus,
    SourceEvidence,
} from "../types";
import { EvidenceStatusBanner } from "./EvidenceStatusBanner";

interface FindingsViewProps {
    snapshotId: string;
    preset?: string;
}

const emptySummary: FindingSummary = {
    supported: true,
    active: 0,
    resolved: 0,
    needs_action: 0,
    accepted: 0,
    dismissed: 0,
    severity: { high: 0, medium: 0, low: 0 },
    families: {
        "dependency-cycle": 0,
        "inheritance-cycle": 0,
        "duplicate-name-candidate": 0,
        oversized: 0,
        complexity: 0,
        nesting: 0,
        parameters: 0,
        coupling: 0,
        inheritance: 0,
        documentation: 0,
        "test-evidence-candidate": 0,
        "orphan-candidate": 0,
    },
    low_confidence: 0,
    reconciliation_complete: true,
    lifecycle_reconciled: true,
    reconciliation_skip_reason: null,
};
const findingFamilies: FindingFamily[] = [
    "dependency-cycle",
    "inheritance-cycle",
    "duplicate-name-candidate",
    "oversized",
    "complexity",
    "nesting",
    "parameters",
    "coupling",
    "inheritance",
    "documentation",
    "test-evidence-candidate",
    "orphan-candidate",
];
const excludedFamilyLabels: Array<[FindingFamily, string]> = [
    ["documentation", "Documentation"],
    ["orphan-candidate", "Orphan candidates"],
    ["duplicate-name-candidate", "Duplicate-name candidates"],
    ["test-evidence-candidate", "Test-evidence candidates"],
];

export function FindingsView({ snapshotId, preset = "" }: FindingsViewProps) {
    const evidenceStatus = useEvidenceStatus(snapshotId);
    const [queuePreset, setQueuePreset] = useState<FindingQueuePreset>(
        preset ? "all" : "high-signal-v1",
    );
    const [summary, setSummary] = useState<FindingSummary>(emptySummary);
    const [page, setPage] = useState<FindingPage | null>(null);
    const [search, setSearch] = useState("");
    const [family, setFamily] = useState("");
    const [severity, setSeverity] = useState(preset === "high-confidence-severity" ? "high" : "");
    const [confidence, setConfidence] = useState(
        preset === "high-confidence-severity" ? "high" : "",
    );
    const [effectiveStatus, setEffectiveStatus] = useState(
        preset === "needs-action" ? "needs-action" : "",
    );
    const [evidenceState, setEvidenceState] = useState(
        preset === "resolved" ? "resolved" : "active",
    );
    const [sort, setSort] = useState("severity");
    const [pageNumber, setPageNumber] = useState(1);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [selected, setSelected] = useState<Finding | null>(null);
    const [history, setHistory] = useState<FindingHistory | null>(null);
    const [source, setSource] = useState<SourceEvidence | null>(null);
    const [loading, setLoading] = useState(true);
    const [detailLoading, setDetailLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [detailError, setDetailError] = useState<string | null>(null);
    const [reviewStatus, setReviewStatus] = useState<ReviewStatus>("new");
    const [reasonCode, setReasonCode] = useState("");
    const [note, setNote] = useState("");
    const [saving, setSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState("");
    const [reviewNotice, setReviewNotice] = useState("");
    const [filterNotice, setFilterNotice] = useState("");
    const [reloadVersion, setReloadVersion] = useState(0);
    const listGeneration = useRef(0);
    const detailGeneration = useRef(0);
    const saveGeneration = useRef(0);
    const previousNavigationPreset = useRef(preset);
    const selectedIdRef = useRef(selectedId);
    const pageRef = useRef(page);

    const direction: "asc" | "desc" =
        sort === "qualified_subject" || sort === "family" ? "asc" : "desc";
    const pageSize = 25;
    const listQuery = useMemo(
        () => ({
            preset: queuePreset,
            search,
            family,
            severity,
            confidence,
            effectiveStatus,
            evidenceState,
            sort,
            direction,
            page: pageNumber,
            pageSize,
        }),
        [
            queuePreset,
            search,
            family,
            severity,
            confidence,
            effectiveStatus,
            evidenceState,
            sort,
            direction,
            pageNumber,
        ],
    );

    const activeConstraints = useMemo(
        () => [
            queuePreset === "high-signal-v1" ? "Queue: Focused" : "Queue: All findings",
            ...(family ? [`Family: ${family}`] : []),
            ...(severity ? [`Severity: ${severity}`] : []),
            ...(confidence ? [`Confidence: ${confidence}`] : []),
            `Status: ${effectiveStatus || "all"}`,
            `Evidence: ${evidenceState || "active and resolved"}`,
            ...(search ? [`Search: ${search}`] : []),
        ],
        [queuePreset, family, severity, confidence, effectiveStatus, evidenceState, search],
    );

    const dirty =
        selected !== null &&
        (reviewStatus !== selected.review_status ||
            reasonCode !== (selected.reason_code ?? "") ||
            note !== selected.note);

    useEffect(() => {
        selectedIdRef.current = selectedId;
    }, [selectedId]);

    useEffect(() => {
        pageRef.current = page;
    }, [page]);

    const invalidateSelection = useCallback(() => {
        detailGeneration.current += 1;
        saveGeneration.current += 1;
        setSelected(null);
        setHistory(null);
        setSource(null);
        setDetailError(null);
        setSaveMessage("");
    }, []);

    useEffect(() => {
        if (previousNavigationPreset.current === preset) return;
        previousNavigationPreset.current = preset;
        listGeneration.current += 1;
        setQueuePreset(preset ? "all" : "high-signal-v1");
        setPage(null);
        setSearch("");
        setFamily("");
        setSeverity(preset === "high-confidence-severity" ? "high" : "");
        setConfidence(preset === "high-confidence-severity" ? "high" : "");
        setEffectiveStatus(preset === "needs-action" ? "needs-action" : "");
        setEvidenceState(preset === "resolved" ? "resolved" : "active");
        setSort("severity");
        setPageNumber(1);
        setFilterNotice("");
        invalidateSelection();
        setSelectedId(null);
    }, [invalidateSelection, preset]);

    const reloadWorkspace = useCallback(async () => {
        const generation = ++listGeneration.current;
        const previousPage = pageRef.current;
        const previousSelectedId = selectedIdRef.current;
        setLoading(true);
        setError(null);
        try {
            const [listResult, summaryResult] = await Promise.allSettled([
                getFindings(snapshotId, listQuery),
                getFindingSummary(snapshotId),
            ]);
            if (generation !== listGeneration.current) return;
            if (summaryResult.status === "fulfilled") {
                setSummary(summaryResult.value);
            }
            if (listResult.status === "rejected") {
                throw listResult.reason;
            }
            const value = listResult.value;
            setPage(value);
            if (value.items.length === 0 && value.total > 0 && listQuery.page > 1) {
                setPageNumber(Math.max(Math.ceil(value.total / listQuery.pageSize), 1));
                return;
            }
            const previousIndex =
                previousPage?.items.findIndex((item) => item.finding_id === previousSelectedId) ??
                -1;
            const nextId =
                previousSelectedId &&
                value.items.some((item) => item.finding_id === previousSelectedId)
                    ? previousSelectedId
                    : (value.items[
                          previousIndex >= 0 ? Math.min(previousIndex, value.items.length - 1) : 0
                      ]?.finding_id ?? null);
            if (nextId !== previousSelectedId) {
                invalidateSelection();
                setSelectedId(nextId);
            }
        } catch {
            if (generation !== listGeneration.current) return;
            setPage(null);
            setError("Findings could not be loaded.");
            invalidateSelection();
            setSelectedId(null);
        } finally {
            if (generation === listGeneration.current) setLoading(false);
        }
    }, [invalidateSelection, listQuery, snapshotId]);

    const requestWorkspaceReload = useCallback(() => {
        listGeneration.current += 1;
        setReloadVersion((value) => value + 1);
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            void reloadWorkspace();
        }, 180);
        return () => {
            window.clearTimeout(timer);
            listGeneration.current += 1;
        };
    }, [reloadVersion, reloadWorkspace]);

    useEffect(() => {
        if (!selectedId) return;
        const generation = ++detailGeneration.current;
        const controller = new AbortController();
        const timer = window.setTimeout(() => {
            setDetailLoading(true);
            setDetailError(null);
            setSaveMessage("");
            setSelected(null);
            setHistory(null);
            setSource(null);
            Promise.all([
                getFinding(selectedId, snapshotId, controller.signal),
                getFindingHistory(selectedId, controller.signal),
            ])
                .then(async ([finding, nextHistory]) => {
                    if (generation !== detailGeneration.current) return;
                    setSelected(finding);
                    setHistory(nextHistory);
                    setReviewStatus(finding.review_status);
                    setReasonCode(finding.reason_code ?? "");
                    setNote(finding.note);
                    if (finding.relative_path && finding.line) {
                        try {
                            const evidence = await getSource(
                                snapshotId,
                                finding.relative_path,
                                Math.max(finding.line - 3, 1),
                                finding.line + 12,
                            );
                            if (generation === detailGeneration.current) setSource(evidence);
                        } catch {
                            if (generation === detailGeneration.current) setSource(null);
                        }
                    }
                })
                .catch((caught: unknown) => {
                    if (
                        generation !== detailGeneration.current ||
                        (caught instanceof DOMException && caught.name === "AbortError")
                    )
                        return;
                    setDetailError("Finding details could not be loaded.");
                })
                .finally(() => {
                    if (generation === detailGeneration.current) setDetailLoading(false);
                });
        }, 0);
        return () => {
            window.clearTimeout(timer);
            controller.abort();
            detailGeneration.current += 1;
        };
    }, [invalidateSelection, selectedId, snapshotId]);

    const selectFinding = (findingId: string) => {
        if (findingId === selectedId) return;
        invalidateSelection();
        setSelectedId(findingId);
    };

    const clearFocusedForExplicitFilter = (value: string) => {
        if (value && queuePreset === "high-signal-v1") {
            setQueuePreset("all");
            setFilterNotice("Focused preset cleared for explicit filters.");
        }
        setPageNumber(1);
    };

    const showAllFindings = () => {
        setQueuePreset("all");
        setPageNumber(1);
        setFilterNotice("All finding families are now included.");
    };

    const restoreFocusedQueue = () => {
        setQueuePreset("high-signal-v1");
        setFamily("");
        setSeverity("");
        setConfidence("");
        setPageNumber(1);
        setFilterNotice("Focused high-signal-v1 queue restored.");
    };

    const clearExplicitFilters = () => {
        setSearch("");
        setFamily("");
        setSeverity("");
        setConfidence("");
        setEffectiveStatus("");
        setEvidenceState("active");
        setPageNumber(1);
        setFilterNotice("Explicit filters cleared.");
    };

    const saveReview = async () => {
        if (!selected || !dirty || saving) return;
        const findingId = selected.finding_id;
        const generation = ++saveGeneration.current;
        setSaving(true);
        setSaveMessage("");
        setReviewNotice("");
        setDetailError(null);
        try {
            const updated = await updateFindingReview(findingId, {
                expectedVersion: selected.review_version,
                reviewStatus,
                note,
                reasonCode,
            });
            if (generation !== saveGeneration.current || findingId !== selectedId) return;
            setSelected(updated);
            setReviewStatus(updated.review_status);
            setReasonCode(updated.reason_code ?? "");
            setNote(updated.note);
            setSaveMessage("Review saved.");
            requestWorkspaceReload();
            try {
                const nextHistory = await getFindingHistory(findingId);
                if (generation === saveGeneration.current && findingId === selectedId) {
                    setHistory(nextHistory);
                }
            } catch {
                // The saved decision remains authoritative when history refresh fails.
            }
        } catch (caught) {
            if (generation !== saveGeneration.current || findingId !== selectedId) return;
            if (caught instanceof ApiError && caught.status === 409 && caught.currentFinding) {
                const current = caught.currentFinding;
                setSelected(current);
                setReviewStatus(current.review_status);
                setReasonCode(current.reason_code ?? "");
                setNote(current.note);
                setReviewNotice(
                    "Another review update was saved first. Current local state has been reloaded.",
                );
                requestWorkspaceReload();
                try {
                    const nextHistory = await getFindingHistory(findingId);
                    if (generation === saveGeneration.current && findingId === selectedId) {
                        setHistory(nextHistory);
                    }
                } catch {
                    // The safe conflict detail remains usable when history refresh fails.
                }
            } else {
                setDetailError("The review decision could not be saved.");
            }
        } finally {
            if (generation === saveGeneration.current) setSaving(false);
        }
    };

    if (!summary.supported || page?.supported === false) {
        return (
            <section className="view findings-view" aria-labelledby="findings-heading">
                <h2 id="findings-heading">Findings</h2>
                <EvidenceStatusBanner status={evidenceStatus.status} error={evidenceStatus.error} />
                <p className="relationships-empty">
                    Findings are not available for this older snapshot. Run a new completed scan to
                    generate versioned finding evidence.
                </p>
            </section>
        );
    }

    return (
        <section className="view findings-view" aria-labelledby="findings-heading">
            <div className="findings-heading-row">
                <div>
                    <h2 id="findings-heading">Findings</h2>
                    <p>Deterministic review candidates from versioned static rules.</p>
                </div>
                <dl className="finding-summary" aria-label="Finding summary">
                    {[
                        ["Active", summary.active],
                        ["Resolved", summary.resolved],
                        ["Needs action", summary.needs_action],
                        ["Accepted", summary.accepted],
                        ["Dismissed", summary.dismissed],
                        ["High", summary.severity.high ?? 0],
                        ["Medium", summary.severity.medium ?? 0],
                        ["Low", summary.severity.low ?? 0],
                        ["Low confidence", summary.low_confidence],
                    ].map(([label, value]) => (
                        <div key={label}>
                            <dt>{label}</dt>
                            <dd>{value}</dd>
                        </div>
                    ))}
                </dl>
            </div>
            <EvidenceStatusBanner status={evidenceStatus.status} error={evidenceStatus.error} />

            <section
                className={`finding-preset-banner finding-preset-banner--${queuePreset === "high-signal-v1" ? "focused" : "all"}`}
                aria-labelledby="finding-preset-heading"
            >
                <div>
                    <p className="eyebrow">Queue preset</p>
                    <h3 id="finding-preset-heading">
                        {queuePreset === "high-signal-v1" ? "Focused queue" : "All findings"}
                    </h3>
                    <p className="finding-preset-name">Applied preset: {queuePreset}</p>
                    <p>
                        {queuePreset === "high-signal-v1"
                            ? "Showing higher-signal cycles and measured complexity, size, coupling, nesting, parameter, and inheritance findings. Full lifecycle counts remain above; documentation and orphan candidates remain available in All findings."
                            : "Showing every finding family in the current lifecycle."}
                    </p>
                    <dl
                        className="finding-excluded-counts"
                        aria-label="Full low-signal family counts"
                    >
                        {excludedFamilyLabels.map(([familyName, label]) => (
                            <div key={familyName}>
                                <dt>{label}</dt>
                                <dd>{summary.families[familyName] ?? 0}</dd>
                            </div>
                        ))}
                    </dl>
                </div>
                <div
                    className="finding-preset-controls"
                    role="group"
                    aria-label="Finding queue preset. Focused is a higher-signal subset."
                >
                    <button
                        type="button"
                        aria-pressed={queuePreset === "high-signal-v1"}
                        onClick={restoreFocusedQueue}
                    >
                        Focused
                    </button>
                    <button
                        type="button"
                        aria-pressed={queuePreset === "all"}
                        onClick={showAllFindings}
                    >
                        All findings
                    </button>
                </div>
                {queuePreset === "high-signal-v1" ? (
                    <button type="button" className="text-action" onClick={showAllFindings}>
                        Show all findings
                    </button>
                ) : (
                    <button type="button" className="text-action" onClick={restoreFocusedQueue}>
                        Restore focused queue
                    </button>
                )}
            </section>

            <div className="finding-active-filters" aria-label="Active finding constraints">
                <span>Active constraints</span>
                <ul>
                    {activeConstraints.map((constraint) => (
                        <li key={constraint}>{constraint}</li>
                    ))}
                </ul>
                <button type="button" onClick={clearExplicitFilters}>
                    Clear explicit filters
                </button>
            </div>

            {filterNotice ? (
                <p className="selection-status" role="status">
                    {filterNotice}
                </p>
            ) : null}

            <div className="finding-toolbar" aria-label="Finding filters">
                <label className="search-field">
                    <span className="sr-only">Search findings</span>
                    <SearchIcon />
                    <input
                        value={search}
                        maxLength={200}
                        placeholder="Search title or qualified subject"
                        onChange={(event) => {
                            setSearch(event.target.value);
                            setPageNumber(1);
                        }}
                    />
                </label>
                <Filter
                    label="Family"
                    value={family}
                    onChange={(value) => {
                        clearFocusedForExplicitFilter(value);
                        setFamily(value);
                    }}
                >
                    <option value="">All families</option>
                    {findingFamilies.map((item) => (
                        <option value={item} key={item}>
                            {item}
                        </option>
                    ))}
                </Filter>
                <Filter
                    label="Severity"
                    value={severity}
                    onChange={(value) => {
                        clearFocusedForExplicitFilter(value);
                        setSeverity(value);
                    }}
                >
                    <option value="">All severities</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                </Filter>
                <Filter
                    label="Confidence"
                    value={confidence}
                    onChange={(value) => {
                        clearFocusedForExplicitFilter(value);
                        setConfidence(value);
                    }}
                >
                    <option value="">All confidence</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                </Filter>
                <Filter
                    label="Status"
                    value={effectiveStatus}
                    onChange={(value) => {
                        setEffectiveStatus(value);
                        setPageNumber(1);
                    }}
                >
                    <option value="">All statuses</option>
                    <option value="new">New</option>
                    <option value="reviewed">Reviewed</option>
                    <option value="needs-action">Needs action</option>
                    <option value="accepted">Accepted</option>
                    <option value="dismissed">Dismissed</option>
                    <option value="resolved">Resolved</option>
                </Filter>
                <Filter
                    label="Evidence"
                    value={evidenceState}
                    onChange={(value) => {
                        setEvidenceState(value);
                        setPageNumber(1);
                    }}
                >
                    <option value="">Active and resolved</option>
                    <option value="active">Active</option>
                    <option value="resolved">Resolved</option>
                </Filter>
                <Filter
                    label="Sort"
                    value={sort}
                    onChange={(value) => {
                        setSort(value);
                        setPageNumber(1);
                    }}
                >
                    <option value="severity">Severity</option>
                    <option value="family">Family</option>
                    <option value="status">Status</option>
                    <option value="first_seen">First seen</option>
                    <option value="last_seen">Last seen</option>
                    <option value="qualified_subject">Qualified subject</option>
                    <option value="finding_id">Finding ID</option>
                </Filter>
            </div>

            {error ? (
                <p className="error-message" role="alert">
                    {error}
                </p>
            ) : null}
            {reviewNotice ? (
                <p className="error-message" role="alert">
                    {reviewNotice}
                </p>
            ) : null}
            {loading ? <p className="selection-status">Loading findings…</p> : null}
            {!loading && page?.items.length === 0 ? (
                <p className="relationships-empty">No findings match the current bounded query.</p>
            ) : null}

            {page && page.items.length > 0 ? (
                <>
                    <div className="findings-workspace">
                        <div className="finding-queue" aria-label="Finding queue">
                            {page.items.map((item) => (
                                <button
                                    type="button"
                                    key={item.finding_id}
                                    aria-pressed={item.finding_id === selectedId}
                                    onClick={() => selectFinding(item.finding_id)}
                                >
                                    <span
                                        className={`finding-severity finding-severity--${item.severity}`}
                                    >
                                        {item.severity}
                                    </span>
                                    <strong>{item.title}</strong>
                                    <span>{item.subject_keys.join(", ")}</span>
                                    <span>
                                        {item.family} · {item.effective_status} · {item.confidence}{" "}
                                        confidence
                                    </span>
                                </button>
                            ))}
                        </div>
                        <div className="finding-detail" aria-live="polite">
                            {detailLoading ? <p>Loading finding details…</p> : null}
                            {detailError ? (
                                <p className="error-message" role="alert">
                                    {detailError}
                                </p>
                            ) : null}
                            {selected ? (
                                <FindingDetails
                                    finding={selected}
                                    history={history}
                                    source={source}
                                    reviewStatus={reviewStatus}
                                    reasonCode={reasonCode}
                                    note={note}
                                    dirty={dirty}
                                    saving={saving}
                                    saveMessage={saveMessage}
                                    onStatus={setReviewStatus}
                                    onReason={setReasonCode}
                                    onNote={setNote}
                                    onSave={saveReview}
                                />
                            ) : null}
                        </div>
                    </div>
                    <div className="pagination">
                        <span>
                            Page {page.page} · {page.total.toLocaleString()} findings
                        </span>
                        <div>
                            <button
                                type="button"
                                disabled={page.page <= 1}
                                onClick={() => setPageNumber((value) => value - 1)}
                            >
                                Previous
                            </button>
                            <button
                                type="button"
                                disabled={page.page * page.page_size >= page.total}
                                onClick={() => setPageNumber((value) => value + 1)}
                            >
                                Next
                            </button>
                        </div>
                    </div>
                </>
            ) : null}
        </section>
    );
}

function Filter({
    label,
    value,
    onChange,
    children,
}: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    children: React.ReactNode;
}) {
    return (
        <label className="filter-field">
            {label}
            <select value={value} onChange={(event) => onChange(event.target.value)}>
                {children}
            </select>
        </label>
    );
}

function FindingDetails({
    finding,
    history,
    source,
    reviewStatus,
    reasonCode,
    note,
    dirty,
    saving,
    saveMessage,
    onStatus,
    onReason,
    onNote,
    onSave,
}: {
    finding: Finding;
    history: FindingHistory | null;
    source: SourceEvidence | null;
    reviewStatus: ReviewStatus;
    reasonCode: string;
    note: string;
    dirty: boolean;
    saving: boolean;
    saveMessage: string;
    onStatus: (value: ReviewStatus) => void;
    onReason: (value: string) => void;
    onNote: (value: string) => void;
    onSave: () => void;
}) {
    return (
        <>
            <header>
                <p className={`finding-severity finding-severity--${finding.severity}`}>
                    {finding.severity} severity
                </p>
                <h3>{finding.title}</h3>
                <p>
                    {finding.family} · {finding.confidence} confidence · {finding.effective_status}
                </p>
            </header>
            <p>{finding.explanation}</p>
            <dl className="finding-facts">
                <div>
                    <dt>Affected subjects</dt>
                    <dd className="mono">{finding.subject_keys.join(", ")}</dd>
                </div>
                <div>
                    <dt>Source</dt>
                    <dd>
                        {finding.relative_path
                            ? `${finding.relative_path}:${finding.line ?? 1}`
                            : "Group-level evidence"}
                    </dd>
                </div>
                <div>
                    <dt>Metric evidence</dt>
                    <dd>{formatEvidence(finding.metric_evidence)}</dd>
                </div>
                <div>
                    <dt>Threshold</dt>
                    <dd>{formatEvidence(finding.threshold_evidence)}</dd>
                </div>
                <div>
                    <dt>First / last seen</dt>
                    <dd className="mono">
                        {finding.first_seen_snapshot_id.slice(0, 12)} /{" "}
                        {finding.last_seen_snapshot_id.slice(0, 12)}
                    </dd>
                </div>
                <div>
                    <dt>Rule</dt>
                    <dd className="mono">
                        {finding.rule_id} v{finding.rule_version}
                    </dd>
                </div>
                <div>
                    <dt>Suggested action</dt>
                    <dd>{finding.suggested_action}</dd>
                </div>
            </dl>
            {source ? (
                <pre className="source-code" aria-label="Finding source evidence">
                    <code>
                        {source.lines.map((line) => (
                            <span className="source-line" key={line.number}>
                                <span className="source-line__number">{line.number}</span>
                                <span>{line.text}</span>
                            </span>
                        ))}
                    </code>
                </pre>
            ) : null}
            <section className="review-editor" aria-labelledby="review-editor-heading">
                <h4 id="review-editor-heading">Review decision</h4>
                <div className="review-fields">
                    <Filter
                        label="Review status"
                        value={reviewStatus}
                        onChange={(value) => onStatus(value as ReviewStatus)}
                    >
                        <option value="new">New</option>
                        <option value="reviewed">Reviewed</option>
                        <option value="needs-action">Needs action</option>
                        <option value="accepted">Accepted</option>
                        <option value="dismissed">Dismissed</option>
                    </Filter>
                    <Filter label="Reason" value={reasonCode} onChange={onReason}>
                        <option value="">No reason selected</option>
                        <option value="intentional-design">Intentional design</option>
                        <option value="false-positive">False positive</option>
                        <option value="accepted-risk">Accepted risk</option>
                        <option value="planned-refactor">Planned refactor</option>
                        <option value="needs-investigation">Needs investigation</option>
                        <option value="other">Other</option>
                    </Filter>
                </div>
                <label className="note-field">
                    Local note
                    <textarea
                        value={note}
                        maxLength={2000}
                        rows={5}
                        onChange={(event) => onNote(event.target.value)}
                    />
                    <span>{note.length.toLocaleString()} / 2,000 plain-text characters</span>
                </label>
                <div className="review-actions">
                    <button
                        className="button button--primary"
                        type="button"
                        disabled={!dirty || saving}
                        onClick={onSave}
                    >
                        {saving ? "Saving…" : "Save review"}
                    </button>
                    <span role="status">
                        {dirty ? "Unsaved changes" : saveMessage || "Review is saved"}
                    </span>
                </div>
            </section>
            <section className="finding-history">
                <h4>Review history</h4>
                {history?.items.length ? (
                    <ol>
                        {history.items.map((event) => (
                            <li key={event.event_id}>
                                <strong>{event.event_type}</strong>
                                <span>
                                    {event.review_status ? ` · ${event.review_status}` : ""} ·{" "}
                                    {event.event_at}
                                </span>
                            </li>
                        ))}
                    </ol>
                ) : (
                    <p>No history events are available.</p>
                )}
            </section>
        </>
    );
}

function formatEvidence(items: Array<[string, number]>): string {
    return items.length
        ? items.map(([name, value]) => `${name.replaceAll("_", " ")}: ${value}`).join(", ")
        : "Not applicable";
}
