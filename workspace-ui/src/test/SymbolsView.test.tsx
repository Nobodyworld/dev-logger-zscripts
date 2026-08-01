import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SymbolsView } from "../components/SymbolsView";
import {
    completeEvidenceStatus,
    partialEvidenceStatus,
    response,
    snapshot,
    symbol,
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

const secondSymbol = {
    ...symbol,
    symbol_id: "symbol-second",
    qualified_name: "pkg.module.second",
    display_name: "second",
    relative_path: "pkg/second.py",
    start_line: 7,
    end_line: 8,
};

function sourceResponse(relativePath: string, line: number, text: string): Response {
    return response({
        relative_path: relativePath,
        start_line: line,
        end_line: line,
        lines: [{ number: line, text }],
        truncated: false,
        content_hash: `hash-${line}`,
    });
}

describe("SymbolsView", () => {
    it("searches, filters, escapes repository text, and opens bounded source evidence", async () => {
        const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
            const url = String(input);
            if (url.includes("/evidence-status")) {
                return response(partialEvidenceStatus(snapshot.snapshot_id, "symbols"));
            }
            if (url.includes("/source?")) {
                return response({
                    relative_path: symbol.relative_path,
                    start_line: 42,
                    end_line: 43,
                    lines: [
                        { number: 42, text: "def analyze(path: Path):" },
                        { number: 43, text: "    return evidence" },
                    ],
                    truncated: false,
                    content_hash: "abcdef",
                });
            }
            const parameters = new URL(url, "http://localhost").searchParams;
            return response({
                items: [symbol],
                total: 51,
                page: Number(parameters.get("page") ?? "1"),
                page_size: 50,
                filters: {
                    kinds: ["method"],
                    modules: [symbol.module_name],
                    visibilities: ["public"],
                },
            });
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        const { container } = render(<SymbolsView snapshotId={snapshot.snapshot_id} />);

        await screen.findByRole("button", {
            name: "<img src=x onerror=alert(1)>",
        });
        expect(await screen.findByRole("heading", { name: "Partial evidence" })).toBeTruthy();
        expect(container.querySelector("img")).toBeNull();
        await user.type(screen.getByPlaceholderText("Search symbols"), "analyze");
        await user.selectOptions(screen.getByLabelText("Kind"), "method");
        expect(screen.getByRole("heading", { name: "Partial evidence" })).toBeTruthy();
        await user.click(screen.getByRole("button", { name: "Next" }));
        expect(screen.getByRole("heading", { name: "Partial evidence" })).toBeTruthy();
        await user.click(screen.getByRole("button", { name: "<img src=x onerror=alert(1)>" }));

        expect(await screen.findByRole("heading", { name: "Source evidence" })).toBeTruthy();
        expect(screen.getByLabelText("Read-only source excerpt")).toBeTruthy();
        expect(screen.getByRole("button", { name: "Close source evidence" })).toBeTruthy();
        expect(screen.getByRole("heading", { name: "Partial evidence" })).toBeTruthy();
        await waitFor(() => {
            expect(
                fetchMock.mock.calls.some(([url]) => String(url).includes("search=analyze")),
            ).toBe(true);
        });
    });

    it("keeps the later symbol and source when an earlier request resolves afterward", async () => {
        const firstSource = deferred<Response>();
        const secondSource = deferred<Response>();
        vi.stubGlobal(
            "fetch",
            vi.fn((input: RequestInfo | URL) => {
                const url = String(input);
                if (url.includes("/source?") && url.includes("pkg%2Fsecond.py")) {
                    return secondSource.promise;
                }
                if (url.includes("/source?")) return firstSource.promise;
                return Promise.resolve(
                    response({
                        items: [symbol, secondSymbol],
                        total: 2,
                        page: 1,
                        page_size: 50,
                        filters: { kinds: [], modules: [], visibilities: [] },
                    }),
                );
            }),
        );
        const user = userEvent.setup();
        render(<SymbolsView snapshotId={snapshot.snapshot_id} />);

        await user.click(await screen.findByRole("button", { name: symbol.qualified_name }));
        await user.click(screen.getByRole("button", { name: secondSymbol.qualified_name }));
        secondSource.resolve(sourceResponse(secondSymbol.relative_path, 7, "second source"));

        expect(await screen.findByText("second source")).toBeTruthy();
        const drawer = screen.getByRole("complementary");
        expect(within(drawer).getByText(secondSymbol.relative_path)).toBeTruthy();
        firstSource.resolve(sourceResponse(symbol.relative_path, 42, "stale first source"));

        await waitFor(() => {
            expect(screen.queryByText("stale first source")).toBeNull();
            expect(screen.getByText("second source")).toBeTruthy();
            expect(within(drawer).getByText(secondSymbol.relative_path)).toBeTruthy();
        });
    });

    it("ignores an earlier source rejection after the later request succeeds", async () => {
        const firstSource = deferred<Response>();
        const secondSource = deferred<Response>();
        vi.stubGlobal(
            "fetch",
            vi.fn((input: RequestInfo | URL) => {
                const url = String(input);
                if (url.includes("/source?") && url.includes("pkg%2Fsecond.py")) {
                    return secondSource.promise;
                }
                if (url.includes("/source?")) return firstSource.promise;
                return Promise.resolve(
                    response({
                        items: [symbol, secondSymbol],
                        total: 2,
                        page: 1,
                        page_size: 50,
                        filters: { kinds: [], modules: [], visibilities: [] },
                    }),
                );
            }),
        );
        const user = userEvent.setup();
        render(<SymbolsView snapshotId={snapshot.snapshot_id} />);

        await user.click(await screen.findByRole("button", { name: symbol.qualified_name }));
        await user.click(screen.getByRole("button", { name: secondSymbol.qualified_name }));
        secondSource.resolve(sourceResponse(secondSymbol.relative_path, 7, "second source"));
        expect(await screen.findByText("second source")).toBeTruthy();
        firstSource.reject(new Error("stale request failed"));

        await waitFor(() => {
            expect(screen.queryByText("Source evidence could not be loaded.")).toBeNull();
            expect(screen.getByText("second source")).toBeTruthy();
            expect(
                within(screen.getByRole("complementary")).getByText(secondSymbol.relative_path),
            ).toBeTruthy();
        });
    });

    it("requests the symbols surface without an unsupported banner for schema 3", async () => {
        const fetchMock = vi.fn((input: RequestInfo | URL) => {
            const url = String(input);
            if (url.includes("/evidence-status")) {
                return Promise.resolve(
                    response(completeEvidenceStatus(snapshot.snapshot_id, "symbols")),
                );
            }
            return Promise.resolve(
                response({
                    items: [symbol],
                    total: 1,
                    page: 1,
                    page_size: 50,
                    filters: { kinds: [], modules: [], visibilities: [] },
                }),
            );
        });
        vi.stubGlobal("fetch", fetchMock);

        render(<SymbolsView snapshotId={snapshot.snapshot_id} />);

        expect(await screen.findByRole("button", { name: symbol.qualified_name })).toBeTruthy();
        expect(
            fetchMock.mock.calls.some(([input]) =>
                String(input).includes("evidence-status?surface=symbols"),
            ),
        ).toBe(true);
        expect(screen.queryByText("Unsupported evidence")).toBeNull();
    });
});
