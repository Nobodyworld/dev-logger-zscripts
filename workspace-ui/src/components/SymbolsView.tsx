import { useDeferredValue, useEffect, useRef, useState } from "react";

import { ApiError, getSource, getSymbols } from "../api";
import { SearchIcon, SortIcon } from "../icons";
import type { SourceEvidence, SymbolPage, SymbolRecord } from "../types";
import { SourceDrawer } from "./SourceDrawer";

interface SymbolsViewProps {
    snapshotId: string;
}

type SortField = "qualified_name" | "kind" | "signature" | "module" | "file" | "line";

const initialPage: SymbolPage = {
    items: [],
    total: 0,
    page: 1,
    page_size: 50,
    filters: { kinds: [], modules: [], visibilities: [] },
};

export function SymbolsView({ snapshotId }: SymbolsViewProps) {
    const [search, setSearch] = useState("");
    const deferredSearch = useDeferredValue(search);
    const [kind, setKind] = useState("");
    const [module, setModule] = useState("");
    const [visibility, setVisibility] = useState("");
    const [sort, setSort] = useState<SortField>("qualified_name");
    const [direction, setDirection] = useState<"asc" | "desc">("asc");
    const [page, setPage] = useState(1);
    const [symbols, setSymbols] = useState<SymbolPage>(initialPage);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selected, setSelected] = useState<SymbolRecord | null>(null);
    const [source, setSource] = useState<SourceEvidence | null>(null);
    const [sourceLoading, setSourceLoading] = useState(false);
    const [sourceError, setSourceError] = useState<string | null>(null);
    const sourceRequestGeneration = useRef(0);

    useEffect(
        () => () => {
            sourceRequestGeneration.current += 1;
        },
        [],
    );

    useEffect(() => {
        let active = true;
        getSymbols(snapshotId, {
            search: deferredSearch,
            kind,
            module,
            visibility,
            sort,
            direction,
            page,
            pageSize: 50,
        })
            .then((result) => {
                if (active) setSymbols(result);
            })
            .catch((caught: unknown) => {
                if (active) {
                    setError(
                        caught instanceof ApiError
                            ? caught.message
                            : "Symbols could not be loaded.",
                    );
                }
            })
            .finally(() => {
                if (active) setLoading(false);
            });
        return () => {
            active = false;
        };
    }, [deferredSearch, direction, kind, module, page, snapshotId, sort, visibility]);

    const selectSymbol = (symbol: SymbolRecord) => {
        const requestGeneration = sourceRequestGeneration.current + 1;
        sourceRequestGeneration.current = requestGeneration;
        setSelected(symbol);
        setSource(null);
        setSourceError(null);
        setSourceLoading(true);
        getSource(snapshotId, symbol.relative_path, symbol.start_line, symbol.end_line)
            .then((result) => {
                if (sourceRequestGeneration.current === requestGeneration) {
                    setSource(result);
                }
            })
            .catch((caught: unknown) => {
                if (sourceRequestGeneration.current === requestGeneration) {
                    setSourceError(
                        caught instanceof ApiError
                            ? caught.message
                            : "Source evidence could not be loaded.",
                    );
                }
            })
            .finally(() => {
                if (sourceRequestGeneration.current === requestGeneration) {
                    setSourceLoading(false);
                }
            });
    };

    const changeSort = (field: SortField) => {
        if (field === sort) {
            setDirection((value) => (value === "asc" ? "desc" : "asc"));
        } else {
            setSort(field);
            setDirection("asc");
        }
        setPage(1);
    };

    const first = symbols.total === 0 ? 0 : (symbols.page - 1) * symbols.page_size + 1;
    const last = Math.min(symbols.page * symbols.page_size, symbols.total);
    const pages = Math.max(1, Math.ceil(symbols.total / symbols.page_size));

    return (
        <section className={`view symbols-view ${selected ? "symbols-view--drawer" : ""}`}>
            <div className="symbols-main">
                <h2>Symbols</h2>
                <div className="symbol-toolbar">
                    <label className="search-field">
                        <span className="sr-only">Search symbols</span>
                        <SearchIcon />
                        <input
                            type="search"
                            value={search}
                            placeholder="Search symbols"
                            onChange={(event) => {
                                setSearch(event.target.value);
                                setPage(1);
                            }}
                        />
                    </label>
                    <Filter
                        label="Kind"
                        value={kind}
                        options={symbols.filters.kinds}
                        onChange={(value) => {
                            setKind(value);
                            setPage(1);
                        }}
                    />
                    <Filter
                        label="Module"
                        value={module}
                        options={symbols.filters.modules}
                        onChange={(value) => {
                            setModule(value);
                            setPage(1);
                        }}
                    />
                    <Filter
                        label="Visibility"
                        value={visibility}
                        options={symbols.filters.visibilities}
                        onChange={(value) => {
                            setVisibility(value);
                            setPage(1);
                        }}
                    />
                </div>
                {error ? <p className="error-message">{error}</p> : null}
                <div className="symbol-table-wrap" aria-busy={loading}>
                    <table className="symbol-table">
                        <thead>
                            <tr>
                                <SortHeader
                                    field="qualified_name"
                                    label="Qualified name"
                                    {...{ sort, direction, changeSort }}
                                />
                                <SortHeader
                                    field="kind"
                                    label="Kind"
                                    {...{ sort, direction, changeSort }}
                                />
                                <SortHeader
                                    field="signature"
                                    label="Signature"
                                    {...{ sort, direction, changeSort }}
                                />
                                <SortHeader
                                    field="module"
                                    label="Module"
                                    {...{ sort, direction, changeSort }}
                                />
                                <SortHeader
                                    field="file"
                                    label="File"
                                    {...{ sort, direction, changeSort }}
                                />
                                <SortHeader
                                    field="line"
                                    label="Line"
                                    {...{ sort, direction, changeSort }}
                                />
                                <th scope="col">Decorators</th>
                                <th scope="col">Docstring</th>
                            </tr>
                        </thead>
                        <tbody>
                            {symbols.items.map((symbol) => (
                                <tr
                                    key={symbol.symbol_id}
                                    className={
                                        selected?.symbol_id === symbol.symbol_id
                                            ? "is-selected"
                                            : ""
                                    }
                                >
                                    <td>
                                        <button
                                            className="symbol-link"
                                            type="button"
                                            onClick={() => selectSymbol(symbol)}
                                        >
                                            {symbol.qualified_name}
                                        </button>
                                    </td>
                                    <td>{symbol.kind}</td>
                                    <td className="mono signature-cell">{symbol.signature}</td>
                                    <td>{symbol.module_name}</td>
                                    <td className="mono">{symbol.relative_path}</td>
                                    <td className="mono">{symbol.start_line}</td>
                                    <td>{symbol.decorators.length > 0 ? "Yes" : "—"}</td>
                                    <td>{symbol.docstring_present ? "Yes" : "—"}</td>
                                </tr>
                            ))}
                            {!loading && symbols.items.length === 0 ? (
                                <tr>
                                    <td colSpan={8} className="empty-table">
                                        No symbols match these filters.
                                    </td>
                                </tr>
                            ) : null}
                        </tbody>
                    </table>
                </div>
                <footer className="pagination" aria-label="Symbols pagination">
                    <span>
                        {first.toLocaleString()}–{last.toLocaleString()} of{" "}
                        {symbols.total.toLocaleString()}
                    </span>
                    <div>
                        <button
                            type="button"
                            onClick={() => setPage((value) => value - 1)}
                            disabled={page <= 1}
                        >
                            Previous
                        </button>
                        <span>
                            Page {page} of {pages}
                        </span>
                        <button
                            type="button"
                            onClick={() => setPage((value) => value + 1)}
                            disabled={page >= pages}
                        >
                            Next
                        </button>
                    </div>
                </footer>
            </div>
            {selected ? (
                <SourceDrawer
                    symbol={selected}
                    source={source}
                    loading={sourceLoading}
                    error={sourceError}
                    onClose={() => {
                        sourceRequestGeneration.current += 1;
                        setSelected(null);
                        setSource(null);
                        setSourceError(null);
                        setSourceLoading(false);
                    }}
                />
            ) : null}
        </section>
    );
}

interface FilterProps {
    label: string;
    value: string;
    options: string[];
    onChange: (value: string) => void;
}

function Filter({ label, value, options, onChange }: FilterProps) {
    return (
        <label className="filter-field">
            {label}
            <select value={value} onChange={(event) => onChange(event.target.value)}>
                <option value="">All {label.toLowerCase()}</option>
                {options.map((option) => (
                    <option value={option} key={option}>
                        {option}
                    </option>
                ))}
            </select>
        </label>
    );
}

interface SortHeaderProps {
    field: SortField;
    label: string;
    sort: SortField;
    direction: "asc" | "desc";
    changeSort: (field: SortField) => void;
}

function SortHeader({ field, label, sort, direction, changeSort }: SortHeaderProps) {
    const active = sort === field;
    return (
        <th
            scope="col"
            aria-sort={active ? (direction === "asc" ? "ascending" : "descending") : "none"}
        >
            <button type="button" onClick={() => changeSort(field)}>
                {label}
                <SortIcon direction={active ? direction : undefined} />
            </button>
        </th>
    );
}
