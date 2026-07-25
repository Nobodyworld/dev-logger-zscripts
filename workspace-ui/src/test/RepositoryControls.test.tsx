import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RepositoryControls } from "../components/RepositoryControls";
import type { AnalysisJob } from "../types";

const startedJob: AnalysisJob = {
    analysis_id: "analysis-1",
    state: "started",
    phase: "discovery",
    completed: 0,
    total: 0,
    current_file: "",
    repository_id: null,
    snapshot_id: null,
    message: null,
};

function renderControls(job: AnalysisJob) {
    render(
        <RepositoryControls
            repositoryPath=""
            repositories={[]}
            job={job}
            onPathChange={vi.fn()}
            onRecentRepository={vi.fn()}
            onScan={vi.fn()}
            onCancel={vi.fn()}
        />,
    );
    return screen.getByRole("progressbar", { name: "Repository scan progress" });
}

describe("RepositoryControls progress", () => {
    it("shows an indeterminate initial state when the total is unknown", () => {
        const progress = renderControls(startedJob);

        expect(progress.getAttribute("max")).toBe("1");
        expect(progress.getAttribute("value")).toBeNull();
        expect(screen.getByRole("status").textContent).toContain("discovery: 0/…");
    });

    it("shows determinate partial progress", () => {
        const progress = renderControls({ ...startedJob, completed: 3, total: 8 });

        expect(progress.getAttribute("max")).toBe("8");
        expect(progress.getAttribute("value")).toBe("3");
        expect(screen.getByRole("status").textContent).toContain("discovery: 3/8");
    });

    it("shows a completed determinate state", () => {
        const progress = renderControls({
            ...startedJob,
            state: "completed",
            completed: 8,
            total: 8,
            message: "Analysis completed.",
        });

        expect(progress.getAttribute("max")).toBe("8");
        expect(progress.getAttribute("value")).toBe("8");
        expect(screen.getByRole("status").textContent).toContain("Analysis completed.");
    });

    it("retains cancellation status and bounded progress", () => {
        const progress = renderControls({
            ...startedJob,
            state: "cancelled",
            completed: 3,
            total: 8,
            message: "Analysis cancelled.",
        });

        expect(progress.getAttribute("max")).toBe("8");
        expect(progress.getAttribute("value")).toBe("3");
        expect(screen.getByRole("status").textContent).toContain("Analysis cancelled.");
    });
});
