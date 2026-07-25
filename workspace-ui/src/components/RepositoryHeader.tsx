import type { Overview, Snapshot } from "../types";

interface RepositoryHeaderProps {
    overview: Overview;
    snapshots: Snapshot[];
    onSnapshotChange: (snapshotId: string) => void;
}

export function RepositoryHeader({ overview, snapshots, onSnapshotChange }: RepositoryHeaderProps) {
    const { repository, snapshot } = overview;
    const state = repository.dirty ? "Dirty" : "Clean";

    return (
        <header className="repository-header">
            <div>
                <h1>{repository.display_name}</h1>
                <dl className="repository-meta" aria-label="Repository state">
                    <div>
                        <dt>Branch</dt>
                        <dd>{repository.branch ?? "Detached"}</dd>
                    </div>
                    <div>
                        <dt>SHA</dt>
                        <dd className="mono">{repository.git_sha?.slice(0, 7) ?? "No Git SHA"}</dd>
                    </div>
                    <div>
                        <dt>Working tree</dt>
                        <dd>{state}</dd>
                    </div>
                    <div>
                        <dt>Scan status</dt>
                        <dd className="status-complete">Completed</dd>
                    </div>
                </dl>
            </div>
            <label className="snapshot-select">
                Current snapshot
                <select
                    value={snapshot.snapshot_id}
                    onChange={(event) => onSnapshotChange(event.target.value)}
                >
                    {snapshots.map((item) => (
                        <option value={item.snapshot_id} key={item.snapshot_id}>
                            {formatSnapshotDate(item.completed_at)}
                        </option>
                    ))}
                </select>
            </label>
        </header>
    );
}

function formatSnapshotDate(value: string | null): string {
    if (!value) return "Completed snapshot";
    return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(new Date(value));
}
