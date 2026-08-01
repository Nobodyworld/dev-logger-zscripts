import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HandoffView } from "../components/HandoffView";
import type {
    ComparisonItem,
    ComparisonSnapshot,
    ComparisonSummary,
    HandoffPreview,
    HandoffSelectionRequest,
    SavedHandoff,
} from "../types";
import {
    completeEvidenceStatus,
    finding,
    findingSummary,
    olderSnapshot,
    partialEvidenceStatus,
    repository,
    response,
    snapshot,
} from "./fixtures";

const snapshots: ComparisonSnapshot[] = [
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
        lifecycle_reconciled: true,
        reconciliation_skip_reason: null,
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
        target_parse_gap_count: 0,
        baseline_lifecycle_reconciled: true,
        target_lifecycle_reconciled: true,
        baseline_reconciliation_skip_reason: null,
        target_reconciliation_skip_reason: null,
        sections: ["files", "symbols", "relationships", "cycles", "metrics", "findings"].map(
            (section) => ({
                section: section as
                    "files" | "symbols" | "relationships" | "cycles" | "metrics" | "findings",
                status: "supported" as const,
                reason_codes: [],
            }),
        ),
    },
    counts: { files_changed: 1 },
    equal_snapshots: false,
};

const delta: ComparisonItem = {
    delta_id: "delta-file-0123456789abcdef",
    change_type: "changed",
    logical_key: "pkg/metrics.py",
    label: "pkg/metrics.py",
    relative_path: "pkg/metrics.py",
};

const preview: HandoffPreview = {
    handoff_format_version: "2",
    markdown: "# Repository Handoff\n\n## Task Objective\n\nReview this change.\n",
    normalized_json: '{"handoff_format_version":"2"}\n',
    json_payload: {
        handoff_format_version: "2",
        analysis_gaps: [],
        omitted_counts: {},
        truncated: false,
    },
    rendered_digest: "digest-0123456789abcdef",
    truncated: false,
    omitted_counts: {},
    warnings: [],
    markdown_character_count: 62,
    json_byte_count: 120,
};

describe("HandoffView", () => {
    afterEach(() => {
        vi.restoreAllMocks();
        Object.defineProperty(navigator, "clipboard", {
            configurable: true,
            value: undefined,
        });
    });

    it("selects bounded evidence, explicitly opts into a note, previews, copies, saves, and downloads", async () => {
        const user = userEvent.setup();
        const clipboard = vi.fn().mockResolvedValue(undefined);
        Object.defineProperty(navigator, "clipboard", {
            configurable: true,
            value: { writeText: clipboard },
        });
        const objectUrl = vi.fn().mockReturnValue("blob:handoff");
        Object.defineProperty(URL, "createObjectURL", {
            configurable: true,
            value: objectUrl,
        });
        Object.defineProperty(URL, "revokeObjectURL", {
            configurable: true,
            value: vi.fn(),
        });
        vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
        const fetchMock = handoffFetch();
        vi.stubGlobal("fetch", fetchMock);
        render(
            <HandoffView
                repositoryId={repository.repository_id}
                targetSnapshotId={snapshot.snapshot_id}
            />,
        );

        expect(await screen.findByRole("heading", { name: "Handoff" })).toBeTruthy();
        await user.click(await screen.findByRole("checkbox", { name: /pkg\/metrics.py/ }));
        await user.click(screen.getByRole("tab", { name: "findings" }));
        const findingSelection = await screen.findByRole("checkbox", {
            name: /<img src=x onerror=alert\(1\)>/,
        });
        await user.click(findingSelection);
        await user.click(
            screen.getByRole("checkbox", { name: "Explicitly include this review note" }),
        );
        await user.click(
            screen.getByRole("checkbox", {
                name: "Include current lifecycle and review status",
            }),
        );
        await user.type(screen.getByLabelText(/Task objective/), "Review this change.");
        await user.click(screen.getByRole("button", { name: "Preview handoff" }));

        expect(await screen.findByText("Deterministic preview updated.")).toBeTruthy();
        expect(screen.getByText("# Repository Handoff", { exact: false })).toBeTruthy();
        const previewCall = fetchMock.mock.calls.find(([input]) =>
            String(input).endsWith("/api/handoffs/preview"),
        );
        const request = JSON.parse(String(previewCall?.[1]?.body)) as HandoffSelectionRequest;
        expect(request.selected_delta_ids).toContain(delta.delta_id);
        expect(request.selected_finding_ids).toContain(finding.finding_id);
        expect(request.explicit_review_note_finding_ids).toEqual([finding.finding_id]);
        expect(request.include_current_review_status).toBe(true);

        await user.click(screen.getByRole("button", { name: "Copy Markdown" }));
        expect(clipboard).toHaveBeenCalledWith(preview.markdown);
        expect(await screen.findByText("Markdown copied to the clipboard.")).toBeTruthy();
        await user.click(screen.getByRole("button", { name: "Download Markdown" }));
        await user.click(screen.getByRole("button", { name: "Download JSON" }));
        expect(objectUrl).toHaveBeenCalledTimes(2);

        await user.click(screen.getByRole("button", { name: "Save locally" }));
        expect(await screen.findByText("Handoff saved locally.")).toBeTruthy();
        expect(screen.getByRole("button", { name: /Review this change/ })).toBeTruthy();
        expect(
            screen.getByRole("heading", { name: "Markdown preview" }).parentElement?.textContent,
        ).toContain(`${preview.json_byte_count} bytes`);

        const objectiveInput = screen.getByLabelText(/Task objective/);
        await user.clear(objectiveInput);
        await user.type(objectiveInput, "temporary edit");
        await user.click(screen.getByRole("button", { name: /Review this change/ }));
        await waitFor(() => {
            expect((objectiveInput as HTMLTextAreaElement).value).toBe("Review this change.");
            expect(screen.getByText("# Repository Handoff", { exact: false })).toBeTruthy();
        });
    }, 10_000);

    it("reports clipboard failure without losing the preview", async () => {
        const user = userEvent.setup();
        Object.defineProperty(navigator, "clipboard", {
            configurable: true,
            value: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
        });
        vi.stubGlobal("fetch", handoffFetch());
        render(
            <HandoffView
                repositoryId={repository.repository_id}
                targetSnapshotId={snapshot.snapshot_id}
            />,
        );

        await screen.findByRole("heading", { name: "Handoff" });
        await user.click(screen.getByRole("button", { name: "Preview handoff" }));
        await user.click(await screen.findByRole("button", { name: "Copy Markdown" }));
        expect((await screen.findByRole("alert")).textContent).toContain(
            "Clipboard permission was denied",
        );
        expect(screen.getByText("# Repository Handoff", { exact: false })).toBeTruthy();
    });

    it("announces a bounded preview error, clears stale output, preserves saved records, and retries", async () => {
        const safeMessage = "The Handoff JSON budget is too small for required metadata.";
        const savedRecord = savedHandoff(defaultSelection());
        let previewCount = 0;
        const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
        vi.stubGlobal(
            "fetch",
            handoffFetch((input) => {
                const url = String(input);
                if (url.startsWith("/api/handoffs?")) {
                    return Promise.resolve(response({ items: [savedRecord] }));
                }
                if (!url.endsWith("/api/handoffs/preview")) return null;
                previewCount += 1;
                if (previewCount === 2) {
                    return Promise.resolve(response({ detail: safeMessage }, 400));
                }
                return Promise.resolve(
                    response({
                        ...preview,
                        markdown:
                            previewCount === 1
                                ? "# Repository Handoff\n\nStale preview"
                                : "# Repository Handoff\n\nRetry succeeded",
                    }),
                );
            }),
        );
        const user = userEvent.setup();
        render(
            <HandoffView
                repositoryId={repository.repository_id}
                targetSnapshotId={snapshot.snapshot_id}
            />,
        );

        const previewButton = await screen.findByRole("button", { name: "Preview handoff" });
        expect(screen.getByRole("button", { name: /Review this change/ })).toBeTruthy();
        await user.click(previewButton);
        expect(await screen.findByText("Stale preview", { exact: false })).toBeTruthy();

        previewButton.focus();
        await user.keyboard("{Enter}");
        const alert = await screen.findByRole("alert");
        expect(alert.textContent).toBe(safeMessage);
        expect(screen.queryByText("Stale preview", { exact: false })).toBeNull();
        expect(screen.queryByRole("button", { name: "Copy Markdown" })).toBeNull();
        expect(screen.getByRole("button", { name: /Review this change/ })).toBeTruthy();

        await user.type(screen.getByLabelText(/Task objective/), " retry");
        await user.click(previewButton);
        expect(await screen.findByText("Retry succeeded", { exact: false })).toBeTruthy();
        expect(screen.queryByRole("alert")).toBeNull();
        expect(consoleError).not.toHaveBeenCalled();
    });

    it("ignores a stale preview after a newer objective succeeds", async () => {
        let resolveFirst!: (value: Response) => void;
        const firstPreview = new Promise<Response>((resolve) => {
            resolveFirst = resolve;
        });
        let previewCount = 0;
        const fetchMock = handoffFetch((input) => {
            if (!String(input).endsWith("/api/handoffs/preview")) return null;
            previewCount += 1;
            return previewCount === 1
                ? firstPreview
                : Promise.resolve(
                      response({
                          ...preview,
                          markdown: "# Repository Handoff\n\nNew objective",
                          rendered_digest: "new-digest",
                      }),
                  );
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(
            <HandoffView
                repositoryId={repository.repository_id}
                targetSnapshotId={snapshot.snapshot_id}
            />,
        );

        await screen.findByRole("heading", { name: "Handoff" });
        await user.click(screen.getByRole("button", { name: "Preview handoff" }));
        await user.type(screen.getByLabelText(/Task objective/), "new");
        await user.click(screen.getByRole("button", { name: "Preview handoff" }));
        expect(await screen.findByText("New objective", { exact: false })).toBeTruthy();
        resolveFirst(response(preview));

        await waitFor(() => {
            expect(screen.getByText("New objective", { exact: false })).toBeTruthy();
            expect(screen.queryByText("Review this change.", { exact: false })).toBeNull();
        });
    });

    it("clears comparison selections and preview when the snapshot pair changes", async () => {
        const fetchMock = handoffFetch();
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(
            <HandoffView
                repositoryId={repository.repository_id}
                targetSnapshotId={snapshot.snapshot_id}
            />,
        );

        const deltaSelection = await screen.findByRole("checkbox", { name: /pkg\/metrics.py/ });
        await user.click(deltaSelection);
        await user.click(screen.getByRole("button", { name: "Preview handoff" }));
        expect(await screen.findByText("# Repository Handoff", { exact: false })).toBeTruthy();

        await user.selectOptions(screen.getByLabelText("Baseline"), snapshot.snapshot_id);

        expect(
            await screen.findByText(
                "Snapshot pair changed; comparison selections and preview were reset.",
            ),
        ).toBeTruthy();
        expect(screen.queryByText("# Repository Handoff", { exact: false })).toBeNull();
        expect(
            (await screen.findByRole("checkbox", {
                name: /pkg\/metrics.py/,
            })) as HTMLInputElement,
        ).toHaveProperty("checked", false);

        await user.click(screen.getByRole("button", { name: "Preview handoff" }));
        await screen.findByText("Deterministic preview updated.");
        const previewCalls = fetchMock.mock.calls.filter(([input]) =>
            String(input).endsWith("/api/handoffs/preview"),
        );
        const latestRequest = JSON.parse(
            String(previewCalls.at(-1)?.[1]?.body),
        ) as HandoffSelectionRequest;
        expect(latestRequest.selected_delta_ids).toEqual([]);
        expect(latestRequest.selected_cycle_ids).toEqual([]);
    });

    it("rehydrates a saved B to C handoff without losing its immutable output", async () => {
        const snapshotC: ComparisonSnapshot = {
            ...snapshots[0],
            snapshot_id: "snapshot-c-0123456789abcdef",
            completed_at: "2026-07-29T12:00:00Z",
            branch: "branch-c",
            git_sha: "cccccccccccccccc",
        };
        const allSnapshots = [snapshotC, snapshots[0], snapshots[1]];
        const savedSelection: HandoffSelectionRequest = {
            ...defaultSelection(),
            target_snapshot_id: snapshotC.snapshot_id,
            baseline_snapshot_id: snapshot.snapshot_id,
            comparison_id: "comparison-b-c",
            selected_delta_ids: [delta.delta_id],
            task_objective: "Saved B to C",
        };
        const immutablePreview: HandoffPreview = {
            ...preview,
            markdown: "# Exact saved B to C\n",
            normalized_json: '{"exact":"saved-b-c"}\n',
            rendered_digest: "saved-b-c-digest",
            markdown_character_count: 21,
            json_byte_count: 23,
        };
        const savedBC = savedHandoff(savedSelection, {
            handoff_id: "handoff-b-c",
            preview: immutablePreview,
        });
        const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
            const url = String(input);
            if (url.includes("comparison-snapshots")) {
                return response({ repository, snapshots: allSnapshots });
            }
            if (url.includes("/evidence-status")) {
                return response(
                    url.includes(snapshotC.snapshot_id)
                        ? partialEvidenceStatus(snapshotC.snapshot_id)
                        : completeEvidenceStatus(
                              url.includes(olderSnapshot.snapshot_id)
                                  ? olderSnapshot.snapshot_id
                                  : snapshot.snapshot_id,
                          ),
                );
            }
            if (url.startsWith("/api/handoffs?")) return response({ items: [savedBC] });
            if (url === "/api/handoffs/handoff-b-c") return response(savedBC);
            if (url.includes("/api/comparisons/summary")) {
                const params = new URL(url, "http://local").searchParams;
                const baseline = params.get("baseline_snapshot_id");
                const target = params.get("target_snapshot_id");
                return response(
                    pairSummary(
                        baseline ?? "",
                        target ?? "",
                        target === snapshotC.snapshot_id ? "comparison-b-c" : "comparison-a-b",
                    ),
                );
            }
            if (url.includes("/api/comparisons/items")) {
                const params = new URL(url, "http://local").searchParams;
                return response({
                    section: "files",
                    section_status: "supported",
                    reason_codes: [],
                    items: [delta],
                    total: 1,
                    page: 1,
                    page_size: 50,
                    truncated: false,
                    comparison_id:
                        params.get("target_snapshot_id") === snapshotC.snapshot_id
                            ? "comparison-b-c"
                            : "comparison-a-b",
                });
            }
            if (url.includes("/findings?")) {
                return response({
                    supported: true,
                    items: [finding],
                    total: 1,
                    page: 1,
                    page_size: 50,
                    summary: findingSummary,
                });
            }
            if (url.endsWith("/api/handoffs/preview")) {
                return response({
                    ...preview,
                    markdown: "# Newly rendered B to C\n",
                    rendered_digest: "new-b-c-digest",
                });
            }
            return response({ detail: `Unexpected request: ${url}` }, 500);
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(
            <HandoffView
                repositoryId={repository.repository_id}
                targetSnapshotId={snapshot.snapshot_id}
            />,
        );

        await screen.findByRole("heading", { name: "Handoff" });
        expect(screen.queryByText("Target evidence is partial.")).toBeNull();
        await user.click(await screen.findByRole("button", { name: /Saved B to C/ }));

        await waitFor(() => {
            expect((screen.getByLabelText("Baseline") as HTMLSelectElement).value).toBe(
                snapshot.snapshot_id,
            );
            expect((screen.getByLabelText("Target") as HTMLSelectElement).value).toBe(
                snapshotC.snapshot_id,
            );
        });
        expect(await screen.findByText("Target evidence is partial.")).toBeTruthy();
        expect(await screen.findByText("# Exact saved B to C", { exact: false })).toBeTruthy();
        expect(screen.getByText("Immutable saved output")).toBeTruthy();
        expect(screen.getByText("Digest saved-b-c-digest")).toBeTruthy();
        expect(screen.getByText(/21 chars · 23 bytes/)).toBeTruthy();
        expect(
            (await screen.findByRole("checkbox", {
                name: /pkg\/metrics.py/,
            })) as HTMLInputElement,
        ).toHaveProperty("checked", true);

        await waitFor(() => {
            const pairCalls = fetchMock.mock.calls.filter(([input]) =>
                String(input).includes("/api/comparisons/summary"),
            );
            expect(pairCalls.length).toBeGreaterThanOrEqual(2);
            expect(screen.getByText("# Exact saved B to C", { exact: false })).toBeTruthy();
        });

        await user.click(screen.getByRole("button", { name: "Preview handoff" }));
        expect(await screen.findByText("# Newly rendered B to C", { exact: false })).toBeTruthy();
        expect(screen.queryByText("# Exact saved B to C", { exact: false })).toBeNull();
    });

    it("keeps schema-3 generic status neutral while reopening a version-mismatch handoff", async () => {
        const schemaThreeSnapshots = snapshots.map((item) =>
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
        const saved = savedHandoff(defaultSelection());
        const fetchMock = handoffFetch((input) => {
            const url = String(input);
            if (url.includes("comparison-snapshots")) {
                return Promise.resolve(response({ repository, snapshots: schemaThreeSnapshots }));
            }
            if (url.includes("/evidence-status")) {
                const snapshotId = url.includes(olderSnapshot.snapshot_id)
                    ? olderSnapshot.snapshot_id
                    : snapshot.snapshot_id;
                return Promise.resolve(response(completeEvidenceStatus(snapshotId, "generic")));
            }
            if (url.startsWith("/api/handoffs?")) {
                return Promise.resolve(response({ items: [saved] }));
            }
            if (url === `/api/handoffs/${saved.handoff_id}`) {
                return Promise.resolve(response(saved));
            }
            if (url.includes("/api/comparisons/summary")) {
                return Promise.resolve(response(mismatchSummary));
            }
            return null;
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();

        render(
            <HandoffView
                repositoryId={repository.repository_id}
                targetSnapshotId={snapshot.snapshot_id}
            />,
        );

        expect(
            await screen.findByText(
                /Files comparison is partial because baseline and target evidence versions differ/,
            ),
        ).toBeTruthy();
        expect(screen.queryByText("Baseline evidence is unsupported.")).toBeNull();
        await user.click(await screen.findByRole("button", { name: /Review this change/ }));
        expect(await screen.findByText("# Repository Handoff", { exact: false })).toBeTruthy();
        expect(screen.queryByText("Baseline evidence is unsupported.")).toBeNull();
        const statusCalls = fetchMock.mock.calls.filter(([input]) =>
            String(input).includes("/evidence-status"),
        );
        expect(statusCalls.length).toBeGreaterThanOrEqual(2);
        expect(statusCalls.every(([input]) => String(input).includes("surface=generic"))).toBe(
            true,
        );
    });

    it("ignores a stale saved-handoff reopen response", async () => {
        let resolveFirst!: (value: Response) => void;
        const firstResponse = new Promise<Response>((resolve) => {
            resolveFirst = resolve;
        });
        const first = savedHandoff(
            { ...defaultSelection(), task_objective: "First saved handoff" },
            { handoff_id: "handoff-first" },
        );
        const secondPreview = {
            ...preview,
            markdown: "# Newer saved handoff\n",
            normalized_json: '{"saved":"newer"}\n',
            rendered_digest: "newer-saved-digest",
        };
        const second = savedHandoff(
            { ...defaultSelection(), task_objective: "Second saved handoff" },
            { handoff_id: "handoff-second", preview: secondPreview },
        );
        const fetchMock = handoffFetch((input) => {
            const url = String(input);
            if (url.startsWith("/api/handoffs?")) {
                return Promise.resolve(response({ items: [first, second] }));
            }
            if (url === "/api/handoffs/handoff-first") return firstResponse;
            if (url === "/api/handoffs/handoff-second") {
                return Promise.resolve(response(second));
            }
            return null;
        });
        vi.stubGlobal("fetch", fetchMock);
        const user = userEvent.setup();
        render(
            <HandoffView
                repositoryId={repository.repository_id}
                targetSnapshotId={snapshot.snapshot_id}
            />,
        );

        await user.click(await screen.findByRole("button", { name: /First saved handoff/ }));
        await user.click(screen.getByRole("button", { name: /Second saved handoff/ }));
        expect(await screen.findByText("# Newer saved handoff", { exact: false })).toBeTruthy();
        resolveFirst(response(first));

        await waitFor(() => {
            expect(screen.getByText("# Newer saved handoff", { exact: false })).toBeTruthy();
            expect(screen.queryByText("# Repository Handoff", { exact: false })).toBeNull();
        });
    });
});

function handoffFetch(
    override?: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response> | null,
) {
    return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const overridden = override?.(input, init);
        if (overridden) return overridden;
        const url = String(input);
        if (url.includes("comparison-snapshots")) {
            return response({ repository, snapshots });
        }
        if (url.includes("/evidence-status")) {
            return response(
                completeEvidenceStatus(
                    url.includes(olderSnapshot.snapshot_id)
                        ? olderSnapshot.snapshot_id
                        : snapshot.snapshot_id,
                ),
            );
        }
        if (url.startsWith("/api/handoffs?")) return response({ items: [] });
        if (url.includes("/api/comparisons/summary")) return response(summary);
        if (url.includes("/api/comparisons/items")) {
            return response({
                comparison_id: summary.identity.comparison_id,
                section: "files",
                section_status: "supported",
                reason_codes: [],
                items: [delta],
                total: 1,
                page: 1,
                page_size: 50,
                truncated: false,
            });
        }
        if (url.includes("/findings?")) {
            return response({
                supported: true,
                items: [finding],
                total: 1,
                page: 1,
                page_size: 50,
                summary: findingSummary,
            });
        }
        if (url.endsWith("/api/handoffs/preview")) return response(preview);
        if (url.endsWith("/api/handoffs") && init?.method === "POST") {
            const selection = JSON.parse(String(init.body)) as HandoffSelectionRequest;
            return response(savedHandoff(selection), 201);
        }
        if (url.includes("/api/handoffs/handoff-local")) {
            return response(savedHandoff(defaultSelection()));
        }
        return response({ detail: "Unexpected request" }, 500);
    });
}

function savedHandoff(
    selection: HandoffSelectionRequest,
    overrides: { handoff_id?: string; preview?: HandoffPreview } = {},
): SavedHandoff {
    const rendered = overrides.preview ?? preview;
    return {
        handoff_id: overrides.handoff_id ?? "handoff-local-0123456789",
        repository_id: repository.repository_id,
        target_snapshot_id: selection.target_snapshot_id,
        baseline_snapshot_id: selection.baseline_snapshot_id,
        comparison_id: selection.comparison_id,
        selection,
        task_objective: selection.task_objective,
        format_version: "2",
        rendered_digest: rendered.rendered_digest,
        markdown_character_count: rendered.markdown_character_count,
        json_byte_count: rendered.json_byte_count,
        created_at: "2026-07-28T12:00:00Z",
        updated_at: "2026-07-28T12:00:00Z",
        local_only: true,
        markdown: rendered.markdown,
        normalized_json: rendered.normalized_json,
        json_payload: rendered.json_payload,
    };
}

function pairSummary(
    baselineSnapshotId: string,
    targetSnapshotId: string,
    comparisonId: string,
): ComparisonSummary {
    return {
        ...summary,
        identity: {
            ...summary.identity,
            comparison_id: comparisonId,
            baseline_snapshot_id: baselineSnapshotId,
            target_snapshot_id: targetSnapshotId,
        },
    };
}

function defaultSelection(): HandoffSelectionRequest {
    return {
        target_snapshot_id: snapshot.snapshot_id,
        baseline_snapshot_id: olderSnapshot.snapshot_id,
        comparison_id: summary.identity.comparison_id,
        enabled_sections: ["comparison", "files", "findings", "task-objective"],
        selected_delta_ids: [delta.delta_id],
        selected_finding_ids: [],
        selected_cycle_ids: [],
        include_current_review_status: false,
        explicit_review_note_finding_ids: [],
        task_objective: "Review this change.",
    };
}
