import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.75,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    viewBox: "0 0 24 24",
    "aria-hidden": true,
};

export function OverviewIcon(props: IconProps) {
    return (
        <svg {...common} {...props}>
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
        </svg>
    );
}

export function SymbolsIcon(props: IconProps) {
    return (
        <svg {...common} {...props}>
            <path d="M8 4 4 8l4 4" />
            <path d="m16 12 4-4-4-4" />
            <path d="m14 3-4 10" />
            <path d="M5 18h14" />
        </svg>
    );
}

export function RelationshipsIcon(props: IconProps) {
    return (
        <svg {...common} {...props}>
            <circle cx="6" cy="6" r="2.5" />
            <circle cx="18" cy="8" r="2.5" />
            <circle cx="10" cy="18" r="2.5" />
            <path d="m8.3 6.5 7.2 1M7.2 8.2l1.7 7.3m7.3-5.3-4.7 5.7" />
        </svg>
    );
}

export function FindingsIcon(props: IconProps) {
    return (
        <svg {...common} {...props}>
            <path d="M5 4h14v16H5z" />
            <path d="M8 8h8M8 12h5M8 16h7" />
            <path d="m15 12 1.5 1.5L19 10.8" />
        </svg>
    );
}

export function CompareIcon(props: IconProps) {
    return (
        <svg {...common} {...props}>
            <path d="M4 7h13M14 4l3 3-3 3" />
            <path d="M20 17H7M10 14l-3 3 3 3" />
        </svg>
    );
}

export function HandoffIcon(props: IconProps) {
    return (
        <svg {...common} {...props}>
            <path d="M5 4h10l4 4v12H5z" />
            <path d="M15 4v4h4M8 13h8M8 16h6" />
            <path d="m10 10 2-2 2 2" />
        </svg>
    );
}

export function MenuIcon(props: IconProps) {
    return (
        <svg {...common} {...props}>
            <path d="M4 7h16M4 12h16M4 17h16" />
        </svg>
    );
}

export function CloseIcon(props: IconProps) {
    return (
        <svg {...common} {...props}>
            <path d="m6 6 12 12M18 6 6 18" />
        </svg>
    );
}

export function SearchIcon(props: IconProps) {
    return (
        <svg {...common} {...props}>
            <circle cx="11" cy="11" r="6" />
            <path d="m16 16 4 4" />
        </svg>
    );
}

export function ScanIcon(props: IconProps) {
    return (
        <svg {...common} {...props}>
            <path d="M20 7v5h-5" />
            <path d="M4 17v-5h5" />
            <path d="M6.1 8a7 7 0 0 1 11.8-2L20 8" />
            <path d="m4 16 2.1 2A7 7 0 0 0 18 16" />
        </svg>
    );
}

export function ChevronIcon(props: IconProps) {
    return (
        <svg {...common} {...props}>
            <path d="m8 10 4 4 4-4" />
        </svg>
    );
}

export function SortIcon({ direction, ...props }: IconProps & { direction?: "asc" | "desc" }) {
    return (
        <svg {...common} {...props}>
            {direction === "asc" ? <path d="m8 14 4-4 4 4" /> : null}
            {direction === "desc" ? <path d="m8 10 4 4 4-4" /> : null}
            {!direction ? (
                <>
                    <path d="m8 10 4-4 4 4" />
                    <path d="m8 14 4 4 4-4" />
                </>
            ) : null}
        </svg>
    );
}
