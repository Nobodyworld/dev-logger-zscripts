import { useEffect, useRef, useState } from "react";

import {
    ApiError,
    cancelAnalysis,
    getAnalysis,
    getOverview,
    listRepositories,
    listSnapshots,
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
import type { AnalysisJob, Overview, Repository, Snapshot, ViewName } from "./types";

export function App() {
    const [repositories, setRepositories] = useState<Repository[]>([]);
    const [repositoryPath, setRepositoryPath] = useState("");
    const [job, setJob] = useState<AnalysisJob | null>(null);
    const [overview, setOverview] = useState<Overview | null>(null);
    const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
    const [activeView, setActiveView] = useState<ViewName>("overview");
    const [findingPreset, setFindingPreset] = useState<string>("");
    const [navigationOpen, setNavigationOpen] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const pollGeneration = useRef(0);

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
            pollGeneration.current += 1;
        };
    }, []);

    const loadSnapshot = async (snapshotId: string, repositoryId: string) => {
        setError(null);
        try {
            const [nextOverview, nextSnapshots] = await Promise.all([
                getOverview(snapshotId),
                listSnapshots(repositoryId),
            ]);
            setOverview(nextOverview);
            setSnapshots(nextSnapshots);
        } catch (caught) {
            setError(messageFrom(caught, "The completed snapshot could not be opened."));
        }
    };

    const openRecentRepository = async (repositoryId: string) => {
        setError(null);
        try {
            const nextSnapshots = await listSnapshots(repositoryId);
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

    const scanRepository = async () => {
        if (!repositoryPath.trim()) return;
        setError(null);
        setOverview(null);
        setSnapshots([]);
        pollGeneration.current += 1;
        const generation = pollGeneration.current;
        try {
            let nextJob = await startAnalysis({ repository_path: repositoryPath.trim() });
            setJob(nextJob);
            while (nextJob.state === "started" && generation === pollGeneration.current) {
                await wait(300);
                nextJob = await getAnalysis(nextJob.analysis_id);
                setJob(nextJob);
            }
            if (generation !== pollGeneration.current) return;
            if (nextJob.state === "completed" && nextJob.snapshot_id && nextJob.repository_id) {
                const [nextOverview, nextSnapshots, nextRepositories] = await Promise.all([
                    getOverview(nextJob.snapshot_id),
                    listSnapshots(nextJob.repository_id),
                    listRepositories(),
                ]);
                setOverview(nextOverview);
                setSnapshots(nextSnapshots);
                setRepositories(nextRepositories);
                setActiveView("overview");
            } else if (nextJob.state === "failed" || nextJob.state === "cancelled") {
                setError(nextJob.message ?? `Analysis ${nextJob.state}.`);
            }
        } catch (caught) {
            setError(messageFrom(caught, "The repository scan could not be started."));
        }
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
                    onPathChange={setRepositoryPath}
                    onRecentRepository={openRecentRepository}
                    onScan={scanRepository}
                    onCancel={cancelScan}
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

function wait(milliseconds: number): Promise<void> {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}
