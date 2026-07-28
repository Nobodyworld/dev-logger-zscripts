"""Deterministic raw metrics and conservative repository finding rules."""

from __future__ import annotations

import ast
import io
import tokenize
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, fields
from pathlib import PurePosixPath

from zscripts.domain.repository_review import (
    ANALYZER_VERSION,
    CycleGroupRecord,
    FindingEvidenceRecord,
    GraphNodeRecord,
    MetricRecord,
    ModuleRecord,
    RelationshipRecord,
    RepositoryRecord,
    SymbolRecord,
    stable_digest,
)
from zscripts.infrastructure.relationship_analysis import graph_metrics
from zscripts.infrastructure.repository_discovery import DiscoveredFile

RESOLVED_STATUSES = frozenset({"resolved-static", "probable-static"})


@dataclass(frozen=True, slots=True)
class FindingPolicy:
    """Immutable experimental thresholds for rule-set version 4."""

    rule_version: str = "1"
    function_lines: int = 80
    class_lines: int = 400
    module_lines: int = 1_000
    cyclomatic_complexity: int = 15
    maximum_nesting: int = 5
    parameter_count: int = 8
    fan_in: int = 12
    fan_out: int = 12
    inheritance_depth: int = 5

    def public_thresholds(self) -> tuple[tuple[str, int], ...]:
        return tuple(
            (field.name, int(getattr(self, field.name)))
            for field in fields(self)
            if field.name != "rule_version"
        )


DEFAULT_FINDING_POLICY = FindingPolicy()


@dataclass(frozen=True, slots=True)
class FindingAnalysisResult:
    """Sorted metric and finding evidence ready for canonical persistence."""

    metrics: tuple[MetricRecord, ...]
    findings: tuple[FindingEvidenceRecord, ...]


class FindingAnalyzer:
    """Calculate metadata-only measurements and versioned finding evidence."""

    def __init__(self, policy: FindingPolicy = DEFAULT_FINDING_POLICY) -> None:
        self.policy = policy

    def analyze(
        self,
        repository: RepositoryRecord,
        discovered_files: Sequence[DiscoveredFile],
        modules: Sequence[ModuleRecord],
        symbols: Sequence[SymbolRecord],
        nodes: Sequence[GraphNodeRecord],
        relationships: Sequence[RelationshipRecord],
        cycles: Sequence[CycleGroupRecord],
    ) -> FindingAnalysisResult:
        syntax = _syntax_metrics(discovered_files)
        metrics = _metric_records(
            modules=modules,
            symbols=symbols,
            nodes=nodes,
            relationships=relationships,
            cycles=cycles,
            syntax=syntax,
        )
        findings = _finding_records(
            repository_id=repository.repository_id,
            modules=modules,
            symbols=symbols,
            nodes=nodes,
            relationships=relationships,
            cycles=cycles,
            metrics=metrics,
            policy=self.policy,
        )
        findings = _merge_findings(findings)
        return FindingAnalysisResult(
            metrics=tuple(sorted(metrics, key=lambda item: (item.subject_id, item.metric_name))),
            findings=tuple(sorted(findings, key=lambda item: item.finding_id)),
        )


@dataclass(frozen=True, slots=True)
class _SyntaxMetric:
    relative_path: str
    start_line: int
    line_count: int
    parameter_count: int
    maximum_nesting: int
    cyclomatic_complexity: int


def _syntax_metrics(files: Sequence[DiscoveredFile]) -> dict[tuple[str, int], _SyntaxMetric]:
    result: dict[tuple[str, int], _SyntaxMetric] = {}
    for discovered in files:
        if not discovered.record.included or discovered.content is None:
            continue
        try:
            text = _decode_python(discovered.content)
            tree = ast.parse(text, filename=discovered.record.relative_path, type_comments=True)
        except (SyntaxError, UnicodeDecodeError, LookupError):
            continue
        result[(discovered.record.relative_path, 0)] = _SyntaxMetric(
            relative_path=discovered.record.relative_path,
            start_line=0,
            line_count=len(text.splitlines()),
            parameter_count=0,
            maximum_nesting=_scope_nesting(tree),
            cyclomatic_complexity=_scope_complexity(tree),
        )
        for node in ast.walk(tree):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            result[(discovered.record.relative_path, node.lineno)] = _SyntaxMetric(
                relative_path=discovered.record.relative_path,
                start_line=node.lineno,
                line_count=max(int(getattr(node, "end_lineno", node.lineno)) - node.lineno + 1, 1),
                parameter_count=_parameter_count(node),
                maximum_nesting=_scope_nesting(node),
                cyclomatic_complexity=_scope_complexity(node),
            )
    return result


def _metric_records(
    *,
    modules: Sequence[ModuleRecord],
    symbols: Sequence[SymbolRecord],
    nodes: Sequence[GraphNodeRecord],
    relationships: Sequence[RelationshipRecord],
    cycles: Sequence[CycleGroupRecord],
    syntax: dict[tuple[str, int], _SyntaxMetric],
) -> list[MetricRecord]:
    records: list[MetricRecord] = []
    module_by_name = {item.module_name: item for item in modules}
    symbols_by_module: dict[str, list[SymbolRecord]] = defaultdict(list)
    for symbol in symbols:
        symbols_by_module[symbol.module_name].append(symbol)

    import_edges = [
        item
        for item in relationships
        if item.relationship_type == "imports"
        and item.target_id is not None
        and item.resolution_status in RESOLVED_STATUSES
    ]
    import_in: dict[str, int] = defaultdict(int)
    import_out: dict[str, int] = defaultdict(int)
    for relationship in import_edges:
        import_out[relationship.source_id] += 1
        if relationship.target_id is not None:
            import_in[relationship.target_id] += 1

    inheritance_edges = [
        item
        for item in relationships
        if item.relationship_type == "inherits"
        and item.target_id is not None
        and item.resolution_status in RESOLVED_STATUSES
    ]
    parents: dict[str, int] = defaultdict(int)
    children: dict[str, int] = defaultdict(int)
    for relationship in inheritance_edges:
        parents[relationship.source_id] += 1
        if relationship.target_id is not None:
            children[relationship.target_id] += 1
    depths = dict(graph_metrics(nodes, inheritance_edges).inheritance_depth)

    import_cycle_members = {
        node_id
        for cycle in cycles
        if cycle.relationship_type == "imports"
        for node_id in cycle.member_node_ids
    }
    inheritance_cycle_members = {
        node_id
        for cycle in cycles
        if cycle.relationship_type == "inherits"
        for node_id in cycle.member_node_ids
    }
    nearby_test_modules = _nearby_test_modules(modules, import_edges)

    for module in modules:
        module_symbols = symbols_by_module.get(module.module_name, [])
        top_level = [item for item in module_symbols if item.parent_symbol_id is None]
        syntax_metric = syntax.get((module.relative_path, 0))
        values = {
            "file_line_count": float(syntax_metric.line_count if syntax_metric else 0),
            "class_count": float(sum(item.kind == "class" for item in module_symbols)),
            "function_method_count": float(
                sum(item.kind in {"function", "method"} for item in module_symbols)
            ),
            "public_symbol_count": float(sum(item.visibility == "public" for item in top_level)),
            "total_symbol_count": float(len(module_symbols)),
            "resolved_fan_in": float(import_in[module.module_id]),
            "resolved_fan_out": float(import_out[module.module_id]),
            "import_cycle_membership": float(module.module_id in import_cycle_members),
            "nearby_test_evidence": float(module.module_id in nearby_test_modules),
        }
        for name, value in values.items():
            records.append(
                _metric(
                    subject_id=module.module_id,
                    subject_type="module",
                    metric_name=name,
                    value=value,
                    unit="boolean" if name.endswith(("membership", "evidence")) else "count",
                    relative_path=module.relative_path,
                    line=1,
                )
            )

    for symbol in symbols:
        syntax_metric = syntax.get((symbol.relative_path, symbol.start_line))
        module_record = module_by_name.get(symbol.module_name)
        values = {
            "source_line_span": float(symbol.end_line - symbol.start_line + 1),
            "parameter_count": float(syntax_metric.parameter_count if syntax_metric else 0),
            "maximum_nesting": float(syntax_metric.maximum_nesting if syntax_metric else 0),
            "cyclomatic_complexity": float(syntax_metric.cyclomatic_complexity if syntax_metric else 1),
            "documentation_present": float(symbol.docstring_present),
            "public_visibility": float(symbol.visibility == "public"),
            "nearby_test_evidence": float(
                module_record is not None and module_record.module_id in nearby_test_modules
            ),
            "direct_parent_count": float(parents[symbol.symbol_id]),
            "direct_child_count": float(children[symbol.symbol_id]),
            "inheritance_cycle_membership": float(symbol.symbol_id in inheritance_cycle_members),
        }
        depth = depths.get(symbol.symbol_id)
        if depth is not None:
            values["resolved_inheritance_depth"] = float(depth)
        for name, value in values.items():
            records.append(
                _metric(
                    subject_id=symbol.symbol_id,
                    subject_type="symbol",
                    metric_name=name,
                    value=value,
                    unit="boolean"
                    if name.endswith(("present", "visibility", "evidence", "membership"))
                    else "count",
                    relative_path=symbol.relative_path,
                    line=symbol.start_line,
                )
            )
    return records


def _finding_records(
    *,
    repository_id: str,
    modules: Sequence[ModuleRecord],
    symbols: Sequence[SymbolRecord],
    nodes: Sequence[GraphNodeRecord],
    relationships: Sequence[RelationshipRecord],
    cycles: Sequence[CycleGroupRecord],
    metrics: Sequence[MetricRecord],
    policy: FindingPolicy,
) -> list[FindingEvidenceRecord]:
    result: list[FindingEvidenceRecord] = []
    metric_index = {(item.subject_id, item.metric_name): item.numeric_value for item in metrics}
    node_index = {item.node_id: item for item in nodes}
    module_by_name = {item.module_name: item for item in modules}

    for cycle in cycles:
        if cycle.relationship_type not in {"imports", "inherits"}:
            continue
        members = tuple(
            sorted(node_index[item].qualified_name for item in cycle.member_node_ids if item in node_index)
        )
        if not members:
            continue
        family = "dependency-cycle" if cycle.relationship_type == "imports" else "inheritance-cycle"
        title = (
            "Confirmed module dependency cycle"
            if cycle.relationship_type == "imports"
            else "Confirmed inheritance cycle"
        )
        result.append(
            _finding(
                repository_id=repository_id,
                rule_id=family,
                policy=policy,
                family=family,
                title=title,
                explanation="Resolved internal relationships form a confirmed static cycle.",
                suggested_action="Review whether the cycle can be reduced without changing behavior.",
                severity="high",
                confidence="high",
                subject_type="cycle",
                subject_keys=members,
                affected_node_ids=cycle.member_node_ids,
                relative_path=None,
                line=None,
                metric_evidence=(("member_count", float(len(members))),),
            )
        )

    duplicate_groups: dict[tuple[str, str], list[SymbolRecord]] = defaultdict(list)
    for symbol in symbols:
        if _excluded_symbol(symbol) or symbol.display_name.startswith("__"):
            continue
        duplicate_groups[(symbol.kind, symbol.display_name)].append(symbol)
    for (kind, name), group in sorted(duplicate_groups.items()):
        unique = {item.qualified_name: item for item in group}
        minimum = 5 if kind == "method" else 2
        if len(unique) < minimum:
            continue
        ordered = tuple(unique[key] for key in sorted(unique))
        result.append(
            _finding(
                repository_id=repository_id,
                rule_id="exact-duplicate-symbol-name",
                policy=policy,
                family="duplicate-name-candidate",
                title=f"Repeated exact {kind} name candidate",
                explanation=(
                    f'The exact case-sensitive name "{name}" appears in {len(ordered)} '
                    "different qualified symbols. This does not imply duplicate behavior."
                ),
                suggested_action="Confirm whether the repeated name is intentional and clear in context.",
                severity="low",
                confidence="high",
                subject_type="symbol-group",
                subject_keys=tuple(item.qualified_name for item in ordered),
                affected_node_ids=tuple(item.symbol_id for item in ordered),
                relative_path=ordered[0].relative_path,
                line=ordered[0].start_line,
                metric_evidence=(("duplicate_count", float(len(ordered))),),
            )
        )

    for module in sorted(modules, key=lambda item: item.module_name):
        line_count = metric_index.get((module.module_id, "file_line_count"), 0)
        if line_count > policy.module_lines:
            result.append(
                _threshold_finding(
                    repository_id,
                    "oversized-module",
                    policy,
                    "oversized",
                    "Large module",
                    module.module_name,
                    "module",
                    module.module_id,
                    module.relative_path,
                    1,
                    "file_line_count",
                    line_count,
                    policy.module_lines,
                )
            )
        for metric_name, threshold, label in (
            ("resolved_fan_in", policy.fan_in, "High resolved fan-in"),
            ("resolved_fan_out", policy.fan_out, "High resolved fan-out"),
        ):
            value = metric_index.get((module.module_id, metric_name), 0)
            if value > threshold:
                result.append(
                    _threshold_finding(
                        repository_id,
                        f"high-{metric_name.replace('_', '-')}",
                        policy,
                        "coupling",
                        label,
                        module.module_name,
                        "module",
                        module.module_id,
                        module.relative_path,
                        1,
                        metric_name,
                        value,
                        threshold,
                        fixed_severity="medium",
                    )
                )

    incoming = _resolved_non_containment_incoming(relationships)
    explicit_exports = {
        f"{module.module_name}.{name}" for module in modules for name in module.public_exports
    }
    for symbol in sorted(symbols, key=lambda item: item.qualified_name):
        if _excluded_symbol(symbol):
            continue
        span = metric_index.get((symbol.symbol_id, "source_line_span"), 0)
        line_threshold = policy.class_lines if symbol.kind == "class" else policy.function_lines
        if symbol.kind in {"class", "function", "method"} and span > line_threshold:
            result.append(
                _threshold_finding(
                    repository_id,
                    "oversized-symbol",
                    policy,
                    "oversized",
                    f"Large {symbol.kind}",
                    symbol.qualified_name,
                    "symbol",
                    symbol.symbol_id,
                    symbol.relative_path,
                    symbol.start_line,
                    "source_line_span",
                    span,
                    line_threshold,
                )
            )
        complexity = metric_index.get((symbol.symbol_id, "cyclomatic_complexity"), 1)
        if symbol.kind in {"function", "method"} and complexity > policy.cyclomatic_complexity:
            result.append(
                _threshold_finding(
                    repository_id,
                    "high-cyclomatic-complexity",
                    policy,
                    "complexity",
                    "High static cyclomatic complexity",
                    symbol.qualified_name,
                    "symbol",
                    symbol.symbol_id,
                    symbol.relative_path,
                    symbol.start_line,
                    "cyclomatic_complexity",
                    complexity,
                    policy.cyclomatic_complexity,
                    fixed_severity="medium",
                )
            )
            if metric_index.get((symbol.symbol_id, "nearby_test_evidence"), 0) == 0:
                result.append(
                    _finding(
                        repository_id=repository_id,
                        rule_id="complexity-without-nearby-test-evidence",
                        policy=policy,
                        family="test-evidence-candidate",
                        title="High complexity without nearby test evidence",
                        explanation=(
                            "Static complexity exceeds the experimental threshold and no recognized "
                            "test module has a resolved import to this source module. This is not a "
                            "claim that the symbol is untested."
                        ),
                        suggested_action="Review available tests and add focused coverage if appropriate.",
                        severity="medium",
                        confidence="medium",
                        subject_type="symbol",
                        subject_keys=(symbol.qualified_name,),
                        affected_node_ids=(symbol.symbol_id,),
                        relative_path=symbol.relative_path,
                        line=symbol.start_line,
                        metric_evidence=(("cyclomatic_complexity", complexity),),
                        threshold_evidence=(("cyclomatic_complexity", float(policy.cyclomatic_complexity)),),
                    )
                )
        for metric_name, threshold, title, family in (
            ("maximum_nesting", policy.maximum_nesting, "Deeply nested symbol", "nesting"),
            ("parameter_count", policy.parameter_count, "Many parameters", "parameters"),
        ):
            value = metric_index.get((symbol.symbol_id, metric_name), 0)
            if symbol.kind in {"function", "method"} and value > threshold:
                result.append(
                    _threshold_finding(
                        repository_id,
                        f"high-{metric_name.replace('_', '-')}",
                        policy,
                        family,
                        title,
                        symbol.qualified_name,
                        "symbol",
                        symbol.symbol_id,
                        symbol.relative_path,
                        symbol.start_line,
                        metric_name,
                        value,
                        threshold,
                    )
                )
        depth = metric_index.get((symbol.symbol_id, "resolved_inheritance_depth"))
        in_cycle = metric_index.get((symbol.symbol_id, "inheritance_cycle_membership"), 0)
        if symbol.kind == "class" and depth is not None and not in_cycle and depth > policy.inheritance_depth:
            result.append(
                _threshold_finding(
                    repository_id,
                    "deep-inheritance",
                    policy,
                    "inheritance",
                    "Deep resolved inheritance",
                    symbol.qualified_name,
                    "symbol",
                    symbol.symbol_id,
                    symbol.relative_path,
                    symbol.start_line,
                    "resolved_inheritance_depth",
                    depth,
                    policy.inheritance_depth,
                    fixed_severity="medium",
                )
            )
        if (
            symbol.kind in {"class", "function"}
            and symbol.parent_symbol_id is None
            and symbol.visibility == "public"
            and not symbol.docstring_present
        ):
            result.append(
                _finding(
                    repository_id=repository_id,
                    rule_id="undocumented-public-symbol",
                    policy=policy,
                    family="documentation",
                    title="Undocumented public symbol",
                    explanation="A public top-level symbol has no statically visible docstring.",
                    suggested_action="Confirm public intent and document the symbol when useful.",
                    severity="low",
                    confidence="high",
                    subject_type="symbol",
                    subject_keys=(symbol.qualified_name,),
                    affected_node_ids=(symbol.symbol_id,),
                    relative_path=symbol.relative_path,
                    line=symbol.start_line,
                )
            )
        subject_module = module_by_name.get(symbol.module_name)
        if (
            symbol.kind in {"class", "function"}
            and symbol.parent_symbol_id is None
            and symbol.visibility == "public"
            and incoming.get(symbol.symbol_id, 0) == 0
            and symbol.qualified_name not in explicit_exports
            and symbol.display_name not in {"main", "cli"}
            and subject_module is not None
            and subject_module.module_name != "__main__"
            and not _is_test_path(symbol.relative_path)
        ):
            result.append(
                _finding(
                    repository_id=repository_id,
                    rule_id="orphan-looking-candidate",
                    policy=policy,
                    family="orphan-candidate",
                    title="Orphan-looking public symbol candidate",
                    explanation=(
                        "No resolved incoming non-containment relationship was found. Static analysis "
                        "cannot prove that this symbol is unused."
                    ),
                    suggested_action="Review entry points, dynamic use, and public API intent.",
                    severity="low",
                    confidence="low",
                    subject_type="symbol",
                    subject_keys=(symbol.qualified_name,),
                    affected_node_ids=(symbol.symbol_id,),
                    relative_path=symbol.relative_path,
                    line=symbol.start_line,
                )
            )
    return result


def _metric(
    *,
    subject_id: str,
    subject_type: str,
    metric_name: str,
    value: float,
    unit: str,
    relative_path: str | None,
    line: int | None,
) -> MetricRecord:
    payload = {
        "subject_id": subject_id,
        "subject_type": subject_type,
        "metric_name": metric_name,
        "numeric_value": value,
        "unit": unit,
        "analyzer_version": ANALYZER_VERSION,
        "relative_path": relative_path,
        "line": line,
    }
    return MetricRecord(
        metric_id=stable_digest("repository-review-metric", payload),
        subject_id=subject_id,
        subject_type=subject_type,
        metric_name=metric_name,
        numeric_value=value,
        unit=unit,
        analyzer_version=ANALYZER_VERSION,
        relative_path=relative_path,
        line=line,
    )


def _merge_findings(
    findings: Sequence[FindingEvidenceRecord],
) -> list[FindingEvidenceRecord]:
    """Merge duplicate logical identities produced by ambiguous source-root evidence."""

    grouped: dict[str, list[FindingEvidenceRecord]] = defaultdict(list)
    for finding in findings:
        grouped[finding.finding_id].append(finding)
    merged: list[FindingEvidenceRecord] = []
    for finding_id in sorted(grouped):
        group = grouped[finding_id]
        first = min(
            group,
            key=lambda item: (
                item.relative_path or "",
                item.line or 0,
                item.affected_node_ids,
            ),
        )
        paths = {item.relative_path for item in group}
        lines = {item.line for item in group}
        merged.append(
            FindingEvidenceRecord(
                finding_id=first.finding_id,
                rule_id=first.rule_id,
                rule_version=first.rule_version,
                family=first.family,
                title=first.title,
                explanation=first.explanation,
                suggested_action=first.suggested_action,
                severity=first.severity,
                confidence=first.confidence,
                subject_type=first.subject_type,
                subject_keys=first.subject_keys,
                affected_node_ids=tuple(
                    sorted({node_id for item in group for node_id in item.affected_node_ids})
                ),
                relative_path=next(iter(paths)) if len(paths) == 1 else None,
                line=next(iter(lines)) if len(paths) == 1 and len(lines) == 1 else None,
                metric_evidence=tuple(
                    sorted({evidence for item in group for evidence in item.metric_evidence})
                ),
                threshold_evidence=tuple(
                    sorted({evidence for item in group for evidence in item.threshold_evidence})
                ),
            )
        )
    return merged


def _finding(
    *,
    repository_id: str,
    rule_id: str,
    policy: FindingPolicy,
    family: str,
    title: str,
    explanation: str,
    suggested_action: str,
    severity: str,
    confidence: str,
    subject_type: str,
    subject_keys: tuple[str, ...],
    affected_node_ids: tuple[str, ...],
    relative_path: str | None,
    line: int | None,
    metric_evidence: tuple[tuple[str, float], ...] = (),
    threshold_evidence: tuple[tuple[str, float], ...] = (),
) -> FindingEvidenceRecord:
    ordered_keys = tuple(sorted(subject_keys))
    finding_id = stable_digest(
        "repository-review-finding",
        {
            "repository_id": repository_id,
            "rule_id": rule_id,
            "rule_version": policy.rule_version,
            "subject_type": subject_type,
            "subject_keys": ordered_keys,
        },
    )
    return FindingEvidenceRecord(
        finding_id=finding_id,
        rule_id=rule_id,
        rule_version=policy.rule_version,
        family=family,
        title=title,
        explanation=explanation,
        suggested_action=suggested_action,
        severity=severity,
        confidence=confidence,
        subject_type=subject_type,
        subject_keys=ordered_keys,
        affected_node_ids=tuple(sorted(affected_node_ids)),
        relative_path=relative_path,
        line=line,
        metric_evidence=tuple(sorted(metric_evidence)),
        threshold_evidence=tuple(sorted(threshold_evidence)),
    )


def _threshold_finding(
    repository_id: str,
    rule_id: str,
    policy: FindingPolicy,
    family: str,
    title: str,
    qualified_subject: str,
    subject_type: str,
    subject_id: str,
    relative_path: str,
    line: int,
    metric_name: str,
    value: float,
    threshold: int,
    *,
    fixed_severity: str | None = None,
) -> FindingEvidenceRecord:
    severity = fixed_severity or _threshold_severity(value, threshold)
    return _finding(
        repository_id=repository_id,
        rule_id=rule_id,
        policy=policy,
        family=family,
        title=title,
        explanation=(
            f"{metric_name.replace('_', ' ').capitalize()} is {value:g}; "
            f"the experimental threshold is greater than {threshold:g}."
        ),
        suggested_action="Review the measured structure and refactor only when it improves maintainability.",
        severity=severity,
        confidence="high",
        subject_type=subject_type,
        subject_keys=(qualified_subject,),
        affected_node_ids=(subject_id,),
        relative_path=relative_path,
        line=line,
        metric_evidence=((metric_name, value),),
        threshold_evidence=((metric_name, float(threshold)),),
    )


def _threshold_severity(value: float, threshold: int) -> str:
    if value > threshold * 2:
        return "high"
    if value > threshold * 1.5:
        return "medium"
    return "low"


def _nearby_test_modules(
    modules: Sequence[ModuleRecord],
    import_edges: Sequence[RelationshipRecord],
) -> set[str]:
    test_module_ids = {item.module_id for item in modules if _is_test_path(item.relative_path)}
    result: set[str] = set()
    for item in import_edges:
        if item.source_id in test_module_ids and item.target_id is not None:
            result.add(item.target_id)
    return result


def _resolved_non_containment_incoming(
    relationships: Sequence[RelationshipRecord],
) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for relationship in relationships:
        if (
            relationship.relationship_type != "contains"
            and relationship.target_id is not None
            and relationship.resolution_status in RESOLVED_STATUSES
        ):
            counts[relationship.target_id] += 1
    return counts


def _excluded_symbol(symbol: SymbolRecord) -> bool:
    path = PurePosixPath(symbol.relative_path)
    lowered = {part.casefold() for part in path.parts}
    return bool(lowered & {"generated", "vendor", "vendored"}) or symbol.visibility == "private"


def _is_test_path(relative_path: str) -> bool:
    path = PurePosixPath(relative_path)
    name = path.name.casefold()
    parts = {part.casefold() for part in path.parts[:-1]}
    return (
        bool(parts & {"test", "tests"})
        or (name.startswith("test_") and name.endswith(".py"))
        or name.endswith("_test.py")
    )


def _decode_python(content: bytes) -> str:
    encoding, _ = tokenize.detect_encoding(io.BytesIO(content).readline)
    return content.decode(encoding)


def _parameter_count(node: ast.AST) -> int:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return 0
    arguments = node.args
    return (
        len(arguments.posonlyargs)
        + len(arguments.args)
        + len(arguments.kwonlyargs)
        + int(arguments.vararg is not None)
        + int(arguments.kwarg is not None)
    )


class _ScopeVisitor(ast.NodeVisitor):
    def __init__(self, root: ast.AST) -> None:
        self.root = root
        self.complexity = 1
        self.current_nesting = 0
        self.maximum_nesting = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        if node is self.root:
            self._visit_body(node.body)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        if node is self.root:
            self._visit_body(node.body)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        if node is self.root:
            self._visit_body(node.body)

    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        self.complexity += 1
        self._nested(node.body)
        self._nested(node.orelse)
        self.visit(node.test)

    def visit_For(self, node: ast.For) -> None:  # noqa: N802
        self.complexity += 1
        self.visit(node.target)
        self.visit(node.iter)
        self._nested((*node.body, *node.orelse))

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:  # noqa: N802
        self.complexity += 1
        self.visit(node.target)
        self.visit(node.iter)
        self._nested((*node.body, *node.orelse))

    def visit_While(self, node: ast.While) -> None:  # noqa: N802
        self.complexity += 1
        self.visit(node.test)
        self._nested((*node.body, *node.orelse))

    def visit_IfExp(self, node: ast.IfExp) -> None:  # noqa: N802
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:  # noqa: N802
        self.complexity += max(len(node.values) - 1, 0)
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
        self.complexity += len(node.handlers)
        self._nested((*node.body, *node.handlers, *node.orelse, *node.finalbody))

    def visit_TryStar(self, node: ast.TryStar) -> None:  # noqa: N802
        self.complexity += len(node.handlers)
        self._nested((*node.body, *node.handlers, *node.orelse, *node.finalbody))

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:  # noqa: N802
        self._visit_body(node.body)

    def visit_Match(self, node: ast.Match) -> None:  # noqa: N802
        self.visit(node.subject)
        self.complexity += sum(not _default_match_case(item) for item in node.cases)
        self._nested(node.cases)

    def visit_match_case(self, node: ast.match_case) -> None:
        if node.guard is not None:
            self.visit(node.guard)
        self._visit_body(node.body)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.complexity += len(node.ifs)
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:  # noqa: N802
        for item in node.items:
            self.visit(item)
        self._nested(node.body)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:  # noqa: N802
        for item in node.items:
            self.visit(item)
        self._nested(node.body)

    def _nested(self, nodes: Sequence[ast.AST]) -> None:
        if not nodes:
            return
        self.current_nesting += 1
        self.maximum_nesting = max(self.maximum_nesting, self.current_nesting)
        self._visit_body(nodes)
        self.current_nesting -= 1

    def _visit_body(self, nodes: Sequence[ast.AST]) -> None:
        for child in nodes:
            self.visit(child)


def _scope_complexity(root: ast.AST) -> int:
    visitor = _ScopeVisitor(root)
    if isinstance(root, ast.Module):
        visitor._visit_body(root.body)
    else:
        visitor.visit(root)
    return visitor.complexity


def _scope_nesting(root: ast.AST) -> int:
    visitor = _ScopeVisitor(root)
    if isinstance(root, ast.Module):
        visitor._visit_body(root.body)
    else:
        visitor.visit(root)
    return visitor.maximum_nesting


def _default_match_case(case: ast.match_case) -> bool:
    pattern = case.pattern
    return (
        isinstance(pattern, ast.MatchAs)
        and pattern.pattern is None
        and pattern.name is None
        and case.guard is None
    )


def finding_rules(policy: FindingPolicy = DEFAULT_FINDING_POLICY) -> tuple[dict[str, object], ...]:
    """Return the documented immutable experimental rule catalog."""

    definitions = (
        ("dependency-cycle", "dependency-cycle", "Confirmed static dependency cycle"),
        ("inheritance-cycle", "inheritance-cycle", "Confirmed static inheritance cycle"),
        ("exact-duplicate-symbol-name", "duplicate-name-candidate", "Repeated exact names"),
        ("oversized-symbol", "oversized", "Large symbols"),
        ("oversized-module", "oversized", "Large modules"),
        ("high-cyclomatic-complexity", "complexity", "High static complexity"),
        ("high-maximum-nesting", "nesting", "Deep nesting"),
        ("high-parameter-count", "parameters", "Many parameters"),
        ("high-resolved-fan-in", "coupling", "High resolved fan-in"),
        ("high-resolved-fan-out", "coupling", "High resolved fan-out"),
        ("deep-inheritance", "inheritance", "Deep resolved inheritance"),
        ("undocumented-public-symbol", "documentation", "Undocumented public symbols"),
        (
            "complexity-without-nearby-test-evidence",
            "test-evidence-candidate",
            "Complexity without nearby test evidence",
        ),
        ("orphan-looking-candidate", "orphan-candidate", "Orphan-looking candidates"),
    )
    thresholds = dict(policy.public_thresholds())
    return tuple(
        {
            "rule_id": rule_id,
            "rule_version": policy.rule_version,
            "family": family,
            "title": title,
            "experimental": True,
            "thresholds": thresholds,
        }
        for rule_id, family, title in definitions
    )


__all__ = [
    "DEFAULT_FINDING_POLICY",
    "FindingAnalysisResult",
    "FindingAnalyzer",
    "FindingPolicy",
    "finding_rules",
]
