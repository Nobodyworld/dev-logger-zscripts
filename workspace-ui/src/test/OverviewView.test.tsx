import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { OverviewView } from "../components/OverviewView";
import { overview } from "./fixtures";

describe("OverviewView", () => {
    it("renders scan counts, version contracts, and filtered finding links", async () => {
        const onOpenFindings = vi.fn();
        const user = userEvent.setup();
        render(<OverviewView overview={overview} onOpenFindings={onOpenFindings} />);

        expect(screen.getByRole("heading", { name: "Overview" })).toBeTruthy();
        expect(screen.getByText("Files analyzed")).toBeTruthy();
        expect(screen.getByText("Files excluded")).toBeTruthy();
        expect(screen.getByText("Parse gaps")).toBeTruthy();
        expect(screen.getByText("Resolved imports")).toBeTruthy();
        expect(screen.getByText("Inheritance edges")).toBeTruthy();
        expect(screen.getByText("Cycle groups")).toBeTruthy();
        expect(screen.getByText("Largest cycle")).toBeTruthy();
        expect(screen.getByText("Analyzer version")).toBeTruthy();
        expect(screen.getByText("Schema version")).toBeTruthy();
        await user.click(screen.getByRole("button", { name: /Needs action/ }));
        expect(onOpenFindings).toHaveBeenCalledWith("needs-action");
    });
});
