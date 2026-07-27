import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FindingsView } from "../components/FindingsView";
import type { Finding } from "../types";
import {
    finding,
    findingHistory,
    findingSummary,
    response,
    secondFinding,
    snapshot,
} from "./fixtures";

interface Deferred<T> {
    promise: Promise<T>;
    resolve: (value: T) => void;
    reject: (reason: unknown) => void;
}

function deferred<T>(): Deferred<T> {
    let resolve!: (value: T) => void;
    let reject!: (reason: unknown) => void;
    const promise = new Promise<T>((resolvePromise, rejectPromise) => {
        resolve = resolvePromise;
        reject = rejectPromise;
    });
    return { promise, resolve, reject };
}

describe("FindingsView", () => {
    it("loads, filters, selects, escapes content, and shows bounded evidence", async () => {
        const fetchMock = findingsFetch();
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        const { container } = render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        expect(await screen.findByRole("heading", { name: "Findings" })).toBeTruthy();
        expect(await screen.findByText(finding.title)).toBeTruthy();
        expect(container.querySelector("img")).toBeNull();
        expect(await screen.findByLabelText("Finding source evidence")).toBeTruthy();
        expect(screen.getByText("def complex_target(...):")).toBeTruthy();

        await user.type(
            screen.getByPlaceholderText("Search title or qualified subject"),
            "complex_target",
        );
        await user.selectOptions(screen.getByLabelText("Severity"), "low");
        await user.selectOptions(screen.getByLabelText("Confidence"), "high");
        await user.selectOptions(screen.getByLabelText("Sort"), "qualified_subject");

        await waitFor(() => {
            expect(
                fetchMock.mock.calls.some(([input]) => {
                    const url = String(input);
                    return (
                        url.includes("search=complex_target") &&
                        url.includes("severity=low") &&
                        url.includes("confidence=high") &&
                        url.includes("sort=qualified_subject")
                    );
                }),
            ).toBe(true);
        });
    });

    it("uses explicit save and preserves plain-text notes", async () => {
        const fetchMock = findingsFetch();
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        const note = await screen.findByLabelText(/Local note/);
        await user.type(note, '<script>alert("escaped")</script>');
        await user.selectOptions(screen.getByLabelText("Review status"), "needs-action");
        expect(screen.getByText("Unsaved changes")).toBeTruthy();
        expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PATCH")).toBe(false);

        await user.click(screen.getByRole("button", { name: "Save review" }));
        expect(await screen.findByText("Review saved.")).toBeTruthy();
        const patch = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
        expect(patch).toBeTruthy();
        expect(String(patch?.[1]?.body)).toContain("<script>");
        expect(document.querySelector("script")).toBeNull();
    });

    it("reloads safe current state on optimistic concurrency conflict", async () => {
        const current: Finding = {
            ...finding,
            review_status: "accepted",
            effective_status: "accepted",
            note: "another local decision",
            reason_code: "intentional-design",
            review_version: 2,
        };
        vi.stubGlobal(
            "fetch",
            findingsFetch(() =>
                response(
                    {
                        detail: "Finding review version conflict.",
                        current,
                    },
                    409,
                ),
            ),
        );
        const user = userEvent.setup();
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        await user.selectOptions(await screen.findByLabelText("Review status"), "reviewed");
        await user.click(screen.getByRole("button", { name: "Save review" }));

        expect(
            await screen.findByText(
                "Another review update was saved first. Current local state has been reloaded.",
            ),
        ).toBeTruthy();
        expect(screen.getByLabelText("Review status")).toHaveProperty("value", "accepted");
        expect(screen.getByLabelText(/Local note/)).toHaveProperty(
            "value",
            "another local decision",
        );
    });

    it("ignores stale detail success after selecting another finding", async () => {
        const firstDetail = deferred<Response>();
        const fetchMock = findingsFetch(undefined, firstDetail);
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        await user.click(
            await screen.findByRole("button", {
                name: /Orphan-looking public symbol candidate/,
            }),
        );
        expect(
            await screen.findByRole("heading", {
                name: "Orphan-looking public symbol candidate",
            }),
        ).toBeTruthy();

        firstDetail.resolve(response(finding));
        await waitFor(() => {
            expect(
                screen.getByRole("heading", {
                    name: "Orphan-looking public symbol candidate",
                }),
            ).toBeTruthy();
            expect(screen.queryByRole("heading", { name: finding.title })).toBeNull();
        });

        expect(screen.queryByText("Finding details could not be loaded.")).toBeNull();
    });

    it("ignores stale detail rejection after selecting another finding", async () => {
        const firstDetail = deferred<Response>();
        vi.stubGlobal("fetch", findingsFetch(undefined, firstDetail));
        const user = userEvent.setup();
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        await user.click(
            await screen.findByRole("button", {
                name: /Orphan-looking public symbol candidate/,
            }),
        );
        expect(
            await screen.findByRole("heading", {
                name: "Orphan-looking public symbol candidate",
            }),
        ).toBeTruthy();
        firstDetail.reject(new Error("stale detail rejection"));
        await waitFor(() => {
            expect(screen.queryByText("Finding details could not be loaded.")).toBeNull();
        });
    });

    it("ignores a stale review success after selection changes", async () => {
        const review = deferred<Response>();
        const fetchMock = findingsFetch(() => review.promise);
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        await user.selectOptions(await screen.findByLabelText("Review status"), "reviewed");
        await user.click(screen.getByRole("button", { name: "Save review" }));
        await user.click(
            screen.getByRole("button", { name: /Orphan-looking public symbol candidate/ }),
        );
        review.resolve(
            response({
                ...finding,
                review_status: "reviewed",
                effective_status: "reviewed",
                review_version: 1,
            }),
        );

        expect(
            await screen.findByRole("heading", {
                name: "Orphan-looking public symbol candidate",
            }),
        ).toBeTruthy();
        await waitFor(() => {
            expect(screen.getByLabelText("Review status")).toHaveProperty("value", "new");
            expect(screen.queryByText("Review saved.")).toBeNull();
        });
    });

    it("ignores a stale review rejection after selection changes", async () => {
        const review = deferred<Response>();
        vi.stubGlobal(
            "fetch",
            findingsFetch(() => review.promise),
        );
        const user = userEvent.setup();
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        await user.selectOptions(await screen.findByLabelText("Review status"), "reviewed");
        await user.click(screen.getByRole("button", { name: "Save review" }));
        await user.click(
            screen.getByRole("button", { name: /Orphan-looking public symbol candidate/ }),
        );
        review.reject(new Error("stale review rejection"));

        expect(
            await screen.findByRole("heading", {
                name: "Orphan-looking public symbol candidate",
            }),
        ).toBeTruthy();
        await waitFor(() => {
            expect(screen.queryByText("The review decision could not be saved.")).toBeNull();
            expect(screen.getByLabelText("Review status")).toHaveProperty("value", "new");
        });
    });

    it("shows unsupported, empty, error, and narrow-layout states", async () => {
        Object.defineProperty(window, "innerWidth", { configurable: true, value: 375 });
        vi.stubGlobal(
            "fetch",
            vi.fn((input: RequestInfo | URL) => {
                const url = String(input);
                if (url.includes("/summary")) {
                    return Promise.resolve(response({ ...findingSummary, supported: false }));
                }
                if (url.includes("/findings?")) {
                    return Promise.resolve(
                        response({
                            supported: false,
                            items: [],
                            total: 0,
                            page: 1,
                            page_size: 25,
                        }),
                    );
                }
                return Promise.resolve(response({ detail: "Unexpected request" }, 500));
            }),
        );
        const { rerender } = render(<FindingsView snapshotId={snapshot.snapshot_id} />);
        expect(
            await screen.findByText(/Findings are not available for this older snapshot/),
        ).toBeTruthy();

        vi.stubGlobal(
            "fetch",
            vi.fn((input: RequestInfo | URL) => {
                const url = String(input);
                if (url.includes("/summary")) return Promise.resolve(response(findingSummary));
                return Promise.resolve(response({ detail: "failed" }, 500));
            }),
        );
        rerender(<FindingsView snapshotId="snapshot-error-0123456789" />);
        expect((await screen.findByRole("alert")).textContent).toBe(
            "Findings could not be loaded.",
        );
    });
});

function findingsFetch(
    reviewResponse?: () => Response | Promise<Response>,
    firstDetail?: Deferred<Response>,
) {
    return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/findings/summary")) return Promise.resolve(response(findingSummary));
        if (url.includes("/findings?")) {
            return Promise.resolve(
                response({
                    supported: true,
                    items: [finding, secondFinding],
                    total: 2,
                    page: 1,
                    page_size: 25,
                }),
            );
        }
        if (url.includes(`/${finding.finding_id}/review`) && init?.method === "PATCH") {
            const next = reviewResponse?.();
            return next instanceof Promise
                ? next
                : Promise.resolve(
                      next ??
                          response({
                              ...finding,
                              review_status: "needs-action",
                              effective_status: "needs-action",
                              note: '<script>alert("escaped")</script>',
                              review_version: 1,
                          }),
                  );
        }
        if (url.includes(`/${finding.finding_id}/history`)) {
            return Promise.resolve(response(findingHistory));
        }
        if (url.includes(`/${secondFinding.finding_id}/history`)) {
            return Promise.resolve(
                response({
                    ...findingHistory,
                    items: findingHistory.items.map((item) => ({
                        ...item,
                        finding_id: secondFinding.finding_id,
                    })),
                }),
            );
        }
        if (url.includes(`/${finding.finding_id}?`)) {
            return firstDetail?.promise ?? Promise.resolve(response(finding));
        }
        if (url.includes(`/${secondFinding.finding_id}?`)) {
            return Promise.resolve(response(secondFinding));
        }
        if (url.includes("/source?")) {
            return Promise.resolve(
                response({
                    relative_path: finding.relative_path,
                    start_line: 1,
                    end_line: 4,
                    lines: [{ number: 4, text: "def complex_target(...):" }],
                    truncated: false,
                    content_hash: "source-hash",
                }),
            );
        }
        return Promise.resolve(response({ detail: "Unexpected request" }, 500));
    });
}
