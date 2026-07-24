import type { Overview } from "../types";

interface OverviewViewProps {
    overview: Overview;
}

export function OverviewView({ overview }: OverviewViewProps) {
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
        </section>
    );
}

function formatDuration(milliseconds: number): string {
    const seconds = Math.max(0, Math.round(milliseconds / 1000));
    const minutes = Math.floor(seconds / 60);
    return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}
