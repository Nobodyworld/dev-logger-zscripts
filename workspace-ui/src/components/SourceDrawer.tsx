import { CloseIcon } from "../icons";
import type { SourceEvidence, SymbolRecord } from "../types";

interface SourceDrawerProps {
    symbol: SymbolRecord;
    source: SourceEvidence | null;
    loading: boolean;
    error: string | null;
    onClose: () => void;
}

export function SourceDrawer({ symbol, source, loading, error, onClose }: SourceDrawerProps) {
    return (
        <aside className="source-drawer" aria-labelledby="source-evidence-title">
            <header className="source-drawer__header">
                <h3 id="source-evidence-title">Source evidence</h3>
                <button className="icon-button" type="button" onClick={onClose}>
                    <span className="sr-only">Close source evidence</span>
                    <CloseIcon />
                </button>
            </header>
            <dl className="source-meta">
                <div>
                    <dt>Path</dt>
                    <dd className="mono">{symbol.relative_path}</dd>
                </div>
                <div>
                    <dt>Line range</dt>
                    <dd className="mono">
                        {symbol.start_line}–{symbol.end_line}
                    </dd>
                </div>
            </dl>
            {loading ? <p role="status">Loading bounded source evidence…</p> : null}
            {error ? <p className="error-message">{error}</p> : null}
            {source ? (
                <pre className="source-code" aria-label="Read-only source excerpt">
                    <code>
                        {source.lines.map((line) => (
                            <span className="source-line" key={line.number}>
                                <span className="source-line__number">{line.number}</span>
                                <span>{line.text || " "}</span>
                            </span>
                        ))}
                    </code>
                </pre>
            ) : null}
            <dl className="symbol-details">
                <div>
                    <dt>Annotations</dt>
                    <dd>{symbol.annotations.length > 0 ? symbol.annotations.join(", ") : "—"}</dd>
                </div>
                <div>
                    <dt>Decorators</dt>
                    <dd>{symbol.decorators.length > 0 ? symbol.decorators.join(", ") : "—"}</dd>
                </div>
                <div>
                    <dt>Docstring</dt>
                    <dd>{symbol.docstring_present ? "Present" : "Not present"}</dd>
                </div>
                <div>
                    <dt>Async</dt>
                    <dd>{symbol.async_flag ? "Yes" : "No"}</dd>
                </div>
            </dl>
        </aside>
    );
}
