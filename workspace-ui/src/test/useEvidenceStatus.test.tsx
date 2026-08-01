import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useEvidenceStatus } from "../hooks/useEvidenceStatus";
import type { EvidenceStatusSurface } from "../types";
import { completeEvidenceStatus, response } from "./fixtures";

interface Deferred<T> {
    promise: Promise<T>;
    resolve: (value: T) => void;
}

function deferred<T>(): Deferred<T> {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((resolvePromise) => {
        resolve = resolvePromise;
    });
    return { promise, resolve };
}

function StatusHarness({
    snapshotId,
    surface,
}: {
    snapshotId: string;
    surface: EvidenceStatusSurface;
}) {
    const state = useEvidenceStatus(snapshotId, surface);
    return (
        <output data-testid="loaded-status">
            {state.error ??
                (state.status ? `${state.status.snapshot_id}:${state.status.surface}` : "empty")}
        </output>
    );
}

describe("useEvidenceStatus", () => {
    it("keys requests by surface and ignores a stale response from the previous surface", async () => {
        const overview = deferred<Response>();
        const findings = deferred<Response>();
        const fetchMock = vi.fn((input: RequestInfo | URL) => {
            const url = String(input);
            return url.includes("surface=overview") ? overview.promise : findings.promise;
        });
        vi.stubGlobal("fetch", fetchMock);
        const { rerender } = render(<StatusHarness snapshotId="snapshot-a" surface="overview" />);

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith(
                "/api/snapshots/snapshot-a/evidence-status?surface=overview",
                expect.objectContaining({ signal: expect.any(AbortSignal) }),
            );
        });
        rerender(<StatusHarness snapshotId="snapshot-a" surface="findings" />);
        expect(screen.getByTestId("loaded-status").textContent).toBe("empty");
        overview.resolve(response(completeEvidenceStatus("snapshot-a", "overview")));
        expect(screen.getByTestId("loaded-status").textContent).toBe("empty");
        findings.resolve(response(completeEvidenceStatus("snapshot-a", "findings")));

        await waitFor(() => {
            expect(screen.getByTestId("loaded-status").textContent).toBe("snapshot-a:findings");
        });
        expect(fetchMock).toHaveBeenCalledWith(
            "/api/snapshots/snapshot-a/evidence-status?surface=findings",
            expect.objectContaining({ signal: expect.any(AbortSignal) }),
        );
    });

    it("clears the previous snapshot immediately while the next status is loading", async () => {
        const next = deferred<Response>();
        vi.stubGlobal(
            "fetch",
            vi.fn((input: RequestInfo | URL) => {
                const url = String(input);
                return url.includes("snapshot-a")
                    ? Promise.resolve(response(completeEvidenceStatus("snapshot-a", "symbols")))
                    : next.promise;
            }),
        );
        const { rerender } = render(<StatusHarness snapshotId="snapshot-a" surface="symbols" />);
        expect(await screen.findByText("snapshot-a:symbols")).toBeTruthy();

        rerender(<StatusHarness snapshotId="snapshot-b" surface="symbols" />);
        expect(screen.getByTestId("loaded-status").textContent).toBe("empty");
        next.resolve(response(completeEvidenceStatus("snapshot-b", "symbols")));

        expect(await screen.findByText("snapshot-b:symbols")).toBeTruthy();
    });
});
