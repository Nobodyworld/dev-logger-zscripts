"""Deterministic static relationship resolution and bounded graph algorithms."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from zscripts.domain.repository_review import (
    ANALYZER_VERSION,
    CycleGroupRecord,
    GraphNodeRecord,
    ModuleRecord,
    RelationshipRecord,
    SymbolRecord,
    TypeReferenceCandidate,
    stable_digest,
)

RESOLVED_STATUSES = frozenset({"resolved-static", "probable-static"})


@dataclass(frozen=True, slots=True)
class RelationshipAnalysisResult:
    """Sorted graph evidence produced from one analyzer result."""

    nodes: tuple[GraphNodeRecord, ...]
    relationships: tuple[RelationshipRecord, ...]
    cycles: tuple[CycleGroupRecord, ...]


@dataclass(frozen=True, slots=True)
class NeighborhoodResult:
    """A deterministic, bounded breadth-first neighborhood."""

    nodes: tuple[GraphNodeRecord, ...]
    relationships: tuple[RelationshipRecord, ...]
    distances: tuple[tuple[str, int], ...]
    truncated: bool


@dataclass(frozen=True, slots=True)
class GraphMetrics:
    """Exact degree and inheritance-depth metrics for a bounded evidence set."""

    fan_in: tuple[tuple[str, int], ...]
    fan_out: tuple[tuple[str, int], ...]
    inheritance_depth: tuple[tuple[str, int | None], ...]


@dataclass(frozen=True, slots=True)
class _Resolution:
    target_ids: tuple[str, ...]
    status: str
    confidence: str


@dataclass(frozen=True, slots=True)
class _AliasTarget:
    target_type: str
    qualified_name: str


class RelationshipAnalyzer:
    """Resolve syntax evidence without importing or executing target code."""

    def analyze(
        self,
        modules: Sequence[ModuleRecord],
        symbols: Sequence[SymbolRecord],
        type_references: Sequence[TypeReferenceCandidate],
    ) -> RelationshipAnalysisResult:
        sorted_modules = tuple(sorted(modules, key=lambda item: (item.module_name, item.module_id)))
        sorted_symbols = tuple(sorted(symbols, key=lambda item: item.symbol_id))
        nodes = _graph_nodes(sorted_modules, sorted_symbols)
        relationships: list[RelationshipRecord] = []
        relationships.extend(_containment_relationships(sorted_modules, sorted_symbols))

        module_index: dict[str, list[ModuleRecord]] = defaultdict(list)
        for module in sorted_modules:
            module_index[module.module_name].append(module)
        symbol_index: dict[str, list[SymbolRecord]] = defaultdict(list)
        for symbol in sorted_symbols:
            symbol_index[symbol.qualified_name].append(symbol)
        aliases = _import_aliases(sorted_modules, module_index, symbol_index)

        relationships.extend(_import_relationships(sorted_modules, module_index))
        for candidate in sorted(type_references, key=lambda item: item.candidate_id):
            relationship_type = "inherits" if candidate.candidate_kind == "inheritance" else "references-type"
            resolution = _resolve_symbol_reference(
                candidate,
                symbols=sorted_symbols,
                modules=sorted_modules,
                symbol_index=symbol_index,
                aliases=aliases,
                class_only=True,
            )
            if len(resolution.target_ids) > 1:
                relationships.append(
                    _relationship(
                        relationship_type=relationship_type,
                        source_id=candidate.source_symbol_id,
                        target_id=None,
                        unresolved_target=candidate.textual_name,
                        resolution_status="ambiguous",
                        confidence="low",
                        relative_path=candidate.relative_path,
                        line=candidate.line,
                        column=candidate.column,
                        evidence=candidate.evidence,
                    )
                )
            elif resolution.target_ids:
                relationships.append(
                    _relationship(
                        relationship_type=relationship_type,
                        source_id=candidate.source_symbol_id,
                        target_id=resolution.target_ids[0],
                        unresolved_target=None,
                        resolution_status=resolution.status,
                        confidence=resolution.confidence,
                        relative_path=candidate.relative_path,
                        line=candidate.line,
                        column=candidate.column,
                        evidence=candidate.evidence,
                    )
                )
            else:
                relationships.append(
                    _relationship(
                        relationship_type=relationship_type,
                        source_id=candidate.source_symbol_id,
                        target_id=None,
                        unresolved_target=candidate.textual_name,
                        resolution_status="unresolved-dynamic",
                        confidence="low",
                        relative_path=candidate.relative_path,
                        line=candidate.line,
                        column=candidate.column,
                        evidence=candidate.evidence,
                    )
                )

        ordered_relationships = tuple(sorted(relationships, key=_relationship_sort_key))
        cycles = tuple(
            sorted(
                (
                    *cycle_groups(nodes, ordered_relationships, relationship_type="imports"),
                    *cycle_groups(nodes, ordered_relationships, relationship_type="inherits"),
                ),
                key=lambda item: item.cycle_id,
            )
        )
        return RelationshipAnalysisResult(
            nodes=nodes,
            relationships=ordered_relationships,
            cycles=cycles,
        )


def strongly_connected_components(
    node_ids: Iterable[str],
    relationships: Sequence[RelationshipRecord],
) -> tuple[tuple[str, ...], ...]:
    """Return deterministic SCC membership using iterative Kosaraju traversal."""

    nodes = tuple(sorted(set(node_ids)))
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    reverse: dict[str, set[str]] = {node: set() for node in nodes}
    for edge in relationships:
        if edge.target_id is None or edge.resolution_status != "resolved-static":
            continue
        if edge.source_id not in adjacency or edge.target_id not in adjacency:
            continue
        adjacency[edge.source_id].add(edge.target_id)
        reverse[edge.target_id].add(edge.source_id)

    visited: set[str] = set()
    finish_order: list[str] = []
    for start in nodes:
        if start in visited:
            continue
        visited.add(start)
        stack: list[tuple[str, bool]] = [(start, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                finish_order.append(node)
                continue
            stack.append((node, True))
            for neighbor in sorted(adjacency[node], reverse=True):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append((neighbor, False))

    assigned: set[str] = set()
    components: list[tuple[str, ...]] = []
    for start in reversed(finish_order):
        if start in assigned:
            continue
        component: list[str] = []
        component_stack = [start]
        assigned.add(start)
        while component_stack:
            node = component_stack.pop()
            component.append(node)
            for neighbor in sorted(reverse[node], reverse=True):
                if neighbor not in assigned:
                    assigned.add(neighbor)
                    component_stack.append(neighbor)
        components.append(tuple(sorted(component)))
    return tuple(sorted(components, key=lambda item: (item[0], len(item), item)))


def cycle_groups(
    nodes: Sequence[GraphNodeRecord],
    relationships: Sequence[RelationshipRecord],
    *,
    relationship_type: str,
) -> tuple[CycleGroupRecord, ...]:
    """Identify cyclic SCCs and derive stable identifiers from members and edges."""

    relevant_edges = tuple(
        edge
        for edge in relationships
        if edge.relationship_type == relationship_type
        and edge.target_id is not None
        and edge.resolution_status == "resolved-static"
    )
    node_ids = {
        node.node_id
        for node in nodes
        if any(edge.source_id == node.node_id or edge.target_id == node.node_id for edge in relevant_edges)
    }
    groups: list[CycleGroupRecord] = []
    for component in strongly_connected_components(node_ids, relevant_edges):
        members = set(component)
        edge_ids = tuple(
            sorted(
                edge.relationship_id
                for edge in relevant_edges
                if edge.source_id in members and edge.target_id in members
            )
        )
        self_cycle = len(component) == 1 and any(
            edge.source_id == component[0] and edge.target_id == component[0] for edge in relevant_edges
        )
        if len(component) < 2 and not self_cycle:
            continue
        cycle_id = stable_digest(
            "repository-review-cycle",
            {
                "relationship_type": relationship_type,
                "members": component,
                "edges": edge_ids,
            },
        )
        groups.append(
            CycleGroupRecord(
                cycle_id=cycle_id,
                relationship_type=relationship_type,
                member_node_ids=component,
                edge_ids=edge_ids,
            )
        )
    return tuple(sorted(groups, key=lambda item: item.cycle_id))


def graph_metrics(
    nodes: Sequence[GraphNodeRecord],
    relationships: Sequence[RelationshipRecord],
) -> GraphMetrics:
    """Calculate deterministic degrees and cycle-safe inheritance depths."""

    node_ids = {node.node_id for node in nodes}
    fan_in = {node_id: 0 for node_id in node_ids}
    fan_out = {node_id: 0 for node_id in node_ids}
    inheritance_parents: dict[str, set[str]] = defaultdict(set)
    for edge in relationships:
        if (
            edge.target_id is None
            or edge.resolution_status not in RESOLVED_STATUSES
            or edge.source_id not in node_ids
            or edge.target_id not in node_ids
        ):
            continue
        fan_out[edge.source_id] += 1
        fan_in[edge.target_id] += 1
        if edge.relationship_type == "inherits":
            inheritance_parents[edge.source_id].add(edge.target_id)

    depth_cache: dict[str, int | None] = {}

    def depth(node_id: str, visiting: set[str]) -> int | None:
        if node_id in depth_cache:
            return depth_cache[node_id]
        if node_id in visiting:
            return None
        parents = inheritance_parents.get(node_id)
        if not parents:
            depth_cache[node_id] = 0
            return 0
        parent_depths = [depth(parent, {*visiting, node_id}) for parent in sorted(parents)]
        if any(item is None for item in parent_depths):
            depth_cache[node_id] = None
        else:
            numeric_depths = [item for item in parent_depths if item is not None]
            depth_cache[node_id] = 1 + max(numeric_depths)
        return depth_cache[node_id]

    inheritance_depth = {node_id: depth(node_id, set()) for node_id in sorted(inheritance_parents)}
    return GraphMetrics(
        fan_in=tuple(sorted(fan_in.items())),
        fan_out=tuple(sorted(fan_out.items())),
        inheritance_depth=tuple(sorted(inheritance_depth.items())),
    )


def bounded_neighborhood(
    nodes: Sequence[GraphNodeRecord],
    relationships: Sequence[RelationshipRecord],
    *,
    focus_id: str,
    depth: int,
    max_nodes: int,
    max_edges: int,
) -> NeighborhoodResult:
    """Return a stable undirected expansion while preserving directed edges."""

    if depth < 0 or max_nodes < 1 or max_edges < 1:
        raise ValueError("Neighborhood limits must be positive.")
    node_index = {node.node_id: node for node in nodes}
    if focus_id not in node_index:
        raise KeyError(focus_id)
    resolved_edges = tuple(
        sorted(
            (
                edge
                for edge in relationships
                if edge.target_id is not None and edge.resolution_status in RESOLVED_STATUSES
            ),
            key=_relationship_sort_key,
        )
    )
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in resolved_edges:
        if edge.source_id in node_index and edge.target_id in node_index:
            adjacency[edge.source_id].add(edge.target_id)
            adjacency[edge.target_id].add(edge.source_id)

    distances = {focus_id: 0}
    queue: deque[str] = deque([focus_id])
    truncated = False
    while queue:
        current = queue.popleft()
        current_depth = distances[current]
        if current_depth >= depth:
            continue
        for neighbor in sorted(adjacency[current]):
            if neighbor in distances:
                continue
            if len(distances) >= max_nodes:
                truncated = True
                continue
            distances[neighbor] = current_depth + 1
            queue.append(neighbor)

    selected_ids = set(distances)
    selected_edges = sorted(
        (
            edge
            for edge in relationships
            if edge.source_id in selected_ids and (edge.target_id is None or edge.target_id in selected_ids)
        ),
        key=_relationship_sort_key,
    )
    if len(selected_edges) > max_edges:
        selected_edges = selected_edges[:max_edges]
        truncated = True
    return NeighborhoodResult(
        nodes=tuple(
            sorted(
                (node_index[node_id] for node_id in selected_ids),
                key=lambda item: (distances[item.node_id], item.qualified_name, item.node_id),
            )
        ),
        relationships=tuple(selected_edges),
        distances=tuple(sorted(distances.items(), key=lambda item: (item[1], item[0]))),
        truncated=truncated,
    )


def _graph_nodes(
    modules: Sequence[ModuleRecord],
    symbols: Sequence[SymbolRecord],
) -> tuple[GraphNodeRecord, ...]:
    nodes: dict[str, GraphNodeRecord] = {}
    for module in modules:
        package_name = _module_package(module)
        for package in _package_prefixes(package_name):
            node_id = _package_id(package)
            nodes[node_id] = GraphNodeRecord(
                node_id=node_id,
                node_type="package",
                display_name=package.rpartition(".")[2],
                qualified_name=package,
                relative_path=None,
                symbol_kind=None,
            )
        nodes[module.module_id] = GraphNodeRecord(
            node_id=module.module_id,
            node_type="module",
            display_name=module.module_name.rpartition(".")[2],
            qualified_name=module.module_name,
            relative_path=module.relative_path,
            symbol_kind=None,
        )
    for symbol in symbols:
        nodes[symbol.symbol_id] = GraphNodeRecord(
            node_id=symbol.symbol_id,
            node_type="symbol",
            display_name=symbol.display_name,
            qualified_name=symbol.qualified_name,
            relative_path=symbol.relative_path,
            symbol_kind=symbol.kind,
        )
    return tuple(sorted(nodes.values(), key=lambda item: item.node_id))


def _containment_relationships(
    modules: Sequence[ModuleRecord],
    symbols: Sequence[SymbolRecord],
) -> list[RelationshipRecord]:
    relationships: list[RelationshipRecord] = []
    for module in modules:
        package_name = _module_package(module)
        if package_name:
            relationships.append(
                _relationship(
                    relationship_type="contains",
                    source_id=_package_id(package_name),
                    target_id=module.module_id,
                    unresolved_target=None,
                    resolution_status="resolved-static",
                    confidence="high",
                    relative_path=module.relative_path,
                    line=1,
                    column=0,
                    evidence=f"{package_name} contains module {module.module_name}",
                )
            )
    module_ids = {module.file_id: module.module_id for module in modules}
    for symbol in symbols:
        source_id = symbol.parent_symbol_id or module_ids.get(symbol.file_id)
        if source_id is None:
            continue
        relationships.append(
            _relationship(
                relationship_type="contains",
                source_id=source_id,
                target_id=symbol.symbol_id,
                unresolved_target=None,
                resolution_status="resolved-static",
                confidence="high",
                relative_path=symbol.relative_path,
                line=symbol.start_line,
                column=symbol.start_column,
                evidence=f"contains {symbol.kind} {symbol.display_name}",
            )
        )
    return relationships


def _import_relationships(
    modules: Sequence[ModuleRecord],
    module_index: dict[str, list[ModuleRecord]],
) -> list[RelationshipRecord]:
    relationships: list[RelationshipRecord] = []
    for source in modules:
        for imported in source.imports:
            base_name = _absolute_import_name(source, imported.module, imported.level)
            display_target = _import_evidence_target(base_name, imported.imported_name)
            target_name = base_name
            if imported.imported_name and base_name:
                submodule_name = f"{base_name}.{imported.imported_name}"
                if submodule_name in module_index:
                    target_name = submodule_name
            matches = module_index.get(target_name or "", [])
            if len(matches) == 1:
                relationships.append(
                    _relationship(
                        relationship_type="imports",
                        source_id=source.module_id,
                        target_id=matches[0].module_id,
                        unresolved_target=None,
                        resolution_status="resolved-static",
                        confidence="high",
                        relative_path=source.relative_path,
                        line=imported.line,
                        column=imported.column,
                        evidence=display_target,
                    )
                )
            elif len(matches) > 1:
                relationships.append(
                    _relationship(
                        relationship_type="imports",
                        source_id=source.module_id,
                        target_id=None,
                        unresolved_target=display_target,
                        resolution_status="ambiguous",
                        confidence="low",
                        relative_path=source.relative_path,
                        line=imported.line,
                        column=imported.column,
                        evidence=display_target,
                    )
                )
            else:
                relationships.append(
                    _relationship(
                        relationship_type="imports",
                        source_id=source.module_id,
                        target_id=None,
                        unresolved_target=display_target,
                        resolution_status="unresolved-dynamic",
                        confidence="low",
                        relative_path=source.relative_path,
                        line=imported.line,
                        column=imported.column,
                        evidence=display_target,
                    )
                )
    return relationships


def _import_aliases(
    modules: Sequence[ModuleRecord],
    module_index: dict[str, list[ModuleRecord]],
    symbol_index: dict[str, list[SymbolRecord]],
) -> dict[str, dict[str, tuple[_AliasTarget, ...]]]:
    result: dict[str, dict[str, tuple[_AliasTarget, ...]]] = {}
    for source in modules:
        alias_map: dict[str, list[_AliasTarget]] = defaultdict(list)
        for imported in source.imports:
            base_name = _absolute_import_name(source, imported.module, imported.level)
            if not base_name:
                continue
            if imported.imported_name is None:
                binding = imported.alias or base_name.split(".")[0]
                target_name = base_name if imported.alias else binding
                if target_name in module_index:
                    alias_map[binding].append(_AliasTarget("module", target_name))
                continue
            binding = imported.alias or imported.imported_name
            submodule_name = f"{base_name}.{imported.imported_name}"
            symbol_name = submodule_name
            if submodule_name in module_index:
                alias_map[binding].append(_AliasTarget("module", submodule_name))
            if symbol_name in symbol_index:
                alias_map[binding].append(_AliasTarget("symbol", symbol_name))
        result[source.relative_path] = {
            binding: tuple(sorted(set(targets), key=lambda item: (item.target_type, item.qualified_name)))
            for binding, targets in alias_map.items()
        }
    return result


def _resolve_symbol_reference(
    candidate: TypeReferenceCandidate,
    *,
    symbols: Sequence[SymbolRecord],
    modules: Sequence[ModuleRecord],
    symbol_index: dict[str, list[SymbolRecord]],
    aliases: dict[str, dict[str, tuple[_AliasTarget, ...]]],
    class_only: bool,
) -> _Resolution:
    def matching(qualified_name: str) -> list[SymbolRecord]:
        matches = symbol_index.get(qualified_name, [])
        return [item for item in matches if not class_only or item.kind == "class"]

    direct = matching(candidate.textual_name)
    if direct:
        return _from_symbol_matches(direct, "resolved-static", "high")

    local = matching(f"{candidate.module_name}.{candidate.textual_name}")
    if local:
        return _from_symbol_matches(local, "resolved-static", "high")

    head, separator, tail = candidate.textual_name.partition(".")
    alias_targets = aliases.get(candidate.relative_path, {}).get(head, ())
    alias_matches: list[SymbolRecord] = []
    for target in alias_targets:
        if target.target_type == "symbol":
            qualified = target.qualified_name + (f".{tail}" if separator else "")
        else:
            qualified = target.qualified_name + (f".{tail}" if separator else "")
        alias_matches.extend(matching(qualified))
    if alias_matches:
        return _from_symbol_matches(alias_matches, "resolved-static", "high")

    package = candidate.module_name.rpartition(".")[0]
    exported_candidates: list[SymbolRecord] = []
    if not separator and package:
        package_modules = [
            module
            for module in modules
            if module.module_name == package and candidate.textual_name in module.public_exports
        ]
        if package_modules:
            exported_candidates = [
                symbol
                for symbol in symbols
                if symbol.display_name == candidate.textual_name
                and symbol.qualified_name.startswith(f"{package}.")
                and (not class_only or symbol.kind == "class")
            ]
    if exported_candidates:
        return _from_symbol_matches(exported_candidates, "probable-static", "medium")
    return _Resolution((), "unresolved-dynamic", "low")


def _from_symbol_matches(
    matches: Sequence[SymbolRecord],
    status: str,
    confidence: str,
) -> _Resolution:
    target_ids = tuple(sorted({item.symbol_id for item in matches}))
    if len(target_ids) > 1:
        return _Resolution(target_ids, "ambiguous", "low")
    return _Resolution(target_ids, status, confidence)


def _absolute_import_name(source: ModuleRecord, module: str | None, level: int) -> str | None:
    if level <= 0:
        return module
    package = _module_package(source)
    parts = package.split(".") if package else []
    parent_count = level - 1
    if parent_count > len(parts):
        return None
    prefix = parts[: len(parts) - parent_count]
    if module:
        prefix.extend(module.split("."))
    return ".".join(prefix) or None


def _module_package(module: ModuleRecord) -> str:
    if PurePosixPath(module.relative_path).name == "__init__.py":
        return module.module_name
    return module.package


def _package_prefixes(package: str) -> tuple[str, ...]:
    parts = package.split(".") if package else []
    return tuple(".".join(parts[:index]) for index in range(1, len(parts) + 1))


def _package_id(package: str) -> str:
    return stable_digest("repository-review-package", {"qualified_name": package})


def _import_evidence_target(module: str | None, imported_name: str | None) -> str:
    if module and imported_name:
        return f"from {module} import {imported_name}"
    if module:
        return f"import {module}"
    if imported_name:
        return f"relative import {imported_name}"
    return "dynamic import"


def _relationship(
    *,
    relationship_type: str,
    source_id: str,
    target_id: str | None,
    unresolved_target: str | None,
    resolution_status: str,
    confidence: str,
    relative_path: str,
    line: int,
    column: int,
    evidence: str,
) -> RelationshipRecord:
    payload = {
        "relationship_type": relationship_type,
        "source_id": source_id,
        "target_id": target_id,
        "unresolved_target": unresolved_target,
        "resolution_status": resolution_status,
        "confidence": confidence,
        "relative_path": relative_path,
        "line": line,
        "column": column,
        "analyzer_version": ANALYZER_VERSION,
        "evidence": evidence,
    }
    return RelationshipRecord(
        relationship_id=stable_digest("repository-review-relationship", payload),
        relationship_type=relationship_type,
        source_id=source_id,
        target_id=target_id,
        unresolved_target=unresolved_target,
        resolution_status=resolution_status,
        confidence=confidence,
        relative_path=relative_path,
        line=line,
        column=column,
        analyzer_version=ANALYZER_VERSION,
        evidence=evidence,
    )


def _relationship_sort_key(
    record: RelationshipRecord,
) -> tuple[str, str, str, str, int, int, str]:
    return (
        record.relationship_type,
        record.source_id,
        record.target_id or record.unresolved_target or "",
        record.relative_path,
        record.line,
        record.column,
        record.relationship_id,
    )


__all__ = [
    "GraphMetrics",
    "NeighborhoodResult",
    "RESOLVED_STATUSES",
    "RelationshipAnalysisResult",
    "RelationshipAnalyzer",
    "bounded_neighborhood",
    "cycle_groups",
    "graph_metrics",
    "strongly_connected_components",
]
