import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

const sameRootScope = {
    presentation_version: "1" as const,
    entered_path: "C:\\Projects\\sample",
    resolved_input_path: "C:\\Projects\\sample",
    analysis_root: "C:\\Projects\\sample",
    git_root_detected: true,
    confirmation_required: false,
    reason: "same-directory" as const,
};

const nestedScope = {
    ...sameRootScope,
    resolved_input_path: "C:\\Projects\\sample\\src\\feature",
    analysis_root: "C:\\Projects\\sample",
    confirmation_required: true,
    reason: "enclosing-git-root" as const,
};

const startedAnalysis = {
    analysis_id: "analysis-00000001",
    state: "started",
    phase: "discovery",
    completed: 0,
    total: 0,
    current_file: "",
    repository_id: null,
    snapshot_id: null,
    message: null,
};

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
            void init;
            if (url === "/api/repositories") return response({ repositories: [] });
            if (url === "/api/repositories/resolve-scope") return response(sameRootScope);
            if (url === "/api/repositories/analyze") {
                return response(startedAnalysis);
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

    it("requires nested scope confirmation before starting exactly one analysis", async () => {
        const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            void init;
            if (url === "/api/repositories") return response({ repositories: [] });
            if (url === "/api/repositories/resolve-scope") return response(nestedScope);
            if (url === "/api/repositories/analyze") return response(startedAnalysis);
            return response({ detail: "Unexpected request" }, 500);
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<App />);

        await user.type(await screen.findByLabelText("Repository path"), nestedScope.entered_path);
        await user.click(screen.getByRole("button", { name: "Scan repository" }));

        const heading = await screen.findByRole("heading", {
            name: "Scan resolved Git repository?",
        });
        expect(heading).toBe(document.activeElement);
        expect(screen.getByText(nestedScope.resolved_input_path)).toBeTruthy();
        expect(screen.getByText(nestedScope.analysis_root)).toBeTruthy();
        expect(fetchMock.mock.calls.some(([url]) => url === "/api/repositories/analyze")).toBe(
            false,
        );
        expect(screen.queryByRole("progressbar")).toBeNull();

        const confirm = screen.getByRole("button", { name: "Scan resolved repository" });
        fireEvent.click(confirm);
        fireEvent.click(confirm);
        await waitFor(() => {
            const analysis = fetchMock.mock.calls.find(
                ([url]) => url === "/api/repositories/analyze",
            );
            expect(analysis).toBeTruthy();
            expect(JSON.parse(String(analysis?.[1]?.body))).toEqual({
                repository_path: nestedScope.analysis_root,
            });
        });
        expect(
            fetchMock.mock.calls.filter(([url]) => url === "/api/repositories/analyze"),
        ).toHaveLength(1);
    });

    it("cancels a pending scope without starting analysis and returns focus to the path", async () => {
        const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
            if (String(input) === "/api/repositories") return response({ repositories: [] });
            return response(nestedScope);
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<App />);

        const path = await screen.findByLabelText("Repository path");
        await user.type(path, nestedScope.entered_path);
        await user.click(screen.getByRole("button", { name: "Scan repository" }));
        const dialog = await screen.findByRole("dialog");
        await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

        await waitFor(() => expect(document.activeElement).toBe(path));
        expect(screen.queryByRole("dialog")).toBeNull();
        expect(screen.queryByRole("progressbar")).toBeNull();
        expect(fetchMock.mock.calls.some(([url]) => url === "/api/repositories/analyze")).toBe(
            false,
        );
    });

    it("clears a stale nested response after a path edit and starts same-root analysis directly", async () => {
        let resolveFirst: ((value: Response) => void) | undefined;
        const firstResolution = new Promise<Response>((resolve) => {
            resolveFirst = resolve;
        });
        let scopeCalls = 0;
        const fetchMock = vi.fn((input: RequestInfo | URL) => {
            const url = String(input);
            if (url === "/api/repositories") return Promise.resolve(response({ repositories: [] }));
            if (url === "/api/repositories/resolve-scope") {
                scopeCalls += 1;
                return scopeCalls === 1
                    ? firstResolution
                    : Promise.resolve(
                          response({ ...sameRootScope, entered_path: "C:\\Projects\\other" }),
                      );
            }
            if (url === "/api/repositories/analyze")
                return Promise.resolve(response(startedAnalysis));
            return Promise.resolve(response({ detail: "Unexpected request" }, 500));
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<App />);

        const path = await screen.findByLabelText("Repository path");
        await user.type(path, nestedScope.entered_path);
        await user.click(screen.getByRole("button", { name: "Scan repository" }));
        await user.clear(path);
        await user.type(path, "C:\\Projects\\other");
        await user.click(screen.getByRole("button", { name: "Scan repository" }));
        resolveFirst?.(response(nestedScope));

        await waitFor(() =>
            expect(
                fetchMock.mock.calls.filter(([url]) => url === "/api/repositories/analyze"),
            ).toHaveLength(1),
        );
        expect(screen.queryByRole("dialog")).toBeNull();
    });
});
