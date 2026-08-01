import { describe, expect, it } from "vitest";

import {
    formatSnapshotChoiceLabel,
    formatSnapshotReference,
    SNAPSHOT_LABEL_PRESENTATION_VERSION,
    snapshotStateMarkers,
} from "../snapshotLabels";
import type { SnapshotChoice } from "../types";
import { repository, snapshot } from "./fixtures";

const choice: SnapshotChoice = {
    ...snapshot,
    snapshot_id: "snapshot-aaaaaaaa55f20e0c",
    completed_at: "2026-08-01T18:42:04.987-05:00",
    observed_state_known: true,
    branch: "main",
    git_sha: "55f20e0c17d1ea0f",
    dirty: false,
    staged: false,
    untracked: false,
    truncated: false,
    parse_gap_count: 0,
    lifecycle_reconciled: true,
    reconciliation_skip_reason: null,
};

describe("snapshot labels", () => {
    it("uses presentation version 1 and stable UTC second precision", () => {
        expect(SNAPSHOT_LABEL_PRESENTATION_VERSION).toBe("1");
        expect(formatSnapshotChoiceLabel(choice)).toBe(
            "2026-08-01 23:42:04Z · main @ 55f20e0c · snapshot …55f20e0c · complete · clean",
        );
        expect(formatSnapshotChoiceLabel(choice)).toBe(formatSnapshotChoiceLabel(choice));
    });

    it("distinguishes same-minute and equal-time choices", () => {
        const later = {
            ...choice,
            snapshot_id: "snapshot-bbbbbbbb11223344",
            completed_at: "2026-08-01T23:42:49Z",
        };
        const equalTime = { ...later, completed_at: choice.completed_at };
        expect(formatSnapshotChoiceLabel(choice)).not.toBe(formatSnapshotChoiceLabel(later));
        expect(formatSnapshotChoiceLabel(choice)).not.toBe(formatSnapshotChoiceLabel(equalTime));
        expect(formatSnapshotChoiceLabel(later)).toContain("2026-08-01 23:42:49Z");
        expect(formatSnapshotChoiceLabel(equalTime)).toContain("snapshot …11223344");
    });

    it("uses branch, detached, missing-SHA, and observation-unknown facts truthfully", () => {
        expect(formatSnapshotChoiceLabel({ ...choice, branch: null })).toContain(
            "detached @ 55f20e0c",
        );
        expect(formatSnapshotChoiceLabel({ ...choice, git_sha: null })).toContain(
            "main · no Git SHA",
        );
        const unknown = formatSnapshotChoiceLabel({
            ...choice,
            observed_state_known: false,
            branch: "must-not-appear",
            git_sha: "must-not-appear",
            dirty: true,
            staged: true,
            untracked: true,
        });
        expect(unknown).toContain("observation unknown");
        expect(unknown).not.toMatch(/detached|clean|dirty|staged|untracked|no Git SHA/);
        expect(unknown).not.toContain("must-not-appear");
    });

    it("formats worktree markers in a deterministic order", () => {
        expect(snapshotStateMarkers(choice)).toEqual(["complete", "clean"]);
        expect(
            snapshotStateMarkers({
                ...choice,
                dirty: true,
                staged: true,
                untracked: true,
            }),
        ).toEqual(["complete", "dirty + staged + untracked"]);
        expect(snapshotStateMarkers({ ...choice, staged: true })).toEqual(["complete", "staged"]);
        expect(snapshotStateMarkers({ ...choice, untracked: true })).toEqual([
            "complete",
            "untracked",
        ]);
    });

    it("formats complete, truncation, and parse-gap states independently", () => {
        expect(snapshotStateMarkers({ ...choice, observed_state_known: false })).toEqual([
            "complete",
        ]);
        expect(
            snapshotStateMarkers({ ...choice, observed_state_known: false, truncated: true }),
        ).toEqual(["truncated"]);
        expect(
            snapshotStateMarkers({ ...choice, observed_state_known: false, parse_gap_count: 1 }),
        ).toEqual(["1 parse gap"]);
        expect(
            snapshotStateMarkers({ ...choice, observed_state_known: false, parse_gap_count: 3 }),
        ).toEqual(["3 parse gaps"]);
        expect(
            snapshotStateMarkers({
                ...choice,
                observed_state_known: false,
                truncated: true,
                parse_gap_count: 2,
            }),
        ).toEqual(["truncated + 2 parse gaps"]);
    });

    it("keeps missing or invalid completion time distinguishable by suffix", () => {
        for (const completed_at of [null, "not-a-time"]) {
            expect(formatSnapshotChoiceLabel({ ...choice, completed_at })).toContain(
                "Completion time unavailable · main @ 55f20e0c · snapshot …55f20e0c",
            );
        }
        expect(formatSnapshotReference("snapshot-missing-12345678")).toBe("Snapshot …12345678");
    });

    it("does not expose repository paths, source content, or full identifiers", () => {
        const label = formatSnapshotChoiceLabel(choice);
        expect(label).not.toContain(repository.repository_id);
        expect(label).not.toContain(snapshot.source_fingerprint);
        expect(label).not.toContain(choice.snapshot_id);
        expect(label).not.toMatch(/[A-Z]:\\|\/home\//);
    });
});
