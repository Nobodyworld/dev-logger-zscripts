import { useEffect, useRef, type FormEvent } from "react";

import { ScanIcon } from "../icons";
import type { AnalysisJob, Repository, RepositoryScopeResolution } from "../types";

interface RepositoryControlsProps {
    repositoryPath: string;
    repositories: Repository[];
    job: AnalysisJob | null;
    pendingScope: RepositoryScopeResolution | null;
    scopeResolving: boolean;
    onPathChange: (value: string) => void;
    onRecentRepository: (repositoryId: string) => void;
    onScan: () => void;
    onCancel: () => void;
    onScopeConfirm: () => void;
    onScopeCancel: () => void;
}

export function RepositoryControls({
    repositoryPath,
    repositories,
    job,
    pendingScope,
    scopeResolving,
    onPathChange,
    onRecentRepository,
    onScan,
    onCancel,
    onScopeConfirm,
    onScopeCancel,
}: RepositoryControlsProps) {
    const inputRef = useRef<HTMLInputElement>(null);
    const headingRef = useRef<HTMLHeadingElement>(null);
    const running = job?.state === "started";
    const progressValue =
        job && job.total > 0
            ? Math.min(job.completed, job.total)
            : job && job.state !== "started"
              ? 1
              : undefined;

    useEffect(() => {
        if (pendingScope) headingRef.current?.focus();
    }, [pendingScope]);

    const submit = (event: FormEvent) => {
        event.preventDefault();
        onScan();
    };

    const cancelScope = () => {
        onScopeCancel();
        window.requestAnimationFrame(() => inputRef.current?.focus());
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
                        ref={inputRef}
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
                        disabled={
                            !repositoryPath.trim() ||
                            running ||
                            scopeResolving ||
                            pendingScope !== null
                        }
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
            {pendingScope ? (
                <section
                    className="scope-confirmation"
                    role="dialog"
                    aria-modal="false"
                    aria-labelledby="scope-confirmation-heading"
                >
                    <p
                        className="scope-confirmation__announcement"
                        role="status"
                        aria-live="polite"
                    >
                        Scan scope changed to the resolved Git repository.
                    </p>
                    <h2 id="scope-confirmation-heading" ref={headingRef} tabIndex={-1}>
                        Scan resolved Git repository?
                    </h2>
                    <dl>
                        <div>
                            <dt>Entered path</dt>
                            <dd className="mono-wrap">{pendingScope.entered_path}</dd>
                        </div>
                        <div>
                            <dt>Canonical entered directory</dt>
                            <dd className="mono-wrap">{pendingScope.resolved_input_path}</dd>
                        </div>
                        <div>
                            <dt>Resolved Git root</dt>
                            <dd className="mono-wrap">{pendingScope.analysis_root}</dd>
                        </div>
                    </dl>
                    <p>
                        Analysis will cover the resolved Git repository, not only the entered
                        directory.
                    </p>
                    <div className="scope-confirmation__actions">
                        <button
                            className="button button--primary"
                            type="button"
                            onClick={onScopeConfirm}
                        >
                            Scan resolved repository
                        </button>
                        <button
                            className="button button--secondary"
                            type="button"
                            onClick={cancelScope}
                        >
                            Cancel
                        </button>
                    </div>
                </section>
            ) : null}
            {job ? (
                <div className="scan-progress" role="status" aria-live="polite">
                    <progress
                        max={Math.max(job.total, 1)}
                        value={progressValue}
                        aria-label="Repository scan progress"
                    />
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
