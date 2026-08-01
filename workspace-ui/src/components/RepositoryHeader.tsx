import { formatSnapshotChoiceLabel, formatSnapshotReference } from "../snapshotLabels";
import type { Overview, SnapshotChoice } from "../types";

interface RepositoryHeaderProps {
    overview: Overview;
    snapshots: SnapshotChoice[];
    onSnapshotChange: (snapshotId: string) => void;
}

export function RepositoryHeader({ overview, snapshots, onSnapshotChange }: RepositoryHeaderProps) {
    const { repository, snapshot } = overview;
    const state = repository.dirty ? "Dirty" : "Clean";
    const selectedChoice = snapshots.find((item) => item.snapshot_id === snapshot.snapshot_id);
    const selectedLabel = selectedChoice
        ? formatSnapshotChoiceLabel(selectedChoice)
        : formatSnapshotReference(snapshot.snapshot_id);

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
            <div className="snapshot-select">
                <label htmlFor="current-snapshot">Current snapshot</label>
                <select
                    id="current-snapshot"
                    value={snapshot.snapshot_id}
                    onChange={(event) => onSnapshotChange(event.target.value)}
                    aria-describedby="current-snapshot-context"
                >
                    {snapshots.map((item) => (
                        <option value={item.snapshot_id} key={item.snapshot_id}>
                            {formatSnapshotChoiceLabel(item)}
                        </option>
                    ))}
                </select>
                <span
                    id="current-snapshot-context"
                    className="snapshot-selection-context"
                    aria-label="Selected snapshot context"
                >
                    Selected snapshot: {selectedLabel}
                </span>
            </div>
        </header>
    );
}
