from __future__ import annotations

import json
import time
from pathlib import Path

from zscripts.application.repository_review import RepositoryReviewService
from zscripts.domain.repository_review import GraphNodeRecord, RelationshipRecord
from zscripts.infrastructure.relationship_analysis import (
    bounded_neighborhood,
    strongly_connected_components,
)


def test_medium_public_fixture_relationship_performance(tmp_path: Path) -> None:
    repository = tmp_path / "medium-public-fixture"
    _write_medium_repository(repository, modules=30, symbols_per_module=12)
    service = RepositoryReviewService(data_directory=tmp_path / "data")

    started = time.perf_counter()
    evidence = service.analyze(repository)
    analysis_seconds = time.perf_counter() - started
    focus = next(
        node.node_id
        for node in evidence.graph_nodes
        if node.node_type == "module" and node.qualified_name == "fixture.module_000"
    )
    query_started = time.perf_counter()
    neighborhood = service.relationship_neighborhood(
        evidence.snapshot.snapshot_id,
        focus_id=focus,
        mode="modules",
        depth=3,
        max_nodes=40,
        max_edges=80,
    )
    query_seconds = time.perf_counter() - query_started
    payload_size = len(json.dumps(neighborhood, separators=(",", ":")).encode())

    assert evidence.snapshot.symbol_count == 360
    assert len(evidence.relationships) >= 389
    assert analysis_seconds < 15
    assert query_seconds < 1
    assert payload_size < 1_000_000
    assert len(neighborhood["nodes"]) <= 40
    assert len(neighborhood["relationships"]) <= 80


def test_bounded_large_synthetic_graph_performance() -> None:
    nodes, relationships = _large_synthetic_graph(node_count=1_000, edge_count=2_500)

    scc_started = time.perf_counter()
    components = strongly_connected_components(
        (node.node_id for node in nodes),
        relationships,
    )
    scc_seconds = time.perf_counter() - scc_started
    query_started = time.perf_counter()
    neighborhood = bounded_neighborhood(
        nodes,
        relationships,
        focus_id="node-0000",
        depth=3,
        max_nodes=40,
        max_edges=80,
    )
    query_seconds = time.perf_counter() - query_started

    assert components
    assert scc_seconds < 2
    assert query_seconds < 1
    assert len(neighborhood.nodes) <= 40
    assert len(neighborhood.relationships) <= 80
    assert neighborhood.truncated is True


def _write_medium_repository(
    root: Path,
    *,
    modules: int,
    symbols_per_module: int,
) -> None:
    """Create deterministic public Python syntax without executing fixture code."""

    package = root / "fixture"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Medium relationship fixture."""\n', encoding="utf-8")
    for module_index in range(modules):
        previous = (module_index - 1) % modules
        lines = [
            f"from . import module_{previous:03d}\n",
            "\n",
        ]
        for symbol_index in range(symbols_per_module):
            lines.extend(
                (
                    f"class Type{symbol_index:02d}:\n",
                    f"    peer: 'module_{previous:03d}.Type{symbol_index:02d}'\n",
                    "    pass\n",
                    "\n",
                )
            )
        (package / f"module_{module_index:03d}.py").write_text(
            "".join(lines),
            encoding="utf-8",
        )


def _large_synthetic_graph(
    *,
    node_count: int,
    edge_count: int,
) -> tuple[tuple[GraphNodeRecord, ...], tuple[RelationshipRecord, ...]]:
    """Return a deterministic, dependency-free large graph fixture."""

    nodes = tuple(
        GraphNodeRecord(
            node_id=f"node-{index:04d}",
            node_type="module",
            display_name=f"module_{index:04d}",
            qualified_name=f"fixture.module_{index:04d}",
            relative_path=f"fixture/module_{index:04d}.py",
            symbol_kind=None,
        )
        for index in range(node_count)
    )
    relationships = tuple(
        RelationshipRecord(
            relationship_id=f"edge-{index:05d}",
            relationship_type="imports",
            source_id=f"node-{index % node_count:04d}",
            target_id=(f"node-{(index * 37 + index // node_count + 1) % node_count:04d}"),
            unresolved_target=None,
            resolution_status="resolved-static",
            confidence="high",
            relative_path=f"fixture/module_{index % node_count:04d}.py",
            line=1,
            column=0,
            analyzer_version="2",
            evidence="synthetic import edge",
        )
        for index in range(edge_count)
    )
    return nodes, relationships
