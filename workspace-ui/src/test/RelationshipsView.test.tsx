import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RelationshipsView } from "../components/RelationshipsView";
import type { RelationshipNeighborhood } from "../types";
import {
    classNode,
    cycleGroup,
    importRelationship,
    moduleB,
    packageNode,
    relationshipNeighborhood,
    relationshipSummary,
    response,
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

describe("RelationshipsView", () => {
    it("loads a bounded graph, exposes textual lists, and opens source evidence", async () => {
        const fetchMock = relationshipFetch();
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<RelationshipsView snapshotId={snapshot.snapshot_id} />);

        expect(screen.getByRole("status").textContent).toContain(
            "Loading bounded relationship evidence",
        );
        expect(await screen.findByRole("heading", { name: "Relationships" })).toBeTruthy();
        expect(
            await screen.findByRole("img", { name: "Focused relationship neighborhood" }),
        ).toBeTruthy();
        expect(screen.getByLabelText("Graph nodes")).toBeTruthy();
        expect(screen.getByText("Selected node:").parentElement?.textContent).toContain("pkg.a");

        const outgoing = screen.getByRole("heading", {
            name: "Outgoing relationships",
        }).parentElement;
        expect(outgoing).not.toBeNull();
        const resolved = within(outgoing as HTMLElement).getByRole("button", {
            name: /resolved-static/,
        });
        await user.click(resolved);

        expect(await screen.findByLabelText("Relationship source excerpt")).toBeTruthy();
        expect(screen.getByText("from pkg import b")).toBeTruthy();
        expect(screen.getByText("from . import b")).toBeTruthy();

        const nodeButton = screen.getByRole("button", { name: /pkg\.bmodule · distance 1/ });
        nodeButton.focus();
        await user.keyboard("{Enter}");
        await waitFor(() => {
            expect(screen.getByText("Selected node:").parentElement?.textContent).toContain(
                "pkg.b",
            );
        });
    });

    it("supports mode, node search, focus, depth, cycle, and resolution controls", async () => {
        const fetchMock = relationshipFetch();
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<RelationshipsView snapshotId={snapshot.snapshot_id} />);

        await screen.findByLabelText("Focus node");
        await user.type(screen.getByPlaceholderText("Search nodes"), "pkg.b");
        expect(within(screen.getByLabelText("Focus node")).getByText("pkg.b")).toBeTruthy();
        await user.selectOptions(screen.getByLabelText("Depth"), "2");
        await user.selectOptions(screen.getByLabelText("Resolution"), "resolved-static");
        await user.selectOptions(screen.getByLabelText("Graph mode"), "inheritance");
        expect(
            within(screen.getByLabelText("Focus node")).getByText(classNode.qualified_name),
        ).toBeTruthy();
        await user.selectOptions(screen.getByLabelText("Cycle group"), cycleGroup.cycle_id);

        await waitFor(() => {
            expect(
                fetchMock.mock.calls.some(([input]) => {
                    const url = String(input);
                    return (
                        url.includes("depth=2") && url.includes("resolution_status=resolved-static")
                    );
                }),
            ).toBe(true);
            expect(screen.getByLabelText("Graph mode")).toHaveProperty("value", "modules");
        });
    });

    it("ignores a stale graph success after a later focus succeeds", async () => {
        const firstGraph = deferred<Response>();
        const secondGraph = deferred<Response>();
        vi.stubGlobal(
            "fetch",
            vi.fn((input: RequestInfo | URL) => {
                const url = String(input);
                if (url.includes("/relationships/summary")) {
                    return Promise.resolve(response(relationshipSummary));
                }
                if (url.includes("/cycles")) {
                    return Promise.resolve(
                        response({ supported: true, items: [], truncated: false }),
                    );
                }
                if (url.includes("/relationships/neighborhood")) {
                    return url.includes(encodeURIComponent(moduleB.node_id))
                        ? secondGraph.promise
                        : firstGraph.promise;
                }
                return Promise.resolve(response({ detail: "Unexpected request" }, 500));
            }),
        );
        const user = userEvent.setup();
        render(<RelationshipsView snapshotId={snapshot.snapshot_id} />);

        const focus = await screen.findByLabelText("Focus node");
        await user.selectOptions(focus, moduleB.node_id);
        secondGraph.resolve(
            response({
                ...relationshipNeighborhood,
                focus_id: moduleB.node_id,
                nodes: [moduleB],
                relationships: [],
                distances: { [moduleB.node_id]: 0 },
            }),
        );
        expect(
            await screen
                .findByText("Selected node:")
                .then((item) => item.parentElement?.textContent),
        ).toContain("pkg.b");

        firstGraph.resolve(response(relationshipNeighborhood));
        await waitFor(() => {
            expect(screen.getByText("Selected node:").parentElement?.textContent).toContain(
                "pkg.b",
            );
        });
    });

    it("ignores a stale graph rejection after a later focus succeeds", async () => {
        const firstGraph = deferred<Response>();
        const secondGraph = deferred<Response>();
        vi.stubGlobal(
            "fetch",
            vi.fn((input: RequestInfo | URL) => {
                const url = String(input);
                if (url.includes("/relationships/summary")) {
                    return Promise.resolve(response(relationshipSummary));
                }
                if (url.includes("/cycles")) {
                    return Promise.resolve(
                        response({ supported: true, items: [], truncated: false }),
                    );
                }
                if (url.includes("/relationships/neighborhood")) {
                    return url.includes(encodeURIComponent(moduleB.node_id))
                        ? secondGraph.promise
                        : firstGraph.promise;
                }
                return Promise.resolve(response({ detail: "Unexpected request" }, 500));
            }),
        );
        const user = userEvent.setup();
        render(<RelationshipsView snapshotId={snapshot.snapshot_id} />);

        await user.selectOptions(await screen.findByLabelText("Focus node"), moduleB.node_id);
        secondGraph.resolve(
            response({
                ...relationshipNeighborhood,
                focus_id: moduleB.node_id,
                nodes: [moduleB],
                relationships: [],
                distances: { [moduleB.node_id]: 0 },
            }),
        );
        await screen.findByText("Selected node:");
        firstGraph.reject(new Error("stale graph failed"));

        await waitFor(() => {
            expect(screen.getByText("Selected node:").parentElement?.textContent).toContain(
                "pkg.b",
            );
        });
        expect(
            screen.queryByText("The focused relationship graph could not be loaded."),
        ).toBeNull();
    });

    it("keeps later relationship source when an earlier source resolves afterward", async () => {
        const firstSource = deferred<Response>();
        const secondSource = deferred<Response>();
        const fetchMock = relationshipFetch((url) => {
            if (url.includes("end_line=6")) return firstSource.promise;
            if (url.includes("end_line=7")) return secondSource.promise;
            return null;
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(<RelationshipsView snapshotId={snapshot.snapshot_id} />);

        const resolvedButton = await screen.findByRole("button", { name: /resolved-static/ });
        const outgoingHeading = screen.getByRole("heading", {
            name: "Outgoing relationships",
        });
        const outgoing = outgoingHeading.parentElement as HTMLElement;
        await user.click(resolvedButton);
        await user.click(within(outgoing).getByRole("button", { name: /unresolved-dynamic/ }));
        secondSource.resolve(sourceResponse(4, "later unresolved source"));
        expect(await screen.findByText("later unresolved source")).toBeTruthy();
        firstSource.resolve(sourceResponse(3, "stale resolved source"));

        await waitFor(() => {
            expect(screen.queryByText("stale resolved source")).toBeNull();
            expect(screen.getByText("later unresolved source")).toBeTruthy();
            expect(screen.getByText("import external.module")).toBeTruthy();
        });
    });

    it("ignores a stale source rejection after a later source succeeds", async () => {
        const firstSource = deferred<Response>();
        const secondSource = deferred<Response>();
        vi.stubGlobal(
            "fetch",
            relationshipFetch((url) => {
                if (url.includes("end_line=6")) return firstSource.promise;
                if (url.includes("end_line=7")) return secondSource.promise;
                return null;
            }),
        );
        const user = userEvent.setup();
        render(<RelationshipsView snapshotId={snapshot.snapshot_id} />);

        const firstButton = await screen.findByRole("button", { name: /resolved-static/ });
        const outgoing = screen.getByRole("heading", {
            name: "Outgoing relationships",
        }).parentElement as HTMLElement;
        await user.click(firstButton);
        await user.click(within(outgoing).getByRole("button", { name: /unresolved-dynamic/ }));
        secondSource.resolve(sourceResponse(4, "later source remains"));
        expect(await screen.findByText("later source remains")).toBeTruthy();
        firstSource.reject(new Error("stale source failed"));

        await waitFor(() => {
            expect(screen.getByText("later source remains")).toBeTruthy();
        });
        expect(screen.queryByText("Source evidence could not be loaded.")).toBeNull();
    });

    it("renders old-snapshot, error, truncation, and narrow-layout states safely", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn((input: RequestInfo | URL) => {
                const url = String(input);
                if (url.includes("/relationships/summary")) {
                    return Promise.resolve(
                        response({ ...relationshipSummary, supported: false, nodes: [] }),
                    );
                }
                return Promise.resolve(response({ supported: false, items: [], truncated: false }));
            }),
        );
        const old = render(<RelationshipsView snapshotId={snapshot.snapshot_id} />);
        expect(await screen.findByText(/predates relationship analysis/)).toBeTruthy();
        old.unmount();

        vi.stubGlobal(
            "fetch",
            vi
                .fn()
                .mockImplementation(() =>
                    Promise.resolve(response({ detail: "Relationship request failed." }, 500)),
                ),
        );
        const failed = render(<RelationshipsView snapshotId={snapshot.snapshot_id} />);
        expect(await screen.findByRole("alert")).toHaveProperty(
            "textContent",
            "Relationship request failed.",
        );
        failed.unmount();

        Object.defineProperty(window, "innerWidth", { configurable: true, value: 375 });
        vi.stubGlobal(
            "fetch",
            relationshipFetch(undefined, {
                ...relationshipNeighborhood,
                truncated: true,
            }),
        );
        const narrow = render(<RelationshipsView snapshotId={snapshot.snapshot_id} />);
        expect(await screen.findByText(/Results were truncated/)).toBeTruthy();
        expect(narrow.container.querySelector(".relationship-workspace")).not.toBeNull();
        expect(narrow.container.querySelector("[style]")).toBeNull();
    });
});

function relationshipFetch(
    sourceOverride?: (url: string) => Promise<Response> | null,
    neighborhood: RelationshipNeighborhood = relationshipNeighborhood,
) {
    return vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/relationships/summary")) {
            return Promise.resolve(response(relationshipSummary));
        }
        if (url.includes("/cycles")) {
            return Promise.resolve(
                response({ supported: true, items: [cycleGroup], truncated: false }),
            );
        }
        if (url.includes("/relationships/neighborhood")) {
            const mode = new URL(url, "http://localhost").searchParams.get("mode");
            if (mode === "packages") {
                return Promise.resolve(
                    response({
                        ...neighborhood,
                        mode: "packages",
                        focus_id: packageNode.node_id,
                        nodes: [packageNode],
                        relationships: [],
                        distances: { [packageNode.node_id]: 0 },
                    }),
                );
            }
            if (mode === "inheritance") {
                return Promise.resolve(
                    response({
                        ...neighborhood,
                        mode: "inheritance",
                        focus_id: classNode.node_id,
                        nodes: [classNode],
                        relationships: [],
                        distances: { [classNode.node_id]: 0 },
                    }),
                );
            }
            return Promise.resolve(response(neighborhood));
        }
        if (url.includes("/source?")) {
            const overridden = sourceOverride?.(url);
            if (overridden) return overridden;
            return Promise.resolve(sourceResponse(importRelationship.line, "from . import b"));
        }
        return Promise.resolve(response({ detail: "Unexpected request" }, 500));
    });
}

function sourceResponse(line: number, text: string): Response {
    return response({
        relative_path: "pkg/a.py",
        start_line: line,
        end_line: line,
        lines: [{ number: line, text }],
        truncated: false,
        content_hash: `hash-${line}`,
    });
}
