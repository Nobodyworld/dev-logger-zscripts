import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { formatSnapshotChoiceLabel } from "../snapshotLabels";
import type { SnapshotChoice } from "../types";
import { olderSnapshot, overview, repository, response, snapshot } from "./fixtures";

const snapshotChoices: SnapshotChoice[] = [snapshot, olderSnapshot].map((choice) => ({
    ...choice,
    observed_state_known: true,
    branch: "main",
    git_sha: repository.git_sha,
    dirty: false,
    staged: false,
    untracked: false,
    lifecycle_reconciled: true,
    reconciliation_skip_reason: null,
}));

describe("App", () => {
    afterEach(() => {
        vi.useRealTimers();
    });

    it("renders the local repository form and empty state", async () => {
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ repositories: [] })));
        render(<App />);

        expect(await screen.findByLabelText("Repository path")).toBeTruthy();
        expect(screen.getByRole("button", { name: "Scan repository" })).toBeTruthy();
        expect(screen.getByText("Select a local Python repository")).toBeTruthy();
    });

    it("shows scan progress and supports cancellation", async () => {
        const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            if (url === "/api/repositories") return response({ repositories: [] });
            if (url === "/api/repositories/analyze") {
                return response({
                    analysis_id: "analysis-00000001",
                    state: "started",
                    phase: "discovery",
                    completed: 0,
                    total: 0,
                    current_file: "",
                    repository_id: null,
                    snapshot_id: null,
                    message: null,
                });
            }
            if (url.endsWith("/cancel") && init?.method === "POST") {
                return response({
                    analysis_id: "analysis-00000001",
                    state: "cancelled",
                    phase: "cancelling",
                    completed: 0,
                    total: 0,
                    current_file: "",
                    repository_id: null,
                    snapshot_id: null,
                    message: "Analysis cancelled.",
                });
            }
            return response({ detail: "Unexpected request" }, 500);
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<App />);

        await user.type(await screen.findByLabelText("Repository path"), "C:\\Projects\\sample");
        await user.click(screen.getByRole("button", { name: "Scan repository" }));
        const cancel = await screen.findByRole("button", { name: "Cancel" });
        expect(cancel.getAttribute("disabled")).toBeNull();
        expect(screen.getByRole("status").textContent).toContain("discovery");
        await user.click(cancel);

        await waitFor(() => {
            expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/cancel"))).toBe(
                true,
            );
        });
    });

    it("switches between prior snapshots", async () => {
        const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
            const url = String(input);
            if (url === "/api/repositories") return response({ repositories: [repository] });
            if (url === `/api/repositories/${repository.repository_id}/comparison-snapshots`) {
                return response({ repository, snapshots: snapshotChoices });
            }
            if (url.includes(olderSnapshot.snapshot_id)) {
                return response({
                    ...overview,
                    snapshot: olderSnapshot,
                });
            }
            if (url.includes(snapshot.snapshot_id)) return response(overview);
            return response({ detail: "Unexpected request" }, 500);
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<App />);

        const recent = await screen.findByLabelText("Recent repositories");
        await user.selectOptions(recent, repository.repository_id);
        const selector = (await screen.findByLabelText("Current snapshot")) as HTMLSelectElement;
        expect(selector.value).toBe(snapshot.snapshot_id);
        expect(Array.from(selector.options, (option) => option.value)).toEqual(
            snapshotChoices.map((choice) => choice.snapshot_id),
        );
        expect(Array.from(selector.options, (option) => option.textContent)).toEqual(
            snapshotChoices.map(formatSnapshotChoiceLabel),
        );
        await user.selectOptions(selector, olderSnapshot.snapshot_id);

        await waitFor(() => {
            expect(
                fetchMock.mock.calls.some(([url]) =>
                    String(url).includes(olderSnapshot.snapshot_id),
                ),
            ).toBe(true);
        });
        expect(
            fetchMock.mock.calls.some(([url]) =>
                String(url).endsWith(`/${repository.repository_id}/snapshots`),
            ),
        ).toBe(false);
    });

    it("presents API errors without exposing raw response content", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn().mockResolvedValue(response({ detail: "Local request failed." }, 500)),
        );
        render(<App />);

        expect(await screen.findByRole("alert")).toBeTruthy();
        expect(screen.getByRole("alert").textContent).toBe("Local request failed.");
    });
});
