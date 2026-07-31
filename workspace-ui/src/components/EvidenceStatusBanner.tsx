import { memo } from "react";

import type { EvidenceLimitationCode, SnapshotEvidenceStatus } from "../types";

interface EvidenceStatusBannerProps {
    title?: string;
    status: SnapshotEvidenceStatus | null;
    side?: "snapshot" | "baseline" | "target";
    compact?: boolean;
    error?: string | null;
}

const LIMITATION_LABELS: Record<EvidenceLimitationCode, string> = {
    "snapshot-truncated": "Snapshot truncated",
    "snapshot-parse-gaps": "Parse gaps",
    "snapshot-schema-unsupported": "Unsupported evidence version",
    "observation-state-unknown": "Historical observation unknown",
    "lifecycle-truncated-scan": "Finding resolution skipped",
    "lifecycle-parse-gaps": "Finding resolution skipped",
    "lifecycle-superseded": "Superseded analysis",
    "lifecycle-analysis-status-unavailable": "Lifecycle status unavailable",
};

function EvidenceStatusBannerComponent({
    title,
    status,
    side = "snapshot",
    compact = false,
    error = null,
}: EvidenceStatusBannerProps) {
    if (error) {
        return (
            <section
                className="evidence-status evidence-status--error"
                aria-label="Evidence status"
            >
                <h3>Evidence status unavailable</h3>
                <p>{error}</p>
            </section>
        );
    }
    if (!status || status.evidence_complete || status.limitations.length === 0) return null;
    const heading = title ?? statusHeading(status, side);
    return (
        <section
            className={`evidence-status ${compact ? "evidence-status--compact" : ""}`}
            role="status"
            aria-live="polite"
            aria-atomic="true"
            aria-label={
                side === "snapshot" ? "Snapshot evidence status" : `${side} evidence status`
            }
        >
            <h3>{heading}</h3>
            <ul>
                {status.limitations.map((limitation) => (
                    <li key={limitation.code}>
                        <div className="evidence-status__label">
                            <strong>{LIMITATION_LABELS[limitation.code]}</strong>
                            <code>{limitation.code}</code>
                            {limitation.count === null ? null : (
                                <span>{limitation.count.toLocaleString()}</span>
                            )}
                        </div>
                        <p>{limitation.consequence}</p>
                    </li>
                ))}
            </ul>
        </section>
    );
}

function statusHeading(
    status: SnapshotEvidenceStatus,
    side: "snapshot" | "baseline" | "target",
): string {
    const sideLabel = side === "baseline" ? "Baseline" : "Target";
    if (status.limitations.some((item) => item.category === "unsupported")) {
        return side === "snapshot"
            ? "Unsupported evidence"
            : `${sideLabel} evidence is unsupported.`;
    }
    if (status.limitations.some((item) => item.category === "partial")) {
        return side === "snapshot" ? "Partial evidence" : `${sideLabel} evidence is partial.`;
    }
    if (status.limitations.some((item) => item.category === "historical")) {
        return side === "snapshot"
            ? "Historical state unknown"
            : `${sideLabel} historical state is unknown.`;
    }
    return side === "snapshot"
        ? "Finding lifecycle authority is limited."
        : `${sideLabel} finding lifecycle authority is limited.`;
}

export const EvidenceStatusBanner = memo(EvidenceStatusBannerComponent);
