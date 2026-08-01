import type { SnapshotChoice } from "./types";

export const SNAPSHOT_LABEL_PRESENTATION_VERSION = "1";

const SNAPSHOT_SUFFIX_LENGTH = 8;
const GIT_SHA_PREFIX_LENGTH = 8;

export function formatSnapshotChoiceLabel(snapshot: SnapshotChoice): string {
    return [
        formatCompletionTime(snapshot.completed_at),
        formatObservation(snapshot),
        snapshotReferenceLabel(snapshot.snapshot_id, "snapshot"),
        ...snapshotStateMarkers(snapshot),
    ].join(" · ");
}

export function snapshotStateMarkers(snapshot: SnapshotChoice): string[] {
    const evidence = formatPartialState(snapshot.truncated, snapshot.parse_gap_count);
    if (!snapshot.observed_state_known) return [evidence];

    const worktree: string[] = [];
    if (snapshot.dirty) worktree.push("dirty");
    if (snapshot.staged) worktree.push("staged");
    if (snapshot.untracked) worktree.push("untracked");
    return [evidence, worktree.length > 0 ? worktree.join(" + ") : "clean"];
}

export function formatSnapshotReference(snapshotId: string): string {
    return snapshotReferenceLabel(snapshotId, "Snapshot");
}

function formatCompletionTime(value: string | null): string {
    if (!value) return "Completion time unavailable";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "Completion time unavailable";
    const iso = parsed.toISOString();
    return `${iso.slice(0, 10)} ${iso.slice(11, 19)}Z`;
}

function formatObservation(snapshot: SnapshotChoice): string {
    if (!snapshot.observed_state_known) return "observation unknown";
    const repositoryState = snapshot.branch ?? "detached";
    return snapshot.git_sha
        ? `${repositoryState} @ ${snapshot.git_sha.slice(0, GIT_SHA_PREFIX_LENGTH)}`
        : `${repositoryState} · no Git SHA`;
}

function formatPartialState(truncated: boolean, parseGapCount: number): string {
    const parseGaps = Math.max(0, parseGapCount);
    if (truncated && parseGaps > 0) {
        return `truncated + ${formatParseGaps(parseGaps)}`;
    }
    if (truncated) return "truncated";
    if (parseGaps > 0) return formatParseGaps(parseGaps);
    return "complete";
}

function formatParseGaps(count: number): string {
    return `${count} parse ${count === 1 ? "gap" : "gaps"}`;
}

function snapshotReferenceLabel(snapshotId: string, prefix: "Snapshot" | "snapshot"): string {
    const suffix = snapshotId.slice(-SNAPSHOT_SUFFIX_LENGTH) || "unknown";
    return `${prefix} …${suffix}`;
}
