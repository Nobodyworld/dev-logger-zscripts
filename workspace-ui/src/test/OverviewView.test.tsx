import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OverviewView } from "../components/OverviewView";
import { overview } from "./fixtures";

describe("OverviewView", () => {
    it("renders scan counts and version contracts", () => {
        render(<OverviewView overview={overview} />);

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
    });
});
