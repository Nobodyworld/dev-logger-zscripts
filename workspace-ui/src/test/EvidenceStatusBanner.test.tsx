import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EvidenceStatusBanner } from "../components/EvidenceStatusBanner";
import type { SnapshotEvidenceStatus } from "../types";
import { completeEvidenceStatus, partialEvidenceStatus, snapshot } from "./fixtures";

describe("EvidenceStatusBanner", () => {
    it("renders nothing for complete supported evidence", () => {
        const { container } = render(<EvidenceStatusBanner status={completeEvidenceStatus()} />);

        expect(container.innerHTML).toBe("");
    });

    it("renders multiple stable limitation labels and full consequences", () => {
        render(<EvidenceStatusBanner status={partialEvidenceStatus()} />);

        expect(screen.getByRole("heading", { name: "Partial evidence" })).toBeTruthy();
        expect(screen.getByText("snapshot-parse-gaps")).toBeTruthy();
        expect(screen.getByText("lifecycle-parse-gaps")).toBeTruthy();
        expect(screen.getByText(/Evidence derived from those files may be absent/i)).toBeTruthy();
        expect(screen.getByText(/Previously active findings may remain active/i)).toBeTruthy();
    });

    it("identifies baseline, target, unknown historical state, and unsupported evidence", () => {
        const historical: SnapshotEvidenceStatus = {
            ...completeEvidenceStatus("historical-snapshot"),
            evidence_complete: false,
            observation_state_known: false,
            limitations: [
                {
                    code: "observation-state-unknown",
                    category: "historical",
                    consequence:
                        "Branch, Git SHA, and working-tree facts were not recorded for this historical snapshot.",
                    count: null,
                },
            ],
        };
        const unsupported: SnapshotEvidenceStatus = {
            ...historical,
            snapshot_id: "unsupported-snapshot",
            limitations: [
                {
                    code: "snapshot-schema-unsupported",
                    category: "unsupported",
                    consequence:
                        "This view cannot interpret the stored evidence version. Run a new scan to produce currently supported evidence.",
                    count: null,
                },
            ],
        };
        render(
            <>
                <EvidenceStatusBanner status={partialEvidenceStatus()} side="baseline" />
                <EvidenceStatusBanner status={historical} side="target" />
                <EvidenceStatusBanner status={unsupported} />
            </>,
        );

        expect(screen.getByText("Baseline evidence is partial.")).toBeTruthy();
        expect(screen.getByText("Target historical state is unknown.")).toBeTruthy();
        expect(screen.getByText("Unsupported evidence")).toBeTruthy();
    });

    it("uses one stable polite status region across an unrelated rerender", () => {
        const status = partialEvidenceStatus(snapshot.snapshot_id);
        const { rerender } = render(<EvidenceStatusBanner status={status} />);
        const region = screen.getByRole("status", { name: "Snapshot evidence status" });

        rerender(<EvidenceStatusBanner status={status} />);

        expect(screen.getAllByRole("status")).toHaveLength(1);
        expect(screen.getByRole("status")).toBe(region);
        expect(region.getAttribute("aria-live")).toBe("polite");
        expect(region.getAttribute("aria-atomic")).toBe("true");
    });
});
