from __future__ import annotations

import shutil
from pathlib import Path

from zscripts.application.repository_review import RepositoryReviewService
from zscripts.domain.repository_review import AnalysisEvidence, GraphNodeRecord, RelationshipRecord
from zscripts.infrastructure.relationship_analysis import (
    bounded_neighborhood,
    graph_metrics,
    strongly_connected_components,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "repository_review"


def test_relationship_resolution_is_stable_and_source_positioned(tmp_path: Path) -> None:
    repository = tmp_path / "relationships"
    shutil.copytree(FIXTURES / "relationships", repository)
    first_service = RepositoryReviewService(data_directory=tmp_path / "data-first")
    second_service = RepositoryReviewService(data_directory=tmp_path / "data-second")

    first = first_service.analyze(repository)
    second = second_service.analyze(repository)

    assert first.snapshot.snapshot_id == second.snapshot.snapshot_id
    assert first.canonical_bytes() == second.canonical_bytes()
    assert [item.relationship_id for item in first.relationships] == [
        item.relationship_id for item in second.relationships
    ]
    assert all(item.line >= 1 and item.column >= 0 for item in first.relationships)
    assert all(Path(item.relative_path).is_absolute() is False for item in first.relationships)
    assert str(repository.resolve()).encode() not in first.canonical_bytes()


def test_import_containment_and_inheritance_resolution(tmp_path: Path) -> None:
    evidence = _analyze_relationship_fixture(tmp_path)
    node_names = {item.node_id: item.qualified_name for item in evidence.graph_nodes}

    cycle_edges = {
        (node_names[item.source_id], node_names[item.target_id])
        for item in evidence.relationships
        if item.relationship_type == "imports"
        and item.target_id is not None
        and "cycle_" in node_names[item.source_id]
    }
    assert cycle_edges == {
        ("app.cycle_a", "app.cycle_b"),
        ("app.cycle_b", "app.cycle_a"),
    }
    assert any(
        item.relationship_type == "imports"
        and item.resolution_status == "ambiguous"
        and item.unresolved_target == "import pkg.shared"
        for item in evidence.relationships
    )
    assert any(
        item.relationship_type == "imports"
        and item.evidence == "from app import models"
        and item.target_id is not None
        and node_names[item.target_id] == "app.models"
        for item in evidence.relationships
    )

    containment = {
        (node_names[item.source_id], node_names[item.target_id])
        for item in evidence.relationships
        if item.relationship_type == "contains" and item.target_id is not None
    }
    assert ("app", "app.models") in containment
    assert ("app.models", "app.models.Customer") in containment
    assert (
        "app.services.CustomerService",
        "app.services.CustomerService.build",
    ) in containment

    inheritance = [item for item in evidence.relationships if item.relationship_type == "inherits"]
    symbols_by_id = {item.symbol_id: item for item in evidence.symbols}
    assert all(item.line == symbols_by_id[item.source_id].start_line for item in inheritance)
    assert all(item.column == symbols_by_id[item.source_id].start_column for item in inheritance)
    resolved_inheritance = {
        (node_names[item.source_id], node_names[item.target_id])
        for item in inheritance
        if item.target_id is not None
    }
    assert ("app.models.Customer", "app.models.Entity") in resolved_inheritance
    assert ("app.services.ImportedCustomer", "app.models.Customer") in resolved_inheritance
    assert ("app.models.Combined", "app.models.Customer") in resolved_inheritance
    assert ("app.models.Combined", "app.models.Order") in resolved_inheritance
    assert any(
        item.unresolved_target == "ExternalBase" and item.resolution_status == "unresolved-dynamic"
        for item in inheritance
    )


def test_bounded_type_references_are_conservative(tmp_path: Path) -> None:
    evidence = _analyze_relationship_fixture(tmp_path)
    node_names = {item.node_id: item.qualified_name for item in evidence.graph_nodes}
    references = [item for item in evidence.relationships if item.relationship_type == "references-type"]

    assert any(
        item.target_id is not None
        and node_names[item.source_id] == "app.models.Order"
        and node_names[item.target_id] == "app.models.Customer"
        for item in references
    )
    assert any(
        item.target_id is not None
        and node_names[item.source_id] == "app.models.Customer"
        and node_names[item.target_id] == "app.models.Customer"
        and "Customer | None" in item.evidence
        for item in references
    )
    assert any(
        item.target_id is not None
        and node_names[item.source_id] == "app.services.CustomerService.build"
        and node_names[item.target_id] == "app.models.Customer"
        for item in references
    )
    assert any(
        item.target_id is None
        and item.unresolved_target == "ExternalRecord"
        and item.resolution_status == "unresolved-dynamic"
        for item in references
    )


def test_scc_metrics_and_cycle_safe_inheritance_are_deterministic() -> None:
    nodes = tuple(_node(name) for name in ("a", "b", "c", "d", "e", "self"))
    edges = (
        _edge("a", "b"),
        _edge("b", "a"),
        _edge("b", "c"),
        _edge("c", "d"),
        _edge("d", "c"),
        _edge("self", "self"),
    )

    first = strongly_connected_components((item.node_id for item in nodes), edges)
    second = strongly_connected_components(reversed([item.node_id for item in nodes]), edges[::-1])

    assert first == second
    assert ("a", "b") in first
    assert ("c", "d") in first
    assert ("e",) in first
    assert ("self",) in first

    inheritance_edges = (
        _edge("a", "b", relationship_type="inherits"),
        _edge("b", "c", relationship_type="inherits"),
        _edge("c", "a", relationship_type="inherits"),
        _edge("d", "e", relationship_type="inherits"),
    )
    metrics = graph_metrics(nodes, (*edges, *inheritance_edges))
    assert dict(metrics.fan_in)["a"] >= 1
    assert dict(metrics.fan_out)["b"] >= 1
    assert dict(metrics.inheritance_depth)["a"] is None
    assert dict(metrics.inheritance_depth)["d"] == 1


def test_bounded_neighborhood_enforces_depth_node_and_edge_limits() -> None:
    nodes = tuple(_node(name) for name in ("a", "b", "c", "d", "e"))
    edges = (
        _edge("a", "b"),
        _edge("a", "c"),
        _edge("b", "d"),
        _edge("c", "e"),
    )

    depth_one = bounded_neighborhood(
        nodes,
        edges,
        focus_id="a",
        depth=1,
        max_nodes=10,
        max_edges=10,
    )
    assert {item.node_id for item in depth_one.nodes} == {"a", "b", "c"}
    assert dict(depth_one.distances) == {"a": 0, "b": 1, "c": 1}
    assert depth_one.truncated is False

    truncated = bounded_neighborhood(
        nodes,
        edges,
        focus_id="a",
        depth=3,
        max_nodes=2,
        max_edges=1,
    )
    assert len(truncated.nodes) == 2
    assert len(truncated.relationships) <= 1
    assert truncated.truncated is True


def _analyze_relationship_fixture(tmp_path: Path) -> AnalysisEvidence:
    repository = tmp_path / "relationships"
    shutil.copytree(FIXTURES / "relationships", repository)
    return RepositoryReviewService(data_directory=tmp_path / "data").analyze(repository)


def _node(node_id: str) -> GraphNodeRecord:
    return GraphNodeRecord(
        node_id=node_id,
        node_type="module",
        display_name=node_id,
        qualified_name=node_id,
        relative_path=f"{node_id}.py",
        symbol_kind=None,
    )


def _edge(
    source_id: str,
    target_id: str,
    *,
    relationship_type: str = "imports",
) -> RelationshipRecord:
    return RelationshipRecord(
        relationship_id=f"{relationship_type}:{source_id}:{target_id}",
        relationship_type=relationship_type,
        source_id=source_id,
        target_id=target_id,
        unresolved_target=None,
        resolution_status="resolved-static",
        confidence="high",
        relative_path=f"{source_id}.py",
        line=1,
        column=0,
        analyzer_version="2",
        evidence=f"{source_id} -> {target_id}",
    )
