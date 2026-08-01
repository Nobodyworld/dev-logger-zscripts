import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RepositoryHeader } from "../components/RepositoryHeader";
import type { SnapshotChoice } from "../types";
import { overview, snapshot } from "./fixtures";

const sameMinuteChoices: SnapshotChoice[] = [
    {
        ...snapshot,
        snapshot_id: "snapshot-aaaaaaaa11111111",
        completed_at: "2026-08-01T18:42:04.000Z",
        observed_state_known: true,
        branch: "branch-a",
        git_sha: "55f20e0c17d1ea0f",
        dirty: false,
        staged: false,
        untracked: false,
        parse_gap_count: 0,
        lifecycle_reconciled: true,
        reconciliation_skip_reason: null,
    },
    {
        ...snapshot,
        snapshot_id: "snapshot-bbbbbbbb22222222",
        completed_at: "2026-08-01T18:42:49.000Z",
        observed_state_known: true,
        branch: "branch-b",
        git_sha: "55f20e0c17d1ea0f",
        dirty: true,
        staged: true,
        untracked: true,
        truncated: true,
        parse_gap_count: 2,
        lifecycle_reconciled: false,
        reconciliation_skip_reason: "truncated-scan",
    },
];

describe("RepositoryHeader", () => {
    it("renders same-minute enriched choices as distinct full accessible labels", () => {
        render(
            <RepositoryHeader
                overview={{ ...overview, snapshot: sameMinuteChoices[0] }}
                snapshots={sameMinuteChoices}
                onSnapshotChange={vi.fn()}
            />,
        );

        const options = screen.getAllByRole("option");
        expect(options.map((option) => option.textContent)).toEqual([
            "2026-08-01 18:42:04Z · branch-a @ 55f20e0c · snapshot …11111111 · complete · clean",
            "2026-08-01 18:42:49Z · branch-b @ 55f20e0c · snapshot …22222222 · truncated + 2 parse gaps · dirty + staged + untracked",
        ]);
        expect(options[0].textContent).not.toBe(options[1].textContent);
        expect(screen.getByText(/Selected snapshot:/).textContent).toContain("…11111111");
    });

    it("preserves option order, exact values, and native keyboard selection", async () => {
        const onSnapshotChange = vi.fn();
        const user = userEvent.setup();
        render(
            <RepositoryHeader
                overview={{ ...overview, snapshot: sameMinuteChoices[0] }}
                snapshots={sameMinuteChoices}
                onSnapshotChange={onSnapshotChange}
            />,
        );

        const selector = screen.getByLabelText("Current snapshot") as HTMLSelectElement;
        expect(Array.from(selector.options, (option) => option.value)).toEqual(
            sameMinuteChoices.map((choice) => choice.snapshot_id),
        );
        await user.selectOptions(selector, sameMinuteChoices[1].snapshot_id);
        expect(onSnapshotChange).toHaveBeenCalledWith(sameMinuteChoices[1].snapshot_id);
    });

    it("keeps unknown observation truthful while exposing partial state", () => {
        const unknownChoice: SnapshotChoice = {
            ...sameMinuteChoices[1],
            observed_state_known: false,
            branch: null,
            git_sha: null,
            dirty: null,
            staged: null,
            untracked: null,
        };
        render(
            <RepositoryHeader
                overview={{ ...overview, snapshot: unknownChoice }}
                snapshots={[unknownChoice]}
                onSnapshotChange={vi.fn()}
            />,
        );

        const optionName = screen.getByRole("option").textContent ?? "";
        expect(optionName).toContain("observation unknown");
        expect(optionName).toContain("truncated + 2 parse gaps");
        expect(optionName).not.toContain("detached");
        expect(optionName).not.toContain("clean");
        expect(screen.getByText(/Selected snapshot:/).textContent).toContain(optionName);
    });
});
