import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import {
    ApiError,
    getCycles,
    getRelationshipNeighborhood,
    getRelationshipNodes,
    getRelationshipSummary,
    getSource,
} from "../api";
import { SearchIcon } from "../icons";
import type {
    CycleGroup,
    GraphMode,
    GraphNode,
    GraphNodePage,
    Relationship,
    RelationshipNeighborhood,
    RelationshipSummary,
    SourceEvidence,
} from "../types";

interface RelationshipsViewProps {
    snapshotId: string;
}

interface PositionedNode {
    node: GraphNode;
    x: number;
    y: number;
}

const graphLimits = { maxNodes: 40, maxEdges: 80 };

export function RelationshipsView({ snapshotId }: RelationshipsViewProps) {
    const [summary, setSummary] = useState<RelationshipSummary | null>(null);
    const [cycles, setCycles] = useState<CycleGroup[]>([]);
    const [mode, setMode] = useState<GraphMode>("modules");
    const [search, setSearch] = useState("");
    const [requestedNodeIds, setRequestedNodeIds] = useState<string[]>([]);
    const [focusId, setFocusId] = useState("");
    const [depth, setDepth] = useState(1);
    const [relationshipType, setRelationshipType] = useState("");
    const [resolutionStatus, setResolutionStatus] = useState("");
    const [nodeResult, setNodeResult] = useState<{
        key: string;
        value: GraphNodePage;
    } | null>(null);
    const [nodeErrorResult, setNodeErrorResult] = useState<{
        key: string;
        message: string;
    } | null>(null);
    const [graphResult, setGraphResult] = useState<{
        key: string;
        value: RelationshipNeighborhood;
    } | null>(null);
    const [graphErrorResult, setGraphErrorResult] = useState<{
        key: string;
        message: string;
    } | null>(null);
    const [selectedRelationship, setSelectedRelationship] = useState<Relationship | null>(null);
    const [selectedRelationshipKey, setSelectedRelationshipKey] = useState("");
    const [source, setSource] = useState<SourceEvidence | null>(null);
    const [sourceLoading, setSourceLoading] = useState(false);
    const [sourceError, setSourceError] = useState<string | null>(null);
    const [summaryError, setSummaryError] = useState<string | null>(null);
    const summaryGeneration = useRef(0);
    const nodeGeneration = useRef(0);
    const graphGeneration = useRef(0);
    const sourceGeneration = useRef(0);

    const invalidateEvidence = useCallback(() => {
        sourceGeneration.current += 1;
        setSelectedRelationship(null);
        setSelectedRelationshipKey("");
        setSource(null);
        setSourceError(null);
        setSourceLoading(false);
    }, []);

    useEffect(() => {
        const generation = summaryGeneration.current + 1;
        summaryGeneration.current = generation;
        Promise.all([getRelationshipSummary(snapshotId), getCycles(snapshotId)])
            .then(([nextSummary, nextCycles]) => {
                if (summaryGeneration.current !== generation) return;
                setSummary(nextSummary);
                setCycles(nextCycles.items);
                setSummaryError(null);
            })
            .catch((caught: unknown) => {
                if (summaryGeneration.current === generation) {
                    setSummaryError(
                        messageFrom(caught, "Relationship evidence could not be loaded."),
                    );
                }
            });
        return () => {
            summaryGeneration.current += 1;
        };
    }, [snapshotId]);

    const nodeRequestKey = JSON.stringify({
        snapshotId,
        mode,
        search: search.trim(),
        nodeIds: requestedNodeIds,
        page: 1,
        pageSize: 100,
    });

    useEffect(() => {
        if (!summary?.supported) return;
        const generation = nodeGeneration.current + 1;
        nodeGeneration.current = generation;
        getRelationshipNodes(snapshotId, {
            mode,
            search: requestedNodeIds.length > 0 ? "" : search.trim(),
            page: 1,
            pageSize: 100,
            nodeIds: requestedNodeIds,
        })
            .then((result) => {
                if (nodeGeneration.current === generation) {
                    setNodeResult({ key: nodeRequestKey, value: result });
                }
            })
            .catch((caught: unknown) => {
                if (nodeGeneration.current === generation) {
                    setNodeErrorResult({
                        key: nodeRequestKey,
                        message: messageFrom(caught, "Relationship nodes could not be loaded."),
                    });
                }
            });
        return () => {
            nodeGeneration.current += 1;
        };
    }, [mode, nodeRequestKey, requestedNodeIds, search, snapshotId, summary?.supported]);

    const displayedNodePage = nodeResult?.key === nodeRequestKey ? nodeResult.value : null;
    const displayedNodeError =
        nodeErrorResult?.key === nodeRequestKey ? nodeErrorResult.message : null;
    const nodeLoading = Boolean(summary?.supported && !displayedNodePage && !displayedNodeError);
    const modeNodes = useMemo(() => displayedNodePage?.items ?? [], [displayedNodePage]);
    const duplicateNodeNames = useMemo(() => {
        const counts = new Map<string, number>();
        for (const node of modeNodes) {
            counts.set(node.qualified_name, (counts.get(node.qualified_name) ?? 0) + 1);
        }
        return new Set(
            [...counts.entries()]
                .filter(([, count]) => count > 1)
                .map(([qualifiedName]) => qualifiedName),
        );
    }, [modeNodes]);

    const effectiveFocusId = modeNodes.some((node) => node.node_id === focusId)
        ? focusId
        : (modeNodes[0]?.node_id ?? "");
    const graphRequestKey = JSON.stringify({
        snapshotId,
        focusId: effectiveFocusId,
        mode,
        depth,
        relationshipType,
        resolutionStatus,
        maxNodes: graphLimits.maxNodes,
        maxEdges: graphLimits.maxEdges,
    });

    useEffect(() => {
        if (!effectiveFocusId) {
            graphGeneration.current += 1;
            return;
        }
        const generation = graphGeneration.current + 1;
        graphGeneration.current = generation;
        getRelationshipNeighborhood(snapshotId, {
            focusId: effectiveFocusId,
            mode,
            depth,
            relationshipType,
            resolutionStatus,
            ...graphLimits,
        })
            .then((result) => {
                if (graphGeneration.current === generation) {
                    setGraphResult({ key: graphRequestKey, value: result });
                }
            })
            .catch((caught: unknown) => {
                if (graphGeneration.current === generation) {
                    setGraphErrorResult({
                        key: graphRequestKey,
                        message: messageFrom(
                            caught,
                            "The focused relationship graph could not be loaded.",
                        ),
                    });
                }
            });
        return () => {
            graphGeneration.current += 1;
        };
    }, [
        depth,
        effectiveFocusId,
        graphRequestKey,
        mode,
        relationshipType,
        resolutionStatus,
        snapshotId,
    ]);

    useEffect(
        () => () => {
            nodeGeneration.current += 1;
            graphGeneration.current += 1;
            sourceGeneration.current += 1;
        },
        [],
    );

    const displayedNeighborhood = graphResult?.key === graphRequestKey ? graphResult.value : null;
    const displayedGraphError =
        graphErrorResult?.key === graphRequestKey ? graphErrorResult.message : null;
    const graphLoading = Boolean(
        effectiveFocusId && !displayedNeighborhood && !displayedGraphError,
    );
    const nodeIndex = useMemo(
        () => new Map((displayedNeighborhood?.nodes ?? []).map((node) => [node.node_id, node])),
        [displayedNeighborhood],
    );
    const positioned = useMemo(() => layoutNodes(displayedNeighborhood), [displayedNeighborhood]);
    const positionIndex = useMemo(
        () => new Map(positioned.map((item) => [item.node.node_id, item])),
        [positioned],
    );
    const outgoing = (displayedNeighborhood?.relationships ?? []).filter(
        (relationship) => relationship.source_id === effectiveFocusId,
    );
    const incoming = (displayedNeighborhood?.relationships ?? []).filter(
        (relationship) => relationship.target_id === effectiveFocusId,
    );
    const focusedNode =
        nodeIndex.get(effectiveFocusId) ??
        modeNodes.find((node) => node.node_id === effectiveFocusId);
    const displayedSelectedRelationship =
        selectedRelationshipKey === graphRequestKey &&
        displayedNeighborhood?.relationships.some(
            (item) => item.relationship_id === selectedRelationship?.relationship_id,
        )
            ? selectedRelationship
            : null;

    const chooseFocus = (nodeId: string) => {
        invalidateEvidence();
        setGraphErrorResult(null);
        setFocusId(nodeId);
    };

    const chooseMode = (nextMode: GraphMode) => {
        invalidateEvidence();
        setNodeErrorResult(null);
        setGraphErrorResult(null);
        setSearch("");
        setRequestedNodeIds([]);
        setFocusId("");
        setMode(nextMode);
    };

    const chooseSearch = (value: string) => {
        invalidateEvidence();
        setNodeErrorResult(null);
        setGraphErrorResult(null);
        setRequestedNodeIds([]);
        setFocusId("");
        setSearch(value);
    };

    const updateGraphFilter = (update: () => void) => {
        invalidateEvidence();
        setGraphErrorResult(null);
        update();
    };

    const chooseCycle = (cycleId: string) => {
        const cycle = cycles.find((item) => item.cycle_id === cycleId);
        if (!cycle) return;
        const memberId = cycle.member_node_ids[0] ?? "";
        invalidateEvidence();
        setNodeErrorResult(null);
        setGraphErrorResult(null);
        setSearch("");
        setMode(cycle.relationship_type === "imports" ? "modules" : "inheritance");
        setFocusId(memberId);
        setRequestedNodeIds(memberId ? [memberId] : []);
    };

    const chooseRelationship = (relationship: Relationship) => {
        const generation = sourceGeneration.current + 1;
        sourceGeneration.current = generation;
        setSelectedRelationship(relationship);
        setSelectedRelationshipKey(graphRequestKey);
        setSource(null);
        setSourceError(null);
        setSourceLoading(true);
        getSource(
            snapshotId,
            relationship.relative_path,
            Math.max(1, relationship.line - 3),
            relationship.line + 3,
        )
            .then((result) => {
                if (sourceGeneration.current === generation) setSource(result);
            })
            .catch((caught: unknown) => {
                if (sourceGeneration.current === generation) {
                    setSourceError(messageFrom(caught, "Source evidence could not be loaded."));
                }
            })
            .finally(() => {
                if (sourceGeneration.current === generation) setSourceLoading(false);
            });
    };

    if (!summary && !summaryError) {
        return (
            <section className="view relationships-view">
                <h2>Relationships</h2>
                <p role="status">Loading bounded relationship evidence…</p>
            </section>
        );
    }

    if (summaryError) {
        return (
            <section className="view relationships-view">
                <h2>Relationships</h2>
                <p className="error-message" role="alert">
                    {summaryError}
                </p>
            </section>
        );
    }

    if (summary && !summary.supported) {
        return (
            <section className="view relationships-view">
                <h2>Relationships</h2>
                <p className="relationships-empty">
                    This snapshot predates relationship analysis. Run a new repository scan to
                    create version 2 graph evidence.
                </p>
            </section>
        );
    }

    return (
        <section className="view relationships-view" aria-labelledby="relationships-heading">
            <div className="relationships-heading-row">
                <div>
                    <h2 id="relationships-heading">Relationships</h2>
                    <p>
                        Deterministic static evidence only. Graphs are bounded to{" "}
                        {graphLimits.maxNodes} nodes and {graphLimits.maxEdges} edges.
                    </p>
                </div>
                {summary ? (
                    <dl className="relationship-totals">
                        <div>
                            <dt>Nodes</dt>
                            <dd>{summary.node_count.toLocaleString()}</dd>
                        </div>
                        <div>
                            <dt>Edges</dt>
                            <dd>{summary.relationship_count.toLocaleString()}</dd>
                        </div>
                        <div>
                            <dt>Cycles</dt>
                            <dd>{summary.cycle_count.toLocaleString()}</dd>
                        </div>
                    </dl>
                ) : null}
            </div>
            <div className="relationship-toolbar">
                <Filter
                    label="Graph mode"
                    value={mode}
                    onChange={(value) => chooseMode(value as GraphMode)}
                >
                    <option value="modules">Modules</option>
                    <option value="packages">Packages</option>
                    <option value="inheritance">Inheritance</option>
                    <option value="containment">Containment</option>
                    <option value="types">Type references</option>
                </Filter>
                <label className="search-field relationship-search">
                    <span className="sr-only">Search relationship nodes</span>
                    <SearchIcon />
                    <input
                        type="search"
                        value={search}
                        placeholder="Search nodes"
                        onChange={(event) => chooseSearch(event.target.value)}
                    />
                </label>
                <Filter label="Focus node" value={effectiveFocusId} onChange={chooseFocus}>
                    {modeNodes.length === 0 ? <option value="">No matching nodes</option> : null}
                    {modeNodes.map((node) => (
                        <option value={node.node_id} key={node.node_id}>
                            {node.qualified_name}
                            {duplicateNodeNames.has(node.qualified_name) && node.relative_path
                                ? ` — ${node.relative_path}`
                                : ""}
                        </option>
                    ))}
                </Filter>
                <Filter
                    label="Depth"
                    value={String(depth)}
                    onChange={(value) => updateGraphFilter(() => setDepth(Number(value)))}
                >
                    <option value="1">1 hop</option>
                    <option value="2">2 hops</option>
                    <option value="3">3 hops</option>
                </Filter>
                <Filter
                    label="Relationship"
                    value={relationshipType}
                    onChange={(value) => updateGraphFilter(() => setRelationshipType(value))}
                >
                    <option value="">All relationships</option>
                    <option value="imports">Imports</option>
                    <option value="contains">Contains</option>
                    <option value="inherits">Inherits</option>
                    <option value="references-type">References type</option>
                </Filter>
                <Filter
                    label="Resolution"
                    value={resolutionStatus}
                    onChange={(value) => updateGraphFilter(() => setResolutionStatus(value))}
                >
                    <option value="">All resolutions</option>
                    <option value="resolved-static">Resolved static</option>
                    <option value="probable-static">Probable static</option>
                    <option value="ambiguous">Ambiguous</option>
                    <option value="unresolved-dynamic">Unresolved dynamic</option>
                </Filter>
                <Filter label="Cycle group" value="" onChange={chooseCycle}>
                    <option value="">Choose a cycle</option>
                    {cycles.map((cycle, index) => (
                        <option value={cycle.cycle_id} key={cycle.cycle_id}>
                            Cycle {index + 1} · {cycle.relationship_type} ·{" "}
                            {cycle.member_node_ids.length} nodes
                        </option>
                    ))}
                </Filter>
            </div>
            {nodeLoading ? <p role="status">Searching relationship nodes…</p> : null}
            {displayedNodeError ? (
                <p className="error-message" role="alert">
                    {displayedNodeError}
                </p>
            ) : null}
            {!nodeLoading && !displayedNodeError && displayedNodePage?.total === 0 ? (
                <p className="relationships-empty">No relationship nodes match this search.</p>
            ) : null}
            {displayedNodePage?.truncated ? (
                <p className="truncation-message" role="status">
                    Node search matched {displayedNodePage.total.toLocaleString()} nodes. Showing
                    the first {displayedNodePage.items.length.toLocaleString()} deterministic
                    results; narrow the search to focus another node.
                </p>
            ) : null}
            {displayedGraphError ? (
                <p className="error-message" role="alert">
                    {displayedGraphError}
                </p>
            ) : null}
            {graphLoading ? <p role="status">Loading focused graph…</p> : null}
            {focusedNode ? (
                <p className="selection-status" role="status" aria-live="polite">
                    Selected node: <span className="mono">{focusedNode.qualified_name}</span>
                </p>
            ) : null}
            {displayedNeighborhood?.truncated ? (
                <p className="truncation-message" role="status">
                    Results were truncated at the configured local graph limits. Narrow the mode,
                    focus, filters, or depth.
                </p>
            ) : null}
            {displayedNeighborhood && displayedNeighborhood.nodes.length > 0 ? (
                <div className="relationship-workspace">
                    <div className="graph-panel">
                        <svg
                            className="relationship-graph"
                            viewBox="0 0 820 420"
                            role="img"
                            aria-label="Focused relationship neighborhood"
                            aria-describedby="relationship-graph-description"
                        >
                            <title id="relationship-graph-title">
                                Focused relationship neighborhood
                            </title>
                            <desc id="relationship-graph-description">
                                Nodes are layered by distance from the selected focus. The adjacent
                                node list and relationship lists provide a textual equivalent.
                            </desc>
                            {displayedNeighborhood.relationships.map((relationship) => {
                                const sourcePosition = positionIndex.get(relationship.source_id);
                                const targetPosition = relationship.target_id
                                    ? positionIndex.get(relationship.target_id)
                                    : undefined;
                                return sourcePosition && targetPosition ? (
                                    <line
                                        className={`graph-edge graph-edge--${relationship.relationship_type}`}
                                        x1={sourcePosition.x}
                                        y1={sourcePosition.y}
                                        x2={targetPosition.x}
                                        y2={targetPosition.y}
                                        key={relationship.relationship_id}
                                    />
                                ) : null;
                            })}
                            {positioned.map(({ node, x, y }) => (
                                <g
                                    className={`graph-node ${
                                        node.node_id === effectiveFocusId
                                            ? "graph-node--selected"
                                            : ""
                                    }`}
                                    key={node.node_id}
                                >
                                    <circle cx={x} cy={y} r="8" />
                                    <text x={x + 14} y={y + 4}>
                                        {shortLabel(node.qualified_name)}
                                    </text>
                                </g>
                            ))}
                        </svg>
                    </div>
                    <div className="graph-node-list" aria-label="Graph nodes">
                        <h3>Nodes</h3>
                        <ul>
                            {displayedNeighborhood.nodes.map((node) => (
                                <li key={node.node_id}>
                                    <button
                                        type="button"
                                        aria-pressed={node.node_id === effectiveFocusId}
                                        onClick={() => chooseFocus(node.node_id)}
                                    >
                                        <span className="mono">{node.qualified_name}</span>
                                        <span>
                                            {node.node_type} · distance{" "}
                                            {displayedNeighborhood.distances[node.node_id] ?? 0}
                                            {duplicateNodeNames.has(node.qualified_name) &&
                                            node.relative_path
                                                ? ` · ${node.relative_path}`
                                                : ""}
                                        </span>
                                    </button>
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>
            ) : !graphLoading ? (
                <p className="relationships-empty">
                    No bounded relationships match this mode, focus, and filter selection.
                </p>
            ) : null}
            <div className="relationship-lists">
                <RelationshipList
                    title="Incoming relationships"
                    items={incoming}
                    nodeIndex={nodeIndex}
                    selectedId={displayedSelectedRelationship?.relationship_id ?? null}
                    onSelect={chooseRelationship}
                />
                <RelationshipList
                    title="Outgoing relationships"
                    items={outgoing}
                    nodeIndex={nodeIndex}
                    selectedId={displayedSelectedRelationship?.relationship_id ?? null}
                    onSelect={chooseRelationship}
                />
            </div>
            <RelationshipEvidence
                relationship={displayedSelectedRelationship}
                source={displayedSelectedRelationship ? source : null}
                loading={displayedSelectedRelationship ? sourceLoading : false}
                error={displayedSelectedRelationship ? sourceError : null}
            />
        </section>
    );
}

function Filter({
    label,
    value,
    onChange,
    children,
}: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    children: ReactNode;
}) {
    return (
        <label className="filter-field">
            {label}
            <select value={value} onChange={(event) => onChange(event.target.value)}>
                {children}
            </select>
        </label>
    );
}

function RelationshipList({
    title,
    items,
    nodeIndex,
    selectedId,
    onSelect,
}: {
    title: string;
    items: Relationship[];
    nodeIndex: Map<string, GraphNode>;
    selectedId: string | null;
    onSelect: (relationship: Relationship) => void;
}) {
    return (
        <section>
            <h3>{title}</h3>
            {items.length > 0 ? (
                <ul>
                    {items.map((relationship) => (
                        <li key={relationship.relationship_id}>
                            <button
                                type="button"
                                aria-pressed={relationship.relationship_id === selectedId}
                                onClick={() => onSelect(relationship)}
                            >
                                <span>
                                    {relationship.relationship_type} ·{" "}
                                    {relationship.resolution_status}
                                </span>
                                <span className="mono">
                                    {relationship.target_id
                                        ? (nodeIndex.get(relationship.target_id)?.qualified_name ??
                                          relationship.target_id.slice(0, 12))
                                        : (relationship.unresolved_target ?? "unresolved")}
                                </span>
                            </button>
                        </li>
                    ))}
                </ul>
            ) : (
                <p>No relationships in this bounded neighborhood.</p>
            )}
        </section>
    );
}

function RelationshipEvidence({
    relationship,
    source,
    loading,
    error,
}: {
    relationship: Relationship | null;
    source: SourceEvidence | null;
    loading: boolean;
    error: string | null;
}) {
    return (
        <section className="relationship-evidence" aria-labelledby="relationship-evidence-heading">
            <h3 id="relationship-evidence-heading">Source evidence</h3>
            {!relationship ? (
                <p>Select an incoming or outgoing relationship to inspect its static evidence.</p>
            ) : (
                <>
                    <dl className="source-meta">
                        <div>
                            <dt>Relationship</dt>
                            <dd>{relationship.relationship_type}</dd>
                        </div>
                        <div>
                            <dt>Resolution</dt>
                            <dd>{relationship.resolution_status}</dd>
                        </div>
                        <div>
                            <dt>Location</dt>
                            <dd className="mono">
                                {relationship.relative_path}:{relationship.line}:
                                {relationship.column}
                            </dd>
                        </div>
                        <div>
                            <dt>Evidence</dt>
                            <dd className="mono">{relationship.evidence}</dd>
                        </div>
                    </dl>
                    {loading ? <p role="status">Loading bounded source evidence…</p> : null}
                    {error ? <p className="error-message">{error}</p> : null}
                    {source ? (
                        <pre className="source-code" aria-label="Relationship source excerpt">
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
                </>
            )}
        </section>
    );
}

function layoutNodes(neighborhood: RelationshipNeighborhood | null): PositionedNode[] {
    if (!neighborhood) return [];
    const layers = new Map<number, GraphNode[]>();
    for (const node of neighborhood.nodes) {
        const distance = neighborhood.distances[node.node_id] ?? 0;
        const layer = layers.get(distance) ?? [];
        layer.push(node);
        layers.set(distance, layer);
    }
    const maxDistance = Math.max(1, ...layers.keys());
    const positioned: PositionedNode[] = [];
    for (const [distance, nodes] of [...layers.entries()].sort(([a], [b]) => a - b)) {
        const ordered = [...nodes].sort((a, b) => a.qualified_name.localeCompare(b.qualified_name));
        const x = 54 + (distance * 690) / maxDistance;
        ordered.forEach((node, index) => {
            const y = ordered.length === 1 ? 210 : 42 + (index * 336) / (ordered.length - 1);
            positioned.push({ node, x, y });
        });
    }
    return positioned;
}

function shortLabel(value: string): string {
    const parts = value.split(".");
    return (parts[parts.length - 1] ?? value).slice(0, 22);
}

function messageFrom(error: unknown, fallback: string): string {
    return error instanceof ApiError ? error.message : fallback;
}
