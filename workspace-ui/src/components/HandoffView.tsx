import { useEffect, useMemo, useRef, useState } from "react";

import {
    ApiError,
    getComparisonItems,
    getComparisonSnapshots,
    getComparisonSummary,
    getFindings,
    getSavedHandoff,
    listHandoffs,
    previewHandoff,
    saveHandoff,
} from "../api";
import type {
    ComparisonItem,
    ComparisonSection,
    ComparisonSnapshot,
    ComparisonSummary,
    Finding,
    HandoffPreview,
    HandoffSelectionRequest,
    SavedHandoff,
} from "../types";

interface HandoffViewProps {
    repositoryId: string;
    targetSnapshotId: string;
}

const SELECTABLE_SECTIONS = [
    "comparison",
    "files",
    "symbols",
    "relationships",
    "cycles",
    "metrics",
    "findings",
    "task-objective",
] as const;

const DELTA_SECTIONS: ComparisonSection[] = [
    "files",
    "symbols",
    "relationships",
    "cycles",
    "metrics",
];

export function HandoffView({ repositoryId, targetSnapshotId }: HandoffViewProps) {
    const [snapshots, setSnapshots] = useState<ComparisonSnapshot[]>([]);
    const [baselineId, setBaselineId] = useState("");
    const [targetId, setTargetId] = useState(targetSnapshotId);
    const [summary, setSummary] = useState<ComparisonSummary | null>(null);
    const [section, setSection] = useState<ComparisonSection>("files");
    const [items, setItems] = useState<ComparisonItem[]>([]);
    const [findings, setFindings] = useState<Finding[]>([]);
    const [selectedDeltaIds, setSelectedDeltaIds] = useState<Set<string>>(new Set());
    const [selectedCycleIds, setSelectedCycleIds] = useState<Set<string>>(new Set());
    const [selectedFindingIds, setSelectedFindingIds] = useState<Set<string>>(new Set());
    const [noteFindingIds, setNoteFindingIds] = useState<Set<string>>(new Set());
    const [enabledSections, setEnabledSections] = useState<Set<string>>(
        new Set(["comparison", "files", "findings", "task-objective"]),
    );
    const [includeReviewStatus, setIncludeReviewStatus] = useState(false);
    const [objective, setObjective] = useState("");
    const [preview, setPreview] = useState<HandoffPreview | null>(null);
    const [previewKey, setPreviewKey] = useState<string | null>(null);
    const [savedPreview, setSavedPreview] = useState<HandoffPreview | null>(null);
    const [rehydratedComparisonId, setRehydratedComparisonId] = useState<string | null | undefined>(
        undefined,
    );
    const [pendingRehydration, setPendingRehydration] = useState<SavedHandoff | null>(null);
    const [saved, setSaved] = useState<SavedHandoff[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionBusy, setActionBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const loadGeneration = useRef(0);
    const actionGeneration = useRef(0);
    const loadedPair = useRef("");
    const normalPairChange = useRef(false);

    useEffect(() => {
        const controller = new AbortController();
        const generation = ++loadGeneration.current;
        loadedPair.current = "";
        void (async () => {
            setSelectedDeltaIds(new Set());
            setSelectedCycleIds(new Set());
            setSelectedFindingIds(new Set());
            setNoteFindingIds(new Set());
            setPreview(null);
            setPreviewKey(null);
            setSavedPreview(null);
            setPendingRehydration(null);
            setRehydratedComparisonId(undefined);
            setLoading(true);
            setError(null);
            try {
                const [snapshotResult, handoffs] = await Promise.all([
                    getComparisonSnapshots(repositoryId, controller.signal),
                    listHandoffs(repositoryId, controller.signal),
                ]);
                if (generation !== loadGeneration.current) return;
                setSnapshots(snapshotResult.snapshots);
                setSaved(handoffs);
                const targetIndex = Math.max(
                    snapshotResult.snapshots.findIndex(
                        (item) => item.snapshot_id === targetSnapshotId,
                    ),
                    0,
                );
                const nextTarget = snapshotResult.snapshots[targetIndex]?.snapshot_id ?? "";
                setTargetId(nextTarget);
                setBaselineId(snapshotResult.snapshots[targetIndex + 1]?.snapshot_id ?? nextTarget);
                setLoading(false);
            } catch (caught) {
                if (controller.signal.aborted || generation !== loadGeneration.current) return;
                setLoading(false);
                setError(messageFrom(caught, "Handoff snapshots could not be loaded."));
            }
        })();
        return () => {
            controller.abort();
            loadGeneration.current += 1;
            actionGeneration.current += 1;
        };
    }, [repositoryId, targetSnapshotId]);

    useEffect(() => {
        if (!baselineId || !targetId) return;
        const controller = new AbortController();
        const generation = ++loadGeneration.current;
        const pairKey = `${baselineId}\0${targetId}`;
        const pending =
            pendingRehydration !== null &&
            (pendingRehydration.selection.baseline_snapshot_id ??
                pendingRehydration.selection.target_snapshot_id) === baselineId &&
            pendingRehydration.selection.target_snapshot_id === targetId
                ? pendingRehydration
                : null;
        const pairChanged = loadedPair.current !== pairKey;
        loadedPair.current = pairKey;
        void (async () => {
            setLoading(true);
            setError(null);
            setItems([]);
            setFindings([]);
            setSummary(null);
            if (pairChanged && pending === null) {
                setSelectedDeltaIds(new Set());
                setSelectedCycleIds(new Set());
                setPreview(null);
                setPreviewKey(null);
                setSavedPreview(null);
                setRehydratedComparisonId(undefined);
                actionGeneration.current += 1;
                if (normalPairChange.current) {
                    setNotice(
                        "Snapshot pair changed; comparison selections and preview were reset.",
                    );
                }
                normalPairChange.current = false;
            }
            try {
                const [nextSummary, evidence] = await Promise.all([
                    getComparisonSummary(baselineId, targetId, controller.signal),
                    section === "findings"
                        ? getFindings(
                              targetId,
                              {
                                  search: "",
                                  family: "",
                                  severity: "",
                                  confidence: "",
                                  effectiveStatus: "",
                                  evidenceState: "",
                                  sort: "severity",
                                  direction: "desc",
                                  page: 1,
                                  pageSize: 50,
                              },
                              controller.signal,
                          )
                        : getComparisonItems(
                              {
                                  baselineSnapshotId: baselineId,
                                  targetSnapshotId: targetId,
                                  section,
                                  changeType: "",
                                  search: "",
                                  sort: "logical_key",
                                  direction: "asc",
                                  page: 1,
                                  pageSize: 50,
                              },
                              controller.signal,
                          ),
                ]);
                if (generation !== loadGeneration.current) return;
                if (
                    pending !== null &&
                    (nextSummary.identity.baseline_snapshot_id !== baselineId ||
                        nextSummary.identity.target_snapshot_id !==
                            pending.selection.target_snapshot_id ||
                        (pending.selection.comparison_id !== null &&
                            nextSummary.identity.comparison_id !== pending.selection.comparison_id))
                ) {
                    setPendingRehydration(null);
                    setActionBusy(false);
                    setError("Saved handoff comparison no longer matches the selected snapshots.");
                    return;
                }
                setSummary(nextSummary);
                if (section === "findings" && "supported" in evidence) {
                    setFindings(evidence.items as Finding[]);
                    setItems([]);
                } else if ("section" in evidence) {
                    setItems(evidence.items);
                }
                if (pending !== null) {
                    setEnabledSections(new Set(pending.selection.enabled_sections));
                    setSelectedDeltaIds(new Set(pending.selection.selected_delta_ids));
                    setSelectedCycleIds(new Set(pending.selection.selected_cycle_ids));
                    setSelectedFindingIds(new Set(pending.selection.selected_finding_ids));
                    setNoteFindingIds(new Set(pending.selection.explicit_review_note_finding_ids));
                    setIncludeReviewStatus(pending.selection.include_current_review_status);
                    setObjective(pending.selection.task_objective);
                    setRehydratedComparisonId(pending.selection.comparison_id);
                    setSavedPreview(previewFromSaved(pending));
                    setPreview(null);
                    setPreviewKey(null);
                    setPendingRehydration(null);
                    setActionBusy(false);
                    setNotice("Saved handoff reopened.");
                }
                setLoading(false);
            } catch (caught) {
                if (controller.signal.aborted || generation !== loadGeneration.current) return;
                setLoading(false);
                if (pending !== null) {
                    setPendingRehydration(null);
                    setSavedPreview(null);
                    setActionBusy(false);
                }
                setError(messageFrom(caught, "Selectable handoff evidence could not be loaded."));
            }
        })();
        return () => controller.abort();
    }, [baselineId, pendingRehydration, section, targetId]);

    const activeComparisonId =
        summary?.identity.baseline_snapshot_id === baselineId &&
        summary.identity.target_snapshot_id === targetId
            ? summary.identity.comparison_id
            : null;

    const selection = useMemo<HandoffSelectionRequest>(
        () => ({
            target_snapshot_id: targetId,
            baseline_snapshot_id: baselineId || null,
            comparison_id:
                rehydratedComparisonId !== undefined ? rehydratedComparisonId : activeComparisonId,
            enabled_sections: [...enabledSections].sort(),
            selected_delta_ids: [...selectedDeltaIds].sort(),
            selected_finding_ids: [...selectedFindingIds].sort(),
            selected_cycle_ids: [...selectedCycleIds].sort(),
            include_current_review_status: includeReviewStatus,
            explicit_review_note_finding_ids: [...noteFindingIds].sort(),
            task_objective: objective,
        }),
        [
            baselineId,
            enabledSections,
            includeReviewStatus,
            noteFindingIds,
            objective,
            selectedDeltaIds,
            selectedCycleIds,
            selectedFindingIds,
            activeComparisonId,
            rehydratedComparisonId,
            targetId,
        ],
    );
    const selectionKey = useMemo(() => selectionIdentity(selection), [selection]);
    const displayedPreview = savedPreview ?? (previewKey === selectionKey ? preview : null);

    const buildPreview = async () => {
        const generation = ++actionGeneration.current;
        setActionBusy(true);
        setError(null);
        setNotice(null);
        setPreview(null);
        setPreviewKey(null);
        setSavedPreview(null);
        setPendingRehydration(null);
        try {
            const result = await previewHandoff(selection);
            if (generation !== actionGeneration.current) return;
            setPreview(result);
            setPreviewKey(selectionKey);
            setNotice("Deterministic preview updated.");
        } catch (caught) {
            if (generation !== actionGeneration.current) return;
            setError(messageFrom(caught, "The handoff preview could not be rendered."));
        } finally {
            if (generation === actionGeneration.current) setActionBusy(false);
        }
    };

    const saveCurrent = async () => {
        const generation = ++actionGeneration.current;
        setActionBusy(true);
        setError(null);
        setNotice(null);
        try {
            const result = await saveHandoff(selection);
            if (generation !== actionGeneration.current) return;
            setSaved((current) => [
                result,
                ...current.filter((item) => item.handoff_id !== result.handoff_id),
            ]);
            setSavedPreview(previewFromSaved(result));
            setPreview(null);
            setPreviewKey(null);
            setNotice("Handoff saved locally.");
        } catch (caught) {
            if (generation !== actionGeneration.current) return;
            setError(messageFrom(caught, "The handoff could not be saved locally."));
        } finally {
            if (generation === actionGeneration.current) setActionBusy(false);
        }
    };

    const reopen = async (handoffId: string) => {
        const generation = ++actionGeneration.current;
        setActionBusy(true);
        setError(null);
        setNotice(null);
        setSavedPreview(null);
        setPreview(null);
        setPreviewKey(null);
        try {
            const result = await getSavedHandoff(handoffId);
            if (generation !== actionGeneration.current) return;
            setPendingRehydration(result);
            setTargetId(result.selection.target_snapshot_id);
            setBaselineId(
                result.selection.baseline_snapshot_id ?? result.selection.target_snapshot_id,
            );
        } catch (caught) {
            if (generation !== actionGeneration.current) return;
            setPendingRehydration(null);
            setError(messageFrom(caught, "The saved handoff could not be reopened."));
            setActionBusy(false);
        }
    };

    const copyMarkdown = async () => {
        if (!displayedPreview) return;
        try {
            await navigator.clipboard.writeText(displayedPreview.markdown);
            setNotice("Markdown copied to the clipboard.");
            setError(null);
        } catch {
            setError("Clipboard permission was denied. Use the Markdown download instead.");
        }
    };

    const changeSnapshotPair = (kind: "baseline" | "target", value: string) => {
        normalPairChange.current =
            selectedDeltaIds.size > 0 ||
            selectedCycleIds.size > 0 ||
            preview !== null ||
            savedPreview !== null;
        actionGeneration.current += 1;
        setPendingRehydration(null);
        setRehydratedComparisonId(undefined);
        setSavedPreview(null);
        setPreview(null);
        setPreviewKey(null);
        setSummary(null);
        if (kind === "baseline") setBaselineId(value);
        else setTargetId(value);
    };

    return (
        <section className="review-view handoff-view" aria-labelledby="handoff-title">
            <div className="view-heading">
                <div>
                    <p className="eyebrow">Local bounded evidence package</p>
                    <h1 id="handoff-title">Handoff</h1>
                    <p>
                        Preview, copy, download, or save deterministic Markdown and JSON. Nothing is
                        sent off this machine.
                    </p>
                </div>
                <span className="status-chip">Format 2 · local only</span>
            </div>

            <div className="snapshot-pair">
                <label>
                    Baseline
                    <select
                        value={baselineId}
                        onChange={(event) => changeSnapshotPair("baseline", event.target.value)}
                    >
                        {snapshots.map((snapshot) => (
                            <option key={snapshot.snapshot_id} value={snapshot.snapshot_id}>
                                {snapshotOptionLabel(snapshot)}
                            </option>
                        ))}
                    </select>
                </label>
                <label>
                    Target
                    <select
                        value={targetId}
                        onChange={(event) => changeSnapshotPair("target", event.target.value)}
                    >
                        {snapshots.map((snapshot) => (
                            <option key={snapshot.snapshot_id} value={snapshot.snapshot_id}>
                                {snapshotOptionLabel(snapshot)}
                            </option>
                        ))}
                    </select>
                </label>
            </div>

            <div className="handoff-builder">
                <div className="handoff-inputs">
                    <fieldset>
                        <legend>Included sections</legend>
                        <div className="checkbox-grid">
                            {SELECTABLE_SECTIONS.map((item) => (
                                <label key={item}>
                                    <input
                                        type="checkbox"
                                        checked={enabledSections.has(item)}
                                        onChange={() =>
                                            setEnabledSections(toggleSet(enabledSections, item))
                                        }
                                    />
                                    {item.replaceAll("-", " ")}
                                </label>
                            ))}
                        </div>
                    </fieldset>

                    <label>
                        Task objective
                        <textarea
                            value={objective}
                            maxLength={4000}
                            rows={5}
                            onChange={(event) => {
                                setObjective(event.target.value);
                                setPreview(null);
                                setPreviewKey(null);
                            }}
                            placeholder="Plain-text objective for the next reviewer"
                        />
                        <small>{objective.length} / 4,000 characters</small>
                    </label>

                    <div className="budget-panel">
                        <strong>Versioned budgets</strong>
                        <span>8 sections · 50 items per section · 50 findings</span>
                        <span>20 explicit notes · 1,000 characters per note</span>
                        <span>100,000 Markdown characters · 500,000 JSON bytes</span>
                    </div>

                    <div
                        className="section-tabs"
                        role="tablist"
                        aria-label="Handoff evidence section"
                    >
                        {[...DELTA_SECTIONS, "findings" as const].map((item) => (
                            <button
                                key={item}
                                type="button"
                                role="tab"
                                aria-selected={section === item}
                                className={
                                    section === item
                                        ? "section-tab section-tab--active"
                                        : "section-tab"
                                }
                                onClick={() => setSection(item)}
                            >
                                {item}
                            </button>
                        ))}
                    </div>

                    {loading ? <p className="loading-state">Loading selectable evidence…</p> : null}
                    {section !== "findings" ? (
                        <div
                            className="selection-list"
                            aria-label={`${section} handoff selections`}
                        >
                            {items.map((item) => (
                                <label key={item.delta_id}>
                                    <input
                                        type="checkbox"
                                        checked={selectedDeltaIds.has(item.delta_id)}
                                        onChange={() =>
                                            setSelectedDeltaIds(
                                                toggleSet(selectedDeltaIds, item.delta_id),
                                            )
                                        }
                                    />
                                    <span>
                                        <strong>{item.label}</strong>
                                        <small>{item.change_type}</small>
                                    </span>
                                </label>
                            ))}
                            {!loading && items.length === 0 ? <p>No selectable changes.</p> : null}
                        </div>
                    ) : (
                        <>
                            <label className="review-status-toggle">
                                <input
                                    type="checkbox"
                                    checked={includeReviewStatus}
                                    onChange={(event) =>
                                        setIncludeReviewStatus(event.target.checked)
                                    }
                                />
                                Include current lifecycle and review status
                            </label>
                            <div className="selection-list" aria-label="Finding handoff selections">
                                {findings.map((finding) => {
                                    const selectedFinding = selectedFindingIds.has(
                                        finding.finding_id,
                                    );
                                    return (
                                        <div className="finding-selection" key={finding.finding_id}>
                                            <label>
                                                <input
                                                    type="checkbox"
                                                    checked={selectedFinding}
                                                    onChange={() =>
                                                        setSelectedFindingIds(
                                                            toggleSet(
                                                                selectedFindingIds,
                                                                finding.finding_id,
                                                            ),
                                                        )
                                                    }
                                                />
                                                <span>
                                                    <strong>{finding.title}</strong>
                                                    <small>
                                                        occurrence at target · current{" "}
                                                        {finding.effective_status}
                                                    </small>
                                                </span>
                                            </label>
                                            <label className="note-opt-in">
                                                <input
                                                    type="checkbox"
                                                    disabled={!selectedFinding}
                                                    checked={noteFindingIds.has(finding.finding_id)}
                                                    onChange={() =>
                                                        setNoteFindingIds(
                                                            toggleSet(
                                                                noteFindingIds,
                                                                finding.finding_id,
                                                            ),
                                                        )
                                                    }
                                                />
                                                Explicitly include this review note
                                            </label>
                                        </div>
                                    );
                                })}
                            </div>
                        </>
                    )}

                    <div className="handoff-actions">
                        <button
                            type="button"
                            className="primary-button"
                            disabled={!targetId}
                            onClick={buildPreview}
                        >
                            Preview handoff
                        </button>
                        <button
                            type="button"
                            className="secondary-button"
                            disabled={actionBusy || !targetId}
                            onClick={saveCurrent}
                        >
                            Save locally
                        </button>
                    </div>
                </div>

                <div className="handoff-preview">
                    <div className="handoff-preview__heading">
                        <h2>Markdown preview</h2>
                        {savedPreview ? <span>Immutable saved output</span> : null}
                        {displayedPreview ? (
                            <>
                                <span>
                                    {displayedPreview.markdown_character_count.toLocaleString()}{" "}
                                    chars · {displayedPreview.json_byte_count.toLocaleString()}{" "}
                                    bytes
                                </span>
                                <small>Digest {displayedPreview.rendered_digest}</small>
                            </>
                        ) : null}
                    </div>
                    {displayedPreview?.truncated ? (
                        <p className="notice-banner notice-banner--warning" role="status">
                            Truncated:{" "}
                            {Object.entries(displayedPreview.omitted_counts)
                                .map(([name, count]) => `${count} ${name}`)
                                .join(", ")}
                        </p>
                    ) : null}
                    {displayedPreview ? (
                        <>
                            <pre className="markdown-preview">{displayedPreview.markdown}</pre>
                            <div className="handoff-actions">
                                <button
                                    type="button"
                                    className="secondary-button"
                                    onClick={copyMarkdown}
                                >
                                    Copy Markdown
                                </button>
                                <button
                                    type="button"
                                    className="secondary-button"
                                    onClick={() =>
                                        downloadBlob(
                                            displayedPreview.markdown,
                                            "repository-handoff.md",
                                            "text/markdown",
                                        )
                                    }
                                >
                                    Download Markdown
                                </button>
                                <button
                                    type="button"
                                    className="secondary-button"
                                    onClick={() =>
                                        downloadBlob(
                                            displayedPreview.normalized_json,
                                            "repository-handoff.json",
                                            "application/json",
                                        )
                                    }
                                >
                                    Download JSON
                                </button>
                            </div>
                        </>
                    ) : (
                        <p className="empty-panel">
                            Select evidence and request a preview. Review notes remain excluded
                            unless individually enabled.
                        </p>
                    )}
                </div>
            </div>

            {error ? (
                <p className="global-error" role="alert">
                    {error}
                </p>
            ) : null}
            {notice ? (
                <p className="notice-banner" role="status">
                    {notice}
                </p>
            ) : null}

            <section className="saved-handoffs" aria-labelledby="saved-handoffs-title">
                <h2 id="saved-handoffs-title">Saved locally</h2>
                {saved.length ? (
                    saved.map((item) => (
                        <button
                            type="button"
                            key={item.handoff_id}
                            className="saved-handoff-row"
                            onClick={() => reopen(item.handoff_id)}
                        >
                            <strong>{item.task_objective || "Untitled handoff"}</strong>
                            <span>{item.created_at}</span>
                            <small>{item.rendered_digest.slice(0, 16)}</small>
                        </button>
                    ))
                ) : (
                    <p>No saved handoffs for this repository.</p>
                )}
            </section>
        </section>
    );
}

function toggleSet(values: Set<string>, value: string): Set<string> {
    const next = new Set(values);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return next;
}

function snapshotOptionLabel(snapshot: ComparisonSnapshot): string {
    const observation = snapshot.observed_state_known
        ? `${snapshot.branch ?? "detached"} · ${snapshot.git_sha?.slice(0, 8) ?? "no SHA"}`
        : "observation unknown";
    return `${snapshot.completed_at} · ${observation}`;
}

function selectionIdentity(selection: HandoffSelectionRequest): string {
    return JSON.stringify({
        target_snapshot_id: selection.target_snapshot_id,
        baseline_snapshot_id: selection.baseline_snapshot_id,
        comparison_id: selection.comparison_id,
        enabled_sections: selection.enabled_sections,
        selected_delta_ids: selection.selected_delta_ids,
        selected_finding_ids: selection.selected_finding_ids,
        selected_cycle_ids: selection.selected_cycle_ids,
        include_current_review_status: selection.include_current_review_status,
        explicit_review_note_finding_ids: selection.explicit_review_note_finding_ids,
        task_objective: selection.task_objective,
    });
}

function previewFromSaved(saved: SavedHandoff): HandoffPreview {
    const payload = saved.json_payload ?? {};
    const warnings = Array.isArray(payload.analysis_gaps)
        ? payload.analysis_gaps.map((item) => String(item))
        : [];
    const omitted =
        payload.omitted_counts && typeof payload.omitted_counts === "object"
            ? (payload.omitted_counts as Record<string, number>)
            : {};
    return {
        handoff_format_version: saved.format_version,
        markdown: saved.markdown ?? "",
        normalized_json: saved.normalized_json ?? `${JSON.stringify(payload, null, 2)}\n`,
        json_payload: payload,
        rendered_digest: saved.rendered_digest,
        truncated: payload.truncated === true,
        omitted_counts: omitted,
        warnings,
        markdown_character_count: saved.markdown_character_count,
        json_byte_count: saved.json_byte_count,
    };
}

function downloadBlob(content: string, filename: string, mediaType: string) {
    const url = URL.createObjectURL(new Blob([content], { type: mediaType }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
}

function messageFrom(error: unknown, fallback: string): string {
    return error instanceof ApiError ? error.message : fallback;
}
