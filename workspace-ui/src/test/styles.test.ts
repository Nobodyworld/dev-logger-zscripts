import { describe, expect, it } from "vitest";

import styles from "../styles.css?raw";

function cssVariable(name: string): string {
    const match = styles.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6});`));
    if (!match) {
        throw new Error(`Missing CSS variable --${name}`);
    }
    return match[1];
}

function channel(value: number): number {
    const normalized = value / 255;
    if (normalized <= 0.04045) {
        return normalized / 12.92;
    }
    return ((normalized + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
    const red = Number.parseInt(hex.slice(1, 3), 16);
    const green = Number.parseInt(hex.slice(3, 5), 16);
    const blue = Number.parseInt(hex.slice(5, 7), 16);
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue);
}

function contrast(left: string, right: string): number {
    const first = luminance(left);
    const second = luminance(right);
    const lighter = Math.max(first, second);
    const darker = Math.min(first, second);
    return (lighter + 0.05) / (darker + 0.05);
}

describe("workspace control styling", () => {
    it("keeps enabled primary button text above the normal-text contrast target", () => {
        const normalContrast = contrast("#ffffff", cssVariable("button-primary"));
        const hoverContrast = contrast("#ffffff", cssVariable("button-primary-hover"));

        expect(normalContrast).toBeGreaterThanOrEqual(4.5);
        expect(hoverContrast).toBeGreaterThanOrEqual(4.5);
        expect(styles).toContain("background: var(--button-primary);");
        expect(styles).toContain("background: var(--button-primary-hover);");
    });

    it("keeps a solid high-contrast focus outline with forced-colors support", () => {
        const focusContrast = contrast("#ffffff", cssVariable("focus"));

        expect(focusContrast).toBeGreaterThanOrEqual(3);
        expect(styles).toContain("outline: 3px solid var(--focus);");
        expect(styles).toContain("outline-offset: 2px;");
        expect(styles).toContain("@media (forced-colors: active)");
        expect(styles).toContain("outline-color: Highlight;");
    });
});
