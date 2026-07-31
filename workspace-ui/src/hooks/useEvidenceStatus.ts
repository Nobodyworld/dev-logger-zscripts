import { useEffect, useState } from "react";

import { getSnapshotEvidenceStatus } from "../api";
import type { SnapshotEvidenceStatus } from "../types";

const STATUS_ERROR = "Evidence status is temporarily unavailable.";

interface EvidenceStatusState {
    status: SnapshotEvidenceStatus | null;
    error: string | null;
}

interface LoadedEvidenceStatusState extends EvidenceStatusState {
    snapshotId: string;
}

interface EvidenceStatusPairState {
    baseline: SnapshotEvidenceStatus | null;
    target: SnapshotEvidenceStatus | null;
    baselineError: string | null;
    targetError: string | null;
}

interface LoadedEvidenceStatusPairState extends EvidenceStatusPairState {
    pairKey: string;
}

const emptyStatus: EvidenceStatusState = { status: null, error: null };
const emptyPair: EvidenceStatusPairState = {
    baseline: null,
    target: null,
    baselineError: null,
    targetError: null,
};

export function useEvidenceStatus(snapshotId: string): EvidenceStatusState {
    const [state, setState] = useState<LoadedEvidenceStatusState>({
        ...emptyStatus,
        snapshotId: "",
    });

    useEffect(() => {
        const controller = new AbortController();
        if (!snapshotId) return () => controller.abort();
        void getSnapshotEvidenceStatus(snapshotId, controller.signal)
            .then((status) => {
                if (!isEvidenceStatus(status)) throw new Error("Invalid evidence status response.");
                if (!controller.signal.aborted) setState({ snapshotId, status, error: null });
            })
            .catch(() => {
                if (!controller.signal.aborted) {
                    setState({ snapshotId, status: null, error: STATUS_ERROR });
                }
            });
        return () => controller.abort();
    }, [snapshotId]);

    return state.snapshotId === snapshotId ? state : emptyStatus;
}

export function useEvidenceStatusPair(
    baselineSnapshotId: string,
    targetSnapshotId: string,
): EvidenceStatusPairState {
    const pairKey = `${baselineSnapshotId}\0${targetSnapshotId}`;
    const [state, setState] = useState<LoadedEvidenceStatusPairState>({
        ...emptyPair,
        pairKey: "",
    });

    useEffect(() => {
        const controller = new AbortController();
        if (!baselineSnapshotId || !targetSnapshotId) return () => controller.abort();
        void Promise.allSettled([
            getSnapshotEvidenceStatus(baselineSnapshotId, controller.signal).then(
                requireEvidenceStatus,
            ),
            getSnapshotEvidenceStatus(targetSnapshotId, controller.signal).then(
                requireEvidenceStatus,
            ),
        ]).then(([baseline, target]) => {
            if (controller.signal.aborted) return;
            setState({
                pairKey,
                baseline: baseline.status === "fulfilled" ? baseline.value : null,
                target: target.status === "fulfilled" ? target.value : null,
                baselineError: baseline.status === "rejected" ? STATUS_ERROR : null,
                targetError: target.status === "rejected" ? STATUS_ERROR : null,
            });
        });
        return () => controller.abort();
    }, [baselineSnapshotId, pairKey, targetSnapshotId]);

    return state.pairKey === pairKey ? state : emptyPair;
}

function requireEvidenceStatus(status: SnapshotEvidenceStatus): SnapshotEvidenceStatus {
    if (!isEvidenceStatus(status)) throw new Error("Invalid evidence status response.");
    return status;
}

function isEvidenceStatus(status: SnapshotEvidenceStatus): boolean {
    return (
        typeof status.evidence_complete === "boolean" &&
        Array.isArray(status.limitations) &&
        typeof status.snapshot_id === "string"
    );
}
