import type { FormEvent } from "react";

import { ScanIcon } from "../icons";
import type { AnalysisJob, Repository } from "../types";

interface RepositoryControlsProps {
    repositoryPath: string;
    repositories: Repository[];
    job: AnalysisJob | null;
    onPathChange: (value: string) => void;
    onRecentRepository: (repositoryId: string) => void;
    onScan: () => void;
    onCancel: () => void;
}

export function RepositoryControls({
    repositoryPath,
    repositories,
    job,
    onPathChange,
    onRecentRepository,
    onScan,
    onCancel,
}: RepositoryControlsProps) {
    const running = job?.state === "started";

    const submit = (event: FormEvent) => {
        event.preventDefault();
        onScan();
    };

    return (
        <section className="repository-controls">
            <form className="repository-form" onSubmit={submit}>
                <label id="repository-path-label" htmlFor="repository-path">
                    Repository path
                </label>
                <div className="repository-form__row">
                    <input
                        id="repository-path"
                        type="text"
                        value={repositoryPath}
                        onChange={(event) => onPathChange(event.target.value)}
                        placeholder="C:\\Projects\\sample-repository"
                        autoComplete="off"
                        disabled={running}
                    />
                    <button
                        className="button button--primary"
                        type="submit"
                        disabled={!repositoryPath || running}
                    >
                        <ScanIcon />
                        Scan repository
                    </button>
                    <button
                        className="button button--secondary"
                        type="button"
                        onClick={onCancel}
                        disabled={!running}
                    >
                        Cancel
                    </button>
                </div>
            </form>
            {repositories.length > 0 ? (
                <label className="recent-repository">
                    Recent repositories
                    <select
                        defaultValue=""
                        onChange={(event) => {
                            if (event.target.value) onRecentRepository(event.target.value);
                        }}
                        disabled={running}
                    >
                        <option value="">Choose a completed repository</option>
                        {repositories.map((repository) => (
                            <option value={repository.repository_id} key={repository.repository_id}>
                                {repository.display_name}
                            </option>
                        ))}
                    </select>
                </label>
            ) : null}
            {job ? (
                <div className="scan-progress" role="status" aria-live="polite">
                    <div className="scan-progress__track">
                        <span
                            style={{
                                width:
                                    job.total > 0
                                        ? `${Math.min(100, Math.round((job.completed / job.total) * 100))}%`
                                        : job.state === "started"
                                          ? "12%"
                                          : "100%",
                            }}
                        />
                    </div>
                    <span>
                        {job.state === "started"
                            ? `${job.phase}: ${job.completed}/${job.total || "…"}`
                            : (job.message ?? job.state)}
                    </span>
                </div>
            ) : null}
        </section>
    );
}
