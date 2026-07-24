import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SymbolsView } from "../components/SymbolsView";
import { response, snapshot, symbol } from "./fixtures";

describe("SymbolsView", () => {
    it("searches, filters, escapes repository text, and opens bounded source evidence", async () => {
        const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
            const url = String(input);
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
            return response({
                items: [symbol],
                total: 1,
                page: 1,
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

        const unsafeName = await screen.findByRole("button", {
            name: "<img src=x onerror=alert(1)>",
        });
        expect(container.querySelector("img")).toBeNull();
        await user.type(screen.getByPlaceholderText("Search symbols"), "analyze");
        await user.selectOptions(screen.getByLabelText("Kind"), "method");
        await user.click(unsafeName);

        expect(await screen.findByRole("heading", { name: "Source evidence" })).toBeTruthy();
        expect(screen.getByLabelText("Read-only source excerpt")).toBeTruthy();
        expect(screen.getByRole("button", { name: "Close source evidence" })).toBeTruthy();
        await waitFor(() => {
            expect(
                fetchMock.mock.calls.some(([url]) => String(url).includes("search=analyze")),
            ).toBe(true);
        });
    });
});
