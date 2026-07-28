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
import { finding, findingSummary, olderSnapshot, repository, response, snapshot } from "./fixtures";

const snapshots: ComparisonSnapshot[] = [
    {
        ...snapshot,
        analyzer_version: "3",
        schema_version: "3",
        rule_set_version: "4",
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
        schema_version: "3",
        rule_set_version: "4",
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
        comparison_id: "comparison-0123456789abcdef",
        repository_id: repository.repository_id,
        baseline_snapshot_id: olderSnapshot.snapshot_id,
        target_snapshot_id: snapshot.snapshot_id,
        comparison_format_version: "1",
    },
    compatibility: {
        same_repository: true,
        baseline_analyzer_version: "3",
        target_analyzer_version: "3",
        baseline_schema_version: "3",
        target_schema_version: "3",
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
    handoff_format_version: "1",
    markdown: "# Repository Handoff\n\n## Task Objective\n\nReview this change.\n",
    json_payload: {
        handoff_format_version: "1",
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
    });

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

function savedHandoff(selection: HandoffSelectionRequest): SavedHandoff {
    return {
        handoff_id: "handoff-local-0123456789",
        repository_id: repository.repository_id,
        target_snapshot_id: snapshot.snapshot_id,
        baseline_snapshot_id: olderSnapshot.snapshot_id,
        comparison_id: summary.identity.comparison_id,
        selection,
        task_objective: selection.task_objective,
        format_version: "1",
        rendered_digest: preview.rendered_digest,
        markdown_character_count: preview.markdown_character_count,
        json_byte_count: preview.json_byte_count,
        created_at: "2026-07-28T12:00:00Z",
        updated_at: "2026-07-28T12:00:00Z",
        local_only: true,
        markdown: preview.markdown,
        json_payload: preview.json_payload,
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
