import type { ComparisonSection, ComparisonSectionCompatibility } from "./types";

const REASON_LABELS: Record<string, string> = {
    "baseline-schema-unsupported": "the baseline schema is unsupported",
    "target-schema-unsupported": "the target schema is unsupported",
    "version-mismatch": "baseline and target evidence versions differ",
    "baseline-truncated": "baseline evidence is truncated",
    "target-truncated": "target evidence is truncated",
    "baseline-parse-gaps": "baseline evidence has parse gaps",
    "target-parse-gaps": "target evidence has parse gaps",
    "baseline-lifecycle-incomplete": "baseline lifecycle authority is incomplete",
    "target-lifecycle-incomplete": "target lifecycle authority is incomplete",
};

export function comparisonCompatibilityMessage(
    section: ComparisonSection,
    compatibility: ComparisonSectionCompatibility,
): string {
    const reasons = compatibility.reason_codes.map((reason) => REASON_LABELS[reason] ?? reason);
    return `${sectionLabel(section)} comparison is ${compatibility.status} because ${
        reasons.join("; ") || "the evidence is unavailable"
    }.`;
}

function sectionLabel(section: ComparisonSection): string {
    return section[0]?.toUpperCase() + section.slice(1);
}
