import type { Overview } from "../types";

interface OverviewViewProps {
    overview: Overview;
    onOpenFindings: (preset: string) => void;
}

export function OverviewView({ overview, onOpenFindings }: OverviewViewProps) {
    const { counts, snapshot } = overview;
    const summary = [
        ["Files analyzed", counts.files_analyzed.toLocaleString()],
        ["Files excluded", counts.files_excluded.toLocaleString()],
        ["Packages", counts.packages.toLocaleString()],
        ["Modules", counts.modules.toLocaleString()],
        ["Classes", counts.classes.toLocaleString()],
        ["Functions", counts.functions.toLocaleString()],
        ["Methods", counts.methods.toLocaleString()],
        ["Parse gaps", counts.parse_gaps.toLocaleString()],
        ["Resolved imports", counts.resolved_import_edges.toLocaleString()],
        ["Inheritance edges", counts.inheritance_edges.toLocaleString()],
        ["Cycle groups", counts.cycle_groups.toLocaleString()],
        ["Largest cycle", counts.largest_cycle_size.toLocaleString()],
        ["Elapsed", formatDuration(snapshot.duration_ms)],
        ["Truncated", snapshot.truncated ? "Yes" : "No"],
    ];

    return (
        <section className="view" aria-labelledby="overview-heading">
            <h2 id="overview-heading">Overview</h2>
            <dl className="summary-band">
                {summary.map(([label, value]) => (
                    <div key={label}>
                        <dt>{label}</dt>
                        <dd>{value}</dd>
                    </div>
                ))}
            </dl>
            <dl className="version-list">
                <div>
                    <dt>Analyzer version</dt>
                    <dd className="mono">{snapshot.analyzer_version}</dd>
                </div>
                <div>
                    <dt>Schema version</dt>
                    <dd className="mono">{snapshot.schema_version}</dd>
                </div>
                <div>
                    <dt>Rule-set version</dt>
                    <dd className="mono">{snapshot.rule_set_version}</dd>
                </div>
                <div>
                    <dt>Source fingerprint</dt>
                    <dd className="mono">{snapshot.source_fingerprint.slice(0, 16)}</dd>
                </div>
            </dl>
            <div className="finding-overview-links" aria-label="Open filtered findings">
                {[
                    ["Active findings", counts.active_findings, "active"],
                    ["Needs action", counts.needs_action_findings, "needs-action"],
                    ["Resolved this scan", counts.resolved_since_last_scan, "resolved"],
                    [
                        "High confidence / severity",
                        counts.high_confidence_high_severity_findings,
                        "high-confidence-severity",
                    ],
                ].map(([label, value, preset]) => (
                    <button
                        type="button"
                        key={label}
                        onClick={() => onOpenFindings(String(preset))}
                    >
                        <span>{label}</span>
                        <strong>{Number(value).toLocaleString()}</strong>
                    </button>
                ))}
            </div>
        </section>
    );
}

function formatDuration(milliseconds: number): string {
    const seconds = Math.max(0, Math.round(milliseconds / 1000));
    const minutes = Math.floor(seconds / 60);
    return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}
