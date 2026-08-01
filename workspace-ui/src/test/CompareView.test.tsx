import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CompareView } from "../components/CompareView";
import { formatSnapshotChoiceLabel } from "../snapshotLabels";
import type {
    ComparisonItem,
    ComparisonPage,
    ComparisonSection,
    ComparisonSummary,
    SnapshotChoice,
} from "../types";
import {
    completeEvidenceStatus,
    olderSnapshot,
    partialEvidenceStatus,
    repository,
    response,
    snapshot,
} from "./fixtures";

const comparisonSnapshots: SnapshotChoice[] = [
    {
        ...snapshot,
        analyzer_version: "3",
        schema_version: "4",
        rule_set_version: "4",
        observed_state_known: true,
        branch: "main",
        git_sha: repository.git_sha,
        dirty: false,
        staged: false,
        untracked: false,
        lifecycle_reconciled: false,
        reconciliation_skip_reason: "parse-gaps",
    },
    {
        ...olderSnapshot,
        analyzer_version: "3",
        schema_version: "4",
        rule_set_version: "4",
        observed_state_known: true,
        branch: "main",
        git_sha: "older0123456789",
        dirty: false,
        staged: false,
        untracked: false,
        lifecycle_reconciled: true,
        reconciliation_skip_reason: null,
    },
];

const summary: ComparisonSummary = {
    identity: {
        comparison_id: "comparison-test-id",
        repository_id: repository.repository_id,
        baseline_snapshot_id: olderSnapshot.snapshot_id,
        target_snapshot_id: snapshot.snapshot_id,
        comparison_format_version: "2",
    },
    compatibility: {
        same_repository: true,
        baseline_analyzer_version: "3",
        target_analyzer_version: "3",
        baseline_schema_version: "4",
        target_schema_version: "4",
        baseline_rule_set_version: "4",
        target_rule_set_version: "4",
        baseline_truncated: false,
        target_truncated: false,
        baseline_parse_gap_count: 0,
        target_parse_gap_count: 1,
        baseline_lifecycle_reconciled: true,
        target_lifecycle_reconciled: false,
        baseline_reconciliation_skip_reason: null,
        target_reconciliation_skip_reason: "parse-gaps",
        sections: [
            {
                section: "files",
                status: "partial",
                reason_codes: ["target-parse-gaps"],
            },
            { section: "symbols", status: "partial", reason_codes: ["target-parse-gaps"] },
            {
                section: "relationships",
                status: "partial",
                reason_codes: ["target-parse-gaps"],
            },
            { section: "cycles", status: "partial", reason_codes: ["target-parse-gaps"] },
            { section: "metrics", status: "partial", reason_codes: ["target-parse-gaps"] },
            {
                section: "findings",
                status: "partial",
                reason_codes: ["target-parse-gaps", "target-lifecycle-incomplete"],
            },
        ],
    },
    counts: {
        files_added: 1,
        files_removed: 0,
        files_not_observed: 1,
        files_changed: 1,
    },
    equal_snapshots: false,
};

const fileItem: ComparisonItem = {
    delta_id: "delta-file-0123456789abcdef",
    change_type: "changed",
    logical_key: "pkg/module.py",
    label: "pkg/module.py",
    relative_path: "pkg/module.py",
    baseline: { parse_status: "parsed", size_bytes: 10 },
    target: { parse_status: "parsed", size_bytes: 12 },
};

const symbolItem: ComparisonItem = {
    delta_id: "delta-symbol-0123456789abcdef",
    change_type: "added",
    logical_key: "python|class|pkg.NewType",
    label: "pkg.NewType",
    relative_path: "pkg/module.py",
};

describe("CompareView", () => {
    it("loads snapshots, exposes partial status, filters, paginates, and selects details", async () => {
        const fetchMock = comparisonFetch();
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(
            <CompareView
                repositoryId={repository.repository_id}
                targetSnapshotId={snapshot.snapshot_id}
            />,
        );

        expect(await screen.findByRole("heading", { name: "Compare" })).toBeTruthy();
        const baseline = screen.getByLabelText("Baseline") as HTMLSelectElement;
        const target = screen.getByLabelText("Target") as HTMLSelectElement;
        expect(baseline.value).toBe(olderSnapshot.snapshot_id);
        expect(target.value).toBe(snapshot.snapshot_id);
        expect(Array.from(target.options, (option) => option.value)).toEqual(
            comparisonSnapshots.map((choice) => choice.snapshot_id),
        );
        expect(Array.from(target.options, (option) => option.textContent)).toEqual(
            comparisonSnapshots.map(formatSnapshotChoiceLabel),
        );
        expect(await screen.findByText("Target evidence is partial.")).toBeTruthy();
        expect(screen.getByText(/target evidence has parse gaps/i)).toBeTruthy();
        expect(await screen.findByRole("button", { name: /pkg\/module\.py/ })).toBeTruthy();
        expect(
            screen.getByRole("status", { name: "target evidence status" }).textContent,
        ).toContain("partial");
        expect(screen.getByText("Repository-relative path")).toBeTruthy();

        await user.type(screen.getByPlaceholderText("Search files"), "module");
        await user.selectOptions(screen.getByLabelText("Change"), "changed");
        await user.click(screen.getByRole("tab", { name: "Symbols" }));

        expect(await screen.findByRole("button", { name: /pkg\.NewType/ })).toBeTruthy();
        await waitFor(() => {
            expect(
                fetchMock.mock.calls.some(([input]) => {
                    const url = String(input);
                    return (
                        url.includes("section=symbols") &&
                        url.includes("search=module") &&
                        url.includes("change_type=changed")
                    );
                }),
            ).toBe(true);
        });

        const metricsTab = screen.getByRole("tab", { name: "Metrics" });
        metricsTab.focus();
        await user.keyboard("{Enter}");
        expect(metricsTab.getAttribute("aria-selected")).toBe("true");
        await waitFor(() => {
            expect(
                fetchMock.mock.calls.some(([input]) => String(input).includes("section=metrics")),
            ).toBe(true);
        });
    });

    it("keeps generic schema-3 status neutral while version mismatch stays section-authoritative", async () => {
        const schemaThreeSnapshots = comparisonSnapshots.map((item) =>
            item.snapshot_id === olderSnapshot.snapshot_id
                ? { ...item, schema_version: "3" }
                : item,
        );
        const mismatchSummary: ComparisonSummary = {
            ...summary,
            compatibility: {
                ...summary.compatibility,
                baseline_schema_version: "3",
                target_schema_version: "4",
                sections: summary.compatibility.sections.map((item) => ({
                    ...item,
                    status: "partial",
                    reason_codes: ["version-mismatch"],
                })),
            },
        };
        const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
            const url = String(input);
            if (url.includes("comparison-snapshots")) {
                return response({ repository, snapshots: schemaThreeSnapshots });
            }
            if (url.includes("/evidence-status")) {
                const snapshotId = url.includes(olderSnapshot.snapshot_id)
                    ? olderSnapshot.snapshot_id
                    : snapshot.snapshot_id;
                return response(completeEvidenceStatus(snapshotId, "generic"));
            }
            if (url.includes("/comparisons/summary")) return response(mismatchSummary);
            if (url.includes("/comparisons/items")) {
                return response({
                    ...page("files", [fileItem]),
                    section_status: "partial",
                    reason_codes: ["version-mismatch"],
                });
            }
            return response({ detail: "Unexpected request" }, 500);
        });
        vi.stubGlobal("fetch", fetchMock);

        render(
            <CompareView
                repositoryId={repository.repository_id}
                targetSnapshotId={snapshot.snapshot_id}
            />,
        );

        expect(
            await screen.findByText(
                "Files comparison is partial because baseline and target evidence versions differ.",
            ),
        ).toBeTruthy();
        expect(screen.queryByText("Baseline evidence is unsupported.")).toBeNull();
        await waitFor(() => {
            const statusCalls = fetchMock.mock.calls.filter(([input]) =>
                String(input).includes("/evidence-status"),
            );
            expect(statusCalls).toHaveLength(2);
            expect(statusCalls.every(([input]) => String(input).includes("surface=generic"))).toBe(
                true,
            );
        });
    });

    it("ignores a stale section response after a newer request succeeds", async () => {
        let resolveFiles!: (value: Response) => void;
        const filesPromise = new Promise<Response>((resolve) => {
            resolveFiles = resolve;
        });
        const fetchMock = vi.fn((input: RequestInfo | URL) => {
            const url = String(input);
            if (url.includes("comparison-snapshots")) {
                return Promise.resolve(response({ repository, snapshots: comparisonSnapshots }));
            }
            if (url.includes("/comparisons/summary")) return Promise.resolve(response(summary));
            if (url.includes("section=files")) return filesPromise;
            if (url.includes("section=symbols")) {
                return Promise.resolve(response(page("symbols", [symbolItem])));
            }
            return Promise.resolve(response({ detail: "Unexpected request" }, 500));
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(
            <CompareView
                repositoryId={repository.repository_id}
                targetSnapshotId={snapshot.snapshot_id}
            />,
        );

        await screen.findByRole("heading", { name: "Compare" });
        await waitFor(() => {
            expect(
                fetchMock.mock.calls.some(([input]) => String(input).includes("section=files")),
            ).toBe(true);
        });
        await user.click(screen.getByRole("tab", { name: "Symbols" }));
        expect(await screen.findByRole("button", { name: /pkg\.NewType/ })).toBeTruthy();
        resolveFiles(response(page("files", [fileItem])));

        await waitFor(() => {
            expect(screen.queryByRole("button", { name: /^changed pkg\/module\.py/ })).toBeNull();
            expect(screen.getByRole("button", { name: /pkg\.NewType/ })).toBeTruthy();
        });
    });

    it("does not display a stale baseline status after the pair changes", async () => {
        let resolveOldStatus!: (value: Response) => void;
        const oldStatus = new Promise<Response>((resolve) => {
            resolveOldStatus = resolve;
        });
        const fetchMock = vi.fn((input: RequestInfo | URL) => {
            const url = String(input);
            if (url.includes("comparison-snapshots")) {
                return Promise.resolve(response({ repository, snapshots: comparisonSnapshots }));
            }
            if (url.includes("/evidence-status")) {
                return url.includes(olderSnapshot.snapshot_id)
                    ? oldStatus
                    : Promise.resolve(response(completeEvidenceStatus(snapshot.snapshot_id)));
            }
            if (url.includes("/comparisons/summary")) return Promise.resolve(response(summary));
            if (url.includes("/comparisons/items")) {
                return Promise.resolve(response(page("files", [fileItem])));
            }
            return Promise.resolve(response({ detail: "Unexpected request" }, 500));
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(
            <CompareView
                repositoryId={repository.repository_id}
                targetSnapshotId={snapshot.snapshot_id}
            />,
        );

        await waitFor(() => {
            expect(
                fetchMock.mock.calls.some(([input]) =>
                    String(input).includes(
                        `/snapshots/${olderSnapshot.snapshot_id}/evidence-status?surface=generic`,
                    ),
                ),
            ).toBe(true);
        });
        await user.selectOptions(screen.getByLabelText("Baseline"), snapshot.snapshot_id);
        resolveOldStatus(response(partialEvidenceStatus(olderSnapshot.snapshot_id)));

        await waitFor(() => {
            expect(screen.queryByText("Baseline evidence is partial.")).toBeNull();
        });
    });

    it("renders migrated snapshot observations as unknown", async () => {
        const unknownSnapshots = comparisonSnapshots.map((item) => ({
            ...item,
            observed_state_known: false,
            branch: null,
            git_sha: null,
            dirty: null,
            staged: null,
            untracked: null,
        }));
        const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
            const url = String(input);
            if (url.includes("comparison-snapshots")) {
                return response({ repository, snapshots: unknownSnapshots });
            }
            if (url.includes("/evidence-status")) {
                const snapshotId = url.includes(olderSnapshot.snapshot_id)
                    ? olderSnapshot.snapshot_id
                    : snapshot.snapshot_id;
                return response({
                    ...completeEvidenceStatus(snapshotId),
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
                });
            }
            if (url.includes("/comparisons/summary")) return response(summary);
            if (url.includes("/comparisons/items")) return response(page("files", [fileItem]));
            return response({ detail: "Unexpected request" }, 500);
        });
        vi.stubGlobal("fetch", fetchMock);

        render(
            <CompareView
                repositoryId={repository.repository_id}
                targetSnapshotId={snapshot.snapshot_id}
            />,
        );

        const facts = await screen.findAllByText("observation unknown");
        expect(facts.filter((item) => item.closest(".snapshot-facts"))).toHaveLength(2);
        expect(await screen.findByText("Baseline historical state is unknown.")).toBeTruthy();
        expect(screen.getByText("Target historical state is unknown.")).toBeTruthy();
        expect(screen.queryByText(/detached/)).toBeNull();
        expect(screen.queryByText(/clean worktree/)).toBeNull();
    });
});

function comparisonFetch() {
    return vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("comparison-snapshots")) {
            return response({ repository, snapshots: comparisonSnapshots });
        }
        if (url.includes("/evidence-status")) {
            return response(
                url.includes(snapshot.snapshot_id)
                    ? partialEvidenceStatus(snapshot.snapshot_id)
                    : completeEvidenceStatus(olderSnapshot.snapshot_id),
            );
        }
        if (url.includes("/comparisons/summary")) return response(summary);
        if (url.includes("section=symbols")) return response(page("symbols", [symbolItem]));
        if (url.includes("section=metrics")) return response(page("metrics", []));
        if (url.includes("/comparisons/items")) return response(page("files", [fileItem]));
        return response({ detail: "Unexpected request" }, 500);
    });
}

function page(section: ComparisonSection, items: ComparisonItem[]): ComparisonPage {
    return {
        comparison_id: summary.identity.comparison_id,
        section,
        section_status: "partial",
        reason_codes: ["target-parse-gaps"],
        items,
        total: items.length,
        page: 1,
        page_size: 50,
        truncated: false,
    };
}
