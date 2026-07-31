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
    it("opens the ordinary workspace in a labeled focused queue with complete family counts", async () => {
        const fetchMock = findingsFetch();
        vi.stubGlobal("fetch", fetchMock);
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        expect(await screen.findByRole("heading", { name: "Focused queue" })).toBeTruthy();
        expect(screen.getByText("Applied preset: high-signal-v1")).toBeTruthy();
        expect(
            screen.getByText(/documentation and orphan candidates remain available/i),
        ).toBeTruthy();
        await waitFor(() => {
            expect(screen.getByText("Documentation").nextElementSibling?.textContent).toBe("14");
            expect(screen.getByText("Orphan candidates").nextElementSibling?.textContent).toBe(
                "18",
            );
            expect(
                screen.getByText("Duplicate-name candidates").nextElementSibling?.textContent,
            ).toBe("0");
            expect(
                screen.getByText("Test-evidence candidates").nextElementSibling?.textContent,
            ).toBe("3");
        });
        await waitFor(() => {
            expect(
                fetchMock.mock.calls.some(([input]) =>
                    String(input).includes("preset=high-signal-v1"),
                ),
            ).toBe(true);
        });
    });

    it("switches between all and focused queues in one action", async () => {
        const fetchMock = findingsFetch();
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        await user.type(
            screen.getByPlaceholderText("Search title or qualified subject"),
            "candidate",
        );
        await user.selectOptions(screen.getByLabelText("Status"), "new");
        await user.selectOptions(screen.getByLabelText("Evidence"), "resolved");
        await user.selectOptions(screen.getByLabelText("Sort"), "family");
        await user.click(await screen.findByRole("button", { name: "Show all findings" }));
        expect(await screen.findByRole("heading", { name: "All findings" })).toBeTruthy();
        expect(screen.getByPlaceholderText("Search title or qualified subject")).toHaveProperty(
            "value",
            "candidate",
        );
        expect(screen.getByLabelText("Status")).toHaveProperty("value", "new");
        expect(screen.getByLabelText("Evidence")).toHaveProperty("value", "resolved");
        expect(screen.getByLabelText("Sort")).toHaveProperty("value", "family");
        await waitFor(() => {
            expect(
                fetchMock.mock.calls.some(([input]) => String(input).includes("preset=all")),
            ).toBe(true);
        });
        await user.click(screen.getByRole("button", { name: "Restore focused queue" }));
        expect(await screen.findByRole("heading", { name: "Focused queue" })).toBeTruthy();
        expect(screen.getByText("Focused high-signal-v1 queue restored.")).toBeTruthy();
    });

    it("exposes the queue selector in native keyboard order", async () => {
        vi.stubGlobal("fetch", findingsFetch());
        const user = userEvent.setup();
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        const focused = await screen.findByRole("button", { name: "Focused" });
        const all = screen.getByRole("button", { name: "All findings" });
        focused.focus();
        await user.tab();
        expect(document.activeElement).toBe(all);
        await user.keyboard("{Enter}");
        expect(await screen.findByRole("heading", { name: "All findings" })).toBeTruthy();
    });

    it("clears the focused preset for an explicit family filter", async () => {
        const fetchMock = findingsFetch();
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        await user.selectOptions(await screen.findByLabelText("Family"), "documentation");
        expect(
            await screen.findByText("Focused preset cleared for explicit filters."),
        ).toBeTruthy();
        expect(screen.getByRole("heading", { name: "All findings" })).toBeTruthy();
        await waitFor(() => {
            expect(
                fetchMock.mock.calls.some(([input]) => {
                    const url = String(input);
                    return url.includes("preset=all") && url.includes("family=documentation");
                }),
            ).toBe(true);
        });
    });

    it.each(["needs-action", "resolved", "high-confidence-severity"])(
        "keeps the explicit %s navigation preset on the complete queue",
        async (navigationPreset) => {
            const fetchMock = findingsFetch();
            vi.stubGlobal("fetch", fetchMock);
            render(<FindingsView snapshotId={snapshot.snapshot_id} preset={navigationPreset} />);

            expect(await screen.findByRole("heading", { name: "All findings" })).toBeTruthy();
            await waitFor(() => {
                expect(
                    fetchMock.mock.calls.some(([input]) => String(input).includes("preset=all")),
                ).toBe(true);
            });
        },
    );

    it("resets an explicit navigation preset when ordinary Findings is reopened", async () => {
        const fetchMock = findingsFetch();
        vi.stubGlobal("fetch", fetchMock);
        const { rerender } = render(
            <FindingsView snapshotId={snapshot.snapshot_id} preset="needs-action" />,
        );

        expect(await screen.findByRole("heading", { name: "All findings" })).toBeTruthy();
        expect(screen.getByLabelText("Status")).toHaveProperty("value", "needs-action");
        rerender(<FindingsView snapshotId={snapshot.snapshot_id} preset="" />);

        expect(await screen.findByRole("heading", { name: "Focused queue" })).toBeTruthy();
        expect(screen.getByLabelText("Status")).toHaveProperty("value", "");
        await waitFor(() => {
            expect(
                fetchMock.mock.calls.some(([input]) =>
                    String(input).includes("preset=high-signal-v1"),
                ),
            ).toBe(true);
        });
    });

    it("ignores a stale focused response after switching to all findings", async () => {
        const focusedList = deferred<Response>();
        const fetchMock = vi.fn((input: RequestInfo | URL) => {
            const url = String(input);
            if (url.includes("/findings/summary")) {
                return Promise.resolve(response(findingSummary));
            }
            if (url.includes("/findings?") && url.includes("preset=high-signal-v1")) {
                return focusedList.promise;
            }
            if (url.includes("/findings?") && url.includes("preset=all")) {
                return Promise.resolve(
                    response({
                        supported: true,
                        preset: "all",
                        items: [secondFinding],
                        total: 1,
                        page: 1,
                        page_size: 25,
                    }),
                );
            }
            if (url.includes(`/${secondFinding.finding_id}/history`)) {
                return Promise.resolve(response(findingHistory));
            }
            if (url.includes(`/${secondFinding.finding_id}?`)) {
                return Promise.resolve(response(secondFinding));
            }
            if (url.includes("/source?")) {
                return Promise.resolve(
                    response({
                        relative_path: secondFinding.relative_path,
                        start_line: 1,
                        end_line: 4,
                        lines: [],
                        truncated: false,
                        content_hash: "source-hash",
                    }),
                );
            }
            return Promise.resolve(response({ detail: "Unexpected request" }, 500));
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        await user.click(await screen.findByRole("button", { name: "Show all findings" }));
        expect(await screen.findByRole("heading", { name: secondFinding.title })).toBeTruthy();
        focusedList.resolve(
            response({
                supported: true,
                preset: "high-signal-v1",
                items: [finding],
                total: 1,
                page: 1,
                page_size: 25,
            }),
        );
        await waitFor(() => {
            expect(screen.getByRole("heading", { name: secondFinding.title })).toBeTruthy();
            expect(screen.queryByRole("heading", { name: finding.title })).toBeNull();
        });
    });

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
                        url.includes("preset=all") &&
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

    it("reviews an excluded family from All findings without resetting the queue", async () => {
        const fetchMock = reviewQueueFetch([finding, secondFinding]);
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        await user.click(await screen.findByRole("button", { name: "Show all findings" }));
        await user.click(
            await screen.findByRole("button", { name: /Orphan-looking public symbol candidate/ }),
        );
        await user.selectOptions(await screen.findByLabelText("Review status"), "accepted");
        await user.click(screen.getByRole("button", { name: "Save review" }));

        expect(await screen.findByText("Review saved.")).toBeTruthy();
        expect(screen.getByRole("heading", { name: "All findings" })).toBeTruthy();
        expect(
            fetchMock.mock.calls
                .filter(([input]) => String(input).includes("/findings?"))
                .every(([input]) => String(input).includes("preset=all")),
        ).toBe(true);
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
        const fetchMock = findingsFetch(() =>
            response(
                {
                    detail: "Finding review version conflict.",
                    current,
                },
                409,
            ),
        );
        vi.stubGlobal("fetch", fetchMock);
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
        await waitFor(() => {
            expect(
                fetchMock.mock.calls.filter(([input]) =>
                    String(input).includes("/findings/summary"),
                ).length,
            ).toBeGreaterThanOrEqual(2);
            expect(
                fetchMock.mock.calls.filter(([input]) => String(input).includes("/findings?"))
                    .length,
            ).toBeGreaterThanOrEqual(2);
            expect(
                fetchMock.mock.calls
                    .filter(([input]) => String(input).includes("/findings?"))
                    .every(([input]) => String(input).includes("preset=high-signal-v1")),
            ).toBe(true);
        });
    });

    it("explains when automatic resolution was skipped", async () => {
        vi.stubGlobal(
            "fetch",
            findingsFetch(undefined, undefined, {
                ...findingSummary,
                reconciliation_complete: false,
                lifecycle_reconciled: true,
                reconciliation_skip_reason: "parse-gaps",
            }),
        );
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        expect(await screen.findByText(/parse gaps made absence unreliable/i)).toBeTruthy();
    });

    it("refreshes a status-filtered queue after a successful review", async () => {
        const fetchMock = reviewQueueFetch([finding]);
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        await user.selectOptions(await screen.findByLabelText("Status"), "new");
        await screen.findByRole("heading", { name: finding.title });
        await user.selectOptions(screen.getByLabelText("Review status"), "reviewed");
        await user.click(screen.getByRole("button", { name: "Save review" }));

        expect(
            await screen.findByText("No findings match the current bounded query."),
        ).toBeTruthy();
        expect(screen.queryByRole("heading", { name: finding.title })).toBeNull();
        expect(
            fetchMock.mock.calls.filter(([input]) => String(input).includes("/findings?")).length,
        ).toBeGreaterThanOrEqual(2);
        expect(
            fetchMock.mock.calls
                .filter(([input]) => String(input).includes("/findings?"))
                .every(([input]) => String(input).includes("preset=high-signal-v1")),
        ).toBe(true);
    });

    it("refreshes needs-action filters and status ordering after saves", async () => {
        const needsAction = {
            ...finding,
            review_status: "needs-action" as const,
            effective_status: "needs-action" as const,
        };
        const fetchMock = reviewQueueFetch([needsAction, secondFinding]);
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        const { container, rerender } = render(
            <FindingsView snapshotId={snapshot.snapshot_id} preset="needs-action" />,
        );

        await screen.findByRole("heading", { name: finding.title });
        await user.selectOptions(screen.getByLabelText("Review status"), "accepted");
        await user.click(screen.getByRole("button", { name: "Save review" }));
        expect(
            await screen.findByText("No findings match the current bounded query."),
        ).toBeTruthy();

        rerender(<FindingsView snapshotId="snapshot-sort-0123456789" />);
        await user.selectOptions(await screen.findByLabelText("Status"), "");
        await user.selectOptions(screen.getByLabelText("Sort"), "status");
        await waitFor(() => {
            const labels = Array.from(
                container.querySelectorAll<HTMLButtonElement>(".finding-queue button"),
            ).map((button) => button.textContent ?? "");
            expect(labels[0]).toContain(secondFinding.title);
            expect(labels[1]).toContain(finding.title);
        });
    });

    it("moves back from an emptied last page and selects a visible row", async () => {
        const findings = Array.from({ length: 26 }, (_, index) => ({
            ...finding,
            finding_id: `finding-page-${String(index).padStart(2, "0")}-0123456789abcdef`,
            title: `Finding ${String(index + 1).padStart(2, "0")}`,
            subject_keys: [`pkg.finding_${index + 1}`],
        }));
        vi.stubGlobal("fetch", reviewQueueFetch(findings));
        const user = userEvent.setup();
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        await user.selectOptions(await screen.findByLabelText("Status"), "new");
        await user.click(await screen.findByRole("button", { name: "Next" }));
        expect(await screen.findByRole("heading", { name: "Finding 26" })).toBeTruthy();
        await user.selectOptions(screen.getByLabelText("Review status"), "reviewed");
        await user.click(screen.getByRole("button", { name: "Save review" }));

        expect(await screen.findByText(/Page 1 · 25 findings/)).toBeTruthy();
        expect(await screen.findByRole("heading", { name: "Finding 01" })).toBeTruthy();
    });

    it("ignores a slow pre-save list response after the post-save refresh", async () => {
        const staleList = deferred<Response>();
        let listCall = 0;
        let current: Finding = finding;
        const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            if (url.includes("/findings/summary")) {
                return Promise.resolve(response(findingSummary));
            }
            if (url.includes("/findings?")) {
                listCall += 1;
                if (listCall === 2) return staleList.promise;
                const parameters = new URL(url, "http://localhost").searchParams;
                const items =
                    parameters.get("effective_status") === "new" &&
                    current.effective_status !== "new"
                        ? []
                        : [current];
                return Promise.resolve(
                    response({
                        supported: true,
                        preset: parameters.get("preset") ?? "all",
                        items,
                        total: items.length,
                        page: 1,
                        page_size: 25,
                    }),
                );
            }
            if (url.includes("/review") && init?.method === "PATCH") {
                current = {
                    ...current,
                    review_status: "reviewed",
                    effective_status: "reviewed",
                    review_version: 1,
                };
                return Promise.resolve(response(current));
            }
            if (url.includes("/history")) return Promise.resolve(response(findingHistory));
            if (url.includes("/api/findings/")) return Promise.resolve(response(current));
            if (url.includes("/source?")) {
                return Promise.resolve(
                    response({
                        relative_path: finding.relative_path,
                        start_line: 1,
                        end_line: 4,
                        lines: [],
                        truncated: false,
                        content_hash: "source-hash",
                    }),
                );
            }
            return Promise.resolve(response({ detail: "Unexpected request" }, 500));
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<FindingsView snapshotId={snapshot.snapshot_id} />);

        await screen.findByRole("heading", { name: finding.title });
        await user.selectOptions(screen.getByLabelText("Status"), "new");
        await waitFor(() => {
            expect(listCall).toBe(2);
        });
        await user.selectOptions(screen.getByLabelText("Review status"), "reviewed");
        await user.click(screen.getByRole("button", { name: "Save review" }));
        expect(
            await screen.findByText("No findings match the current bounded query."),
        ).toBeTruthy();

        staleList.resolve(
            response({
                supported: true,
                preset: "high-signal-v1",
                items: [finding],
                total: 1,
                page: 1,
                page_size: 25,
            }),
        );
        await waitFor(() => {
            expect(screen.queryByRole("heading", { name: finding.title })).toBeNull();
        });
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
                            preset: "high-signal-v1",
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
    summary = findingSummary,
) {
    return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/findings/summary")) return Promise.resolve(response(summary));
        if (url.includes("/findings?")) {
            const parameters = new URL(url, "http://localhost").searchParams;
            return Promise.resolve(
                response({
                    supported: true,
                    preset: parameters.get("preset") ?? "all",
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

function reviewQueueFetch(initialItems: Finding[]) {
    let items = initialItems.map((item) => ({ ...item }));
    return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/findings/summary")) {
            const counts = {
                ...findingSummary,
                active: items.length,
                needs_action: items.filter((item) => item.review_status === "needs-action").length,
                accepted: items.filter((item) => item.review_status === "accepted").length,
                dismissed: items.filter((item) => item.review_status === "dismissed").length,
            };
            return Promise.resolve(response(counts));
        }
        if (url.includes("/findings?")) {
            const parameters = new URL(url, "http://localhost").searchParams;
            const effectiveStatus = parameters.get("effective_status");
            const pageNumber = Number(parameters.get("page") ?? "1");
            const pageSize = Number(parameters.get("page_size") ?? "25");
            const matches = effectiveStatus
                ? items.filter((item) => item.effective_status === effectiveStatus)
                : [...items];
            if (parameters.get("sort") === "status") {
                matches.sort(
                    (left, right) =>
                        left.effective_status.localeCompare(right.effective_status) ||
                        left.finding_id.localeCompare(right.finding_id),
                );
                if (parameters.get("direction") === "desc") matches.reverse();
            }
            const start = (pageNumber - 1) * pageSize;
            return Promise.resolve(
                response({
                    supported: true,
                    preset: parameters.get("preset") ?? "all",
                    items: matches.slice(start, start + pageSize),
                    total: matches.length,
                    page: pageNumber,
                    page_size: pageSize,
                }),
            );
        }
        if (url.includes("/review") && init?.method === "PATCH") {
            const findingId = decodeURIComponent(url.split("/api/findings/")[1].split("/")[0]);
            const payload = JSON.parse(String(init.body)) as {
                review_status: Finding["review_status"];
                note: string;
                reason_code: string | null;
            };
            const current = items.find((item) => item.finding_id === findingId);
            if (!current) return Promise.resolve(response({ detail: "Not found" }, 404));
            const updated: Finding = {
                ...current,
                review_status: payload.review_status,
                effective_status: payload.review_status,
                note: payload.note,
                reason_code: payload.reason_code,
                review_version: current.review_version + 1,
            };
            items = items.map((item) => (item.finding_id === findingId ? updated : item));
            return Promise.resolve(response(updated));
        }
        if (url.includes("/history")) return Promise.resolve(response(findingHistory));
        if (url.includes("/source?")) {
            return Promise.resolve(
                response({
                    relative_path: finding.relative_path,
                    start_line: 1,
                    end_line: 4,
                    lines: [],
                    truncated: false,
                    content_hash: "source-hash",
                }),
            );
        }
        if (url.includes("/api/findings/")) {
            const findingId = decodeURIComponent(url.split("/api/findings/")[1].split("?")[0]);
            const current = items.find((item) => item.finding_id === findingId);
            return Promise.resolve(
                current ? response(current) : response({ detail: "Finding was not found." }, 404),
            );
        }
        return Promise.resolve(response({ detail: "Unexpected request" }, 500));
    });
}
