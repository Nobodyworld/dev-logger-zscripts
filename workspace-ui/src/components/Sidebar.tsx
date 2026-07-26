import { CloseIcon, MenuIcon, OverviewIcon, RelationshipsIcon, SymbolsIcon } from "../icons";
import type { ViewName } from "../types";

interface SidebarProps {
    activeView: ViewName;
    open: boolean;
    onOpen: () => void;
    onClose: () => void;
    onSelect: (view: ViewName) => void;
}

export function Sidebar({ activeView, open, onOpen, onClose, onSelect }: SidebarProps) {
    const choose = (view: ViewName) => {
        onSelect(view);
        onClose();
    };

    return (
        <>
            <button
                className="mobile-menu"
                type="button"
                aria-label="Open navigation"
                aria-expanded={open}
                onClick={() => (open ? onClose() : onOpen())}
            >
                <MenuIcon />
            </button>
            <aside
                className={`sidebar ${open ? "sidebar--open" : ""}`}
                aria-label="Workspace navigation"
            >
                <div className="sidebar__brand-row">
                    <span className="sidebar__brand">Zscripts</span>
                    <button className="icon-button sidebar__close" type="button" onClick={onClose}>
                        <span className="sr-only">Close navigation</span>
                        <CloseIcon />
                    </button>
                </div>
                <nav>
                    <button
                        className={`nav-item ${activeView === "overview" ? "nav-item--active" : ""}`}
                        type="button"
                        aria-current={activeView === "overview" ? "page" : undefined}
                        onClick={() => choose("overview")}
                    >
                        <OverviewIcon />
                        Overview
                    </button>
                    <button
                        className={`nav-item ${activeView === "symbols" ? "nav-item--active" : ""}`}
                        type="button"
                        aria-current={activeView === "symbols" ? "page" : undefined}
                        onClick={() => choose("symbols")}
                    >
                        <SymbolsIcon />
                        Symbols
                    </button>
                    <button
                        className={`nav-item ${
                            activeView === "relationships" ? "nav-item--active" : ""
                        }`}
                        type="button"
                        aria-current={activeView === "relationships" ? "page" : undefined}
                        onClick={() => choose("relationships")}
                    >
                        <RelationshipsIcon />
                        Relationships
                    </button>
                </nav>
                <p className="sidebar__beta">PUBLIC BETA — ACTIVE DEVELOPMENT</p>
            </aside>
            {open ? (
                <button className="sidebar-scrim" aria-label="Close navigation" onClick={onClose} />
            ) : null}
        </>
    );
}
