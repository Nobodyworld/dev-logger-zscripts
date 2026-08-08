import { useEffect, useRef, useState } from "react";

import {
    ApiError,
    cancelAnalysis,
    getAnalysis,
    getComparisonSnapshots,
    getOverview,
    listRepositories,
    resolveRepositoryScope,
    startAnalysis,
} from "./api";
import { RepositoryControls } from "./components/RepositoryControls";
import { RepositoryHeader } from "./components/RepositoryHeader";
import { CompareView } from "./components/CompareView";
import { HandoffView } from "./components/HandoffView";
import { OverviewView } from "./components/OverviewView";
import { FindingsView } from "./components/FindingsView";
import { RelationshipsView } from "./components/RelationshipsView";
import { Sidebar } from "./components/Sidebar";
import { SymbolsView } from "./components/SymbolsView";
import type {
    AnalysisJob,
    Overview,
    Repository,
    RepositoryScopeResolution,
    SnapshotChoice,
    ViewName,
} from "./types";

export function App() {
    const [repositories, setRepositories] = useState<Repository[]>([]);
    const [repositoryPath, setRepositoryPath] = useState("");
    const [job, setJob] = useState<AnalysisJob | null>(null);
    const [overview, setOverview] = useState<Overview | null>(null);
    const [snapshots, setSnapshots] = useState<SnapshotChoice[]>([]);
    const [activeView, setActiveView] = useState<ViewName>("overview");
    const [findingPreset, setFindingPreset] = useState<string>("");
    const [navigationOpen, setNavigationOpen] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [pendingScope, setPendingScope] = useState<RepositoryScopeResolution | null>(null);
    const [scopeResolving, setScopeResolving] = useState(false);
    const pollGeneration = useRef(0);
    const scopeGeneration = useRef(0);
    const scopeAbortController = useRef<AbortController | null>(null);
    const scopeRequestInFlight = useRef(false);
    const analysisStarting = useRef(false);
    const mounted = useRef(true);

    useEffect(() => {
        let active = true;
        listRepositories()
            .then((items) => {
                if (active) setRepositories(items);
            })
            .catch((caught: unknown) => {
                if (active)
                    setError(messageFrom(caught, "Recent repositories could not be loaded."));
            });
        return () => {
            active = false;
            mounted.current = false;
            scopeGeneration.current += 1;
            scopeAbortController.current?.abort();
            pollGeneration.current += 1;
        };
    }, []);

    const loadSnapshot = async (snapshotId: string, repositoryId: string) => {
        setError(null);
        try {
            const [nextOverview, snapshotResult] = await Promise.all([
                getOverview(snapshotId),
                getComparisonSnapshots(repositoryId),
            ]);
            setOverview(nextOverview);
            setSnapshots(snapshotResult.snapshots);
        } catch (caught) {
            setError(messageFrom(caught, "The completed snapshot could not be opened."));
        }
    };

    const openRecentRepository = async (repositoryId: string) => {
        invalidatePendingScope();
        setError(null);
        try {
            const snapshotResult = await getComparisonSnapshots(repositoryId);
            const nextSnapshots = snapshotResult.snapshots;
            if (nextSnapshots.length === 0) {
                setError("This repository has no completed snapshots.");
                return;
            }
            const nextOverview = await getOverview(nextSnapshots[0].snapshot_id);
            setSnapshots(nextSnapshots);
            setOverview(nextOverview);
            setJob(null);
            setActiveView("overview");
        } catch (caught) {
            setError(messageFrom(caught, "The recent repository could not be opened."));
        }
    };

    const beginAnalysis = async (analysisRoot: string) => {
        if (analysisStarting.current) return;
        analysisStarting.current = true;
        setError(null);
        setOverview(null);
        setSnapshots([]);
        pollGeneration.current += 1;
        const generation = pollGeneration.current;
        try {
            let nextJob = await startAnalysis({ repository_path: analysisRoot });
            analysisStarting.current = false;
            setJob(nextJob);
            while (nextJob.state === "started" && generation === pollGeneration.current) {
                await wait(300);
                nextJob = await getAnalysis(nextJob.analysis_id);
                setJob(nextJob);
            }
            if (generation !== pollGeneration.current) return;
            if (nextJob.state === "completed" && nextJob.snapshot_id && nextJob.repository_id) {
                const [nextOverview, snapshotResult, nextRepositories] = await Promise.all([
                    getOverview(nextJob.snapshot_id),
                    getComparisonSnapshots(nextJob.repository_id),
                    listRepositories(),
                ]);
                setOverview(nextOverview);
                setSnapshots(snapshotResult.snapshots);
                setRepositories(nextRepositories);
                setActiveView("overview");
            } else if (nextJob.state === "failed" || nextJob.state === "cancelled") {
                setError(nextJob.message ?? `Analysis ${nextJob.state}.`);
            }
        } catch (caught) {
            setError(messageFrom(caught, "The repository scan could not be started."));
        } finally {
            analysisStarting.current = false;
        }
    };

    const invalidatePendingScope = () => {
        scopeGeneration.current += 1;
        scopeAbortController.current?.abort();
        scopeAbortController.current = null;
        scopeRequestInFlight.current = false;
        setScopeResolving(false);
        setPendingScope(null);
    };

    const changeRepositoryPath = (value: string) => {
        setRepositoryPath(value);
        invalidatePendingScope();
    };

    const scanRepository = async () => {
        const submittedPath = repositoryPath.trim();
        if (!submittedPath || scopeRequestInFlight.current || analysisStarting.current) return;
        invalidatePendingScope();
        const generation = scopeGeneration.current;
        const controller = new AbortController();
        scopeAbortController.current = controller;
        scopeRequestInFlight.current = true;
        setScopeResolving(true);
        setError(null);
        setJob(null);
        try {
            const scope = await resolveRepositoryScope(submittedPath, controller.signal);
            if (generation !== scopeGeneration.current || !mounted.current) return;
            scopeRequestInFlight.current = false;
            setScopeResolving(false);
            scopeAbortController.current = null;
            if (scope.confirmation_required) {
                setPendingScope(scope);
                return;
            }
            await beginAnalysis(scope.analysis_root);
        } catch (caught) {
            if (generation !== scopeGeneration.current || !mounted.current || isAbortError(caught))
                return;
            scopeRequestInFlight.current = false;
            setScopeResolving(false);
            scopeAbortController.current = null;
            setError(messageFrom(caught, "The repository path could not be resolved."));
        }
    };

    const confirmScope = async () => {
        const scope = pendingScope;
        if (!scope || analysisStarting.current) return;
        setPendingScope(null);
        await beginAnalysis(scope.analysis_root);
    };

    const cancelScan = async () => {
        if (!job || job.state !== "started") return;
        try {
            setJob(await cancelAnalysis(job.analysis_id));
        } catch (caught) {
            setError(messageFrom(caught, "The scan could not be cancelled."));
        }
    };

    return (
        <div className="app-shell">
            <Sidebar
                activeView={activeView}
                open={navigationOpen}
                onOpen={() => setNavigationOpen(true)}
                onClose={() => setNavigationOpen(false)}
                onSelect={(view) => {
                    if (view === "findings") setFindingPreset("");
                    setActiveView(view);
                }}
            />
            <main className="workspace">
                <header className="topbar">
                    <span>Repository Review</span>
                </header>
                <RepositoryControls
                    repositoryPath={repositoryPath}
                    repositories={repositories}
                    job={job}
                    pendingScope={pendingScope}
                    scopeResolving={scopeResolving}
                    onPathChange={changeRepositoryPath}
                    onRecentRepository={openRecentRepository}
                    onScan={scanRepository}
                    onCancel={cancelScan}
                    onScopeConfirm={confirmScope}
                    onScopeCancel={invalidatePendingScope}
                />
                {error ? (
                    <p className="global-error" role="alert">
                        {error}
                    </p>
                ) : null}
                {overview ? (
                    <>
                        <RepositoryHeader
                            overview={overview}
                            snapshots={snapshots}
                            onSnapshotChange={(snapshotId) =>
                                loadSnapshot(snapshotId, overview.repository.repository_id)
                            }
                        />
                        {activeView === "overview" ? (
                            <OverviewView
                                overview={overview}
                                onOpenFindings={(preset) => {
                                    setFindingPreset(preset);
                                    setActiveView("findings");
                                }}
                            />
                        ) : null}
                        {activeView === "symbols" ? (
                            <SymbolsView
                                key={overview.snapshot.snapshot_id}
                                snapshotId={overview.snapshot.snapshot_id}
                            />
                        ) : null}
                        {activeView === "relationships" ? (
                            <RelationshipsView
                                key={overview.snapshot.snapshot_id}
                                snapshotId={overview.snapshot.snapshot_id}
                            />
                        ) : null}
                        {activeView === "findings" ? (
                            <FindingsView
                                key={overview.snapshot.snapshot_id}
                                snapshotId={overview.snapshot.snapshot_id}
                                preset={findingPreset}
                            />
                        ) : null}
                        {activeView === "compare" ? (
                            <CompareView
                                key={`${overview.repository.repository_id}:${overview.snapshot.snapshot_id}`}
                                repositoryId={overview.repository.repository_id}
                                targetSnapshotId={overview.snapshot.snapshot_id}
                            />
                        ) : null}
                        {activeView === "handoff" ? (
                            <HandoffView
                                key={`${overview.repository.repository_id}:${overview.snapshot.snapshot_id}`}
                                repositoryId={overview.repository.repository_id}
                                targetSnapshotId={overview.snapshot.snapshot_id}
                            />
                        ) : null}
                    </>
                ) : (
                    <EmptyState hasJob={job?.state === "started"} />
                )}
                <footer className="mobile-beta">PUBLIC BETA — ACTIVE DEVELOPMENT</footer>
            </main>
        </div>
    );
}

function EmptyState({ hasJob }: { hasJob: boolean }) {
    return (
        <section className="empty-state">
            <h1>{hasJob ? "Scanning repository" : "Select a local Python repository"}</h1>
            <p>
                {hasJob
                    ? "Static metadata is being read without importing or executing the project."
                    : "Enter a path on this machine to create a read-only, metadata-only local snapshot."}
            </p>
        </section>
    );
}

function messageFrom(error: unknown, fallback: string): string {
    return error instanceof ApiError ? error.message : fallback;
}

function isAbortError(error: unknown): boolean {
    return error instanceof DOMException && error.name === "AbortError";
}

function wait(milliseconds: number): Promise<void> {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}
