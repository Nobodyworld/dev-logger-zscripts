import { useEffect, useState } from "react";

import { getSnapshotEvidenceStatus } from "../api";
import type { EvidenceStatusSurface, SnapshotEvidenceStatus } from "../types";

const STATUS_ERROR = "Evidence status is temporarily unavailable.";

interface EvidenceStatusState {
    status: SnapshotEvidenceStatus | null;
    error: string | null;
}

interface LoadedEvidenceStatusState extends EvidenceStatusState {
    requestKey: string;
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

export function useEvidenceStatus(
    snapshotId: string,
    surface: EvidenceStatusSurface = "generic",
): EvidenceStatusState {
    const requestKey = `${snapshotId}\0${surface}`;
    const [state, setState] = useState<LoadedEvidenceStatusState>({
        ...emptyStatus,
        requestKey: "",
    });

    useEffect(() => {
        const controller = new AbortController();
        if (!snapshotId) return () => controller.abort();
        void getSnapshotEvidenceStatus(snapshotId, surface, controller.signal)
            .then((status) => {
                if (!isEvidenceStatus(status) || status.surface !== surface) {
                    throw new Error("Invalid evidence status response.");
                }
                if (!controller.signal.aborted) setState({ requestKey, status, error: null });
            })
            .catch(() => {
                if (!controller.signal.aborted) {
                    setState({ requestKey, status: null, error: STATUS_ERROR });
                }
            });
        return () => controller.abort();
    }, [requestKey, snapshotId, surface]);

    return state.requestKey === requestKey ? state : emptyStatus;
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
            getSnapshotEvidenceStatus(baselineSnapshotId, "generic", controller.signal).then(
                requireGenericEvidenceStatus,
            ),
            getSnapshotEvidenceStatus(targetSnapshotId, "generic", controller.signal).then(
                requireGenericEvidenceStatus,
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

function requireGenericEvidenceStatus(status: SnapshotEvidenceStatus): SnapshotEvidenceStatus {
    if (!isEvidenceStatus(status) || status.surface !== "generic") {
        throw new Error("Invalid evidence status response.");
    }
    return status;
}

function isEvidenceStatus(status: SnapshotEvidenceStatus): boolean {
    return (
        typeof status.evidence_complete === "boolean" &&
        Array.isArray(status.limitations) &&
        typeof status.snapshot_id === "string"
    );
}
