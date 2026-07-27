from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from zscripts.application.repository_review import RepositoryReviewService
from zscripts.infrastructure.finding_analysis import FindingAnalyzer
from zscripts.infrastructure.repository_discovery import AnalysisCancelled
from zscripts.infrastructure.snapshot_store import ReviewConflictError, SnapshotStore

FIXTURES = Path(__file__).parents[1] / "fixtures" / "repository_review"


def test_exact_metrics_rules_and_stable_canonical_evidence(tmp_path: Path) -> None:
    repository = tmp_path / "findings"
    shutil.copytree(FIXTURES / "findings", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")

    first = service.analyze(repository)
    second = service.analyze(repository)
    symbols = {item.symbol_id: item for item in first.symbols}
    metrics = {
        (symbols[item.subject_id].qualified_name, item.metric_name): item.numeric_value
        for item in first.metrics
        if item.subject_id in symbols
    }

    assert metrics[("pkg.metrics.complex_target", "cyclomatic_complexity")] == 9
    assert metrics[("pkg.metrics.complex_target", "parameter_count")] == 9
    assert metrics[("pkg.metrics.complex_target", "nearby_test_evidence")] == 1
    assert metrics[("pkg.metrics.deeply_nested", "maximum_nesting")] == 6
    assert metrics[("pkg.inheritance.LevelSix", "resolved_inheritance_depth")] == 6
    assert first.snapshot.snapshot_id == second.snapshot.snapshot_id
    assert first.canonical_bytes() == second.canonical_bytes()
    assert str(repository.resolve()).encode() not in first.canonical_bytes()

    families = {item.family for item in first.findings}
    assert {
        "dependency-cycle",
        "duplicate-name-candidate",
        "nesting",
        "parameters",
        "inheritance",
        "documentation",
        "orphan-candidate",
    } <= families
    assert all("dead code" not in item.explanation.casefold() for item in first.findings)
    assert not any(
        item.family == "test-evidence-candidate" and item.subject_keys == ("pkg.metrics.complex_target",)
        for item in first.findings
    )


def test_nested_scope_complexity_is_not_charged_to_enclosing_symbol(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "sample.py").write_text(
        """
def outer():
    def inner(value):
        if value:
            if value > 1:
                return value
        return 0
    return inner
""".lstrip(),
        encoding="utf-8",
    )
    evidence = RepositoryReviewService(data_directory=tmp_path / "data").analyze(repository)
    symbols = {item.symbol_id: item for item in evidence.symbols}
    complexity = {
        symbols[item.subject_id].qualified_name: item.numeric_value
        for item in evidence.metrics
        if item.subject_id in symbols and item.metric_name == "cyclomatic_complexity"
    }

    assert complexity["sample.outer"] == 1
    assert complexity["sample.outer.inner"] == 3


def test_lifecycle_resolution_reactivation_and_review_history(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    source = repository / "sample.py"
    original = "def public_item():\n    return 1\n"
    source.write_text(original, encoding="utf-8")
    service = RepositoryReviewService(data_directory=tmp_path / "data")

    first = service.analyze(repository)
    finding = next(
        item
        for item in first.findings
        if item.rule_id == "undocumented-public-symbol" and item.subject_keys == ("sample.public_item",)
    )
    reviewed = service.update_finding_review(
        finding.finding_id,
        expected_version=0,
        review_status="accepted",
        note='<script>alert("local")</script>',
        reason_code="intentional-design",
    )
    assert reviewed["review_version"] == 1

    source.write_text(
        'def public_item():\n    """Documented now."""\n    return 1\n',
        encoding="utf-8",
    )
    second = service.analyze(repository)
    resolved = service.finding_detail(finding.finding_id)
    assert resolved["evidence_state"] == "resolved"
    assert resolved["effective_status"] == "resolved"
    assert resolved["review_status"] == "accepted"
    assert resolved["note"] == '<script>alert("local")</script>'
    assert resolved["resolved_snapshot_id"] == second.snapshot.snapshot_id
    assert (
        service.finding_detail(finding.finding_id, second.snapshot.snapshot_id)["finding_id"]
        == finding.finding_id
    )

    source.write_text(original, encoding="utf-8")
    third = service.analyze(repository)
    reactivated = service.finding_detail(finding.finding_id)
    assert reactivated["last_seen_snapshot_id"] == third.snapshot.snapshot_id
    assert reactivated["evidence_state"] == "active"
    assert reactivated["effective_status"] == "accepted"
    history = service.finding_history(finding.finding_id, page_size=20)["items"]
    assert [item["event_type"] for item in history] == [
        "finding-reactivated",
        "finding-resolved",
        "review-decision-changed",
        "finding-first-seen",
    ]


def test_failed_scan_and_review_write_failure_preserve_existing_state(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "sample.py").write_text("def public_item():\n    return 1\n", encoding="utf-8")
    store = SnapshotStore(tmp_path / "data")
    service = RepositoryReviewService(store=store)
    evidence = service.analyze(repository)
    finding = next(item for item in evidence.findings if item.rule_id == "undocumented-public-symbol")

    class FailingFindingAnalyzer(FindingAnalyzer):
        def analyze(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
            raise RuntimeError("simulated finding failure")

    failing_service = RepositoryReviewService(
        store=store,
        finding_analyzer=FailingFindingAnalyzer(),
    )
    with pytest.raises(RuntimeError, match="finding failure"):
        failing_service.analyze(repository)
    assert service.finding_detail(finding.finding_id)["evidence_state"] == "active"

    with sqlite3.connect(store.database_path) as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_review_event
            BEFORE INSERT ON finding_review_events
            WHEN NEW.event_type = 'review-decision-changed'
            BEGIN
                SELECT RAISE(ABORT, 'simulated review failure');
            END
            """
        )
    with pytest.raises(sqlite3.IntegrityError, match="review failure"):
        service.update_finding_review(
            finding.finding_id,
            expected_version=0,
            review_status="reviewed",
            note="should roll back",
            reason_code="other",
        )
    current = service.finding_detail(finding.finding_id)
    assert current["review_version"] == 0
    assert current["review_status"] == "new"
    assert current["note"] == ""


def test_review_conflict_and_note_limit_are_enforced(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "sample.py").write_text("def public_item():\n    return 1\n", encoding="utf-8")
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    finding = next(item for item in evidence.findings if item.rule_id == "undocumented-public-symbol")

    service.update_finding_review(
        finding.finding_id,
        expected_version=0,
        review_status="reviewed",
        note="first",
        reason_code="needs-investigation",
    )
    with pytest.raises(ReviewConflictError) as conflict:
        service.store.update_finding_review(
            finding.finding_id,
            expected_version=0,
            review_status="dismissed",
            note="stale",
            reason_code="false-positive",
            updated_at="2026-01-01T00:00:00.000Z",
        )
    assert conflict.value.current.review.version == 1
    with pytest.raises(ValueError, match="2,000"):
        service.update_finding_review(
            finding.finding_id,
            expected_version=1,
            review_status="reviewed",
            note="x" * 2_001,
            reason_code="other",
        )


def test_cancelled_scan_does_not_resolve_existing_findings(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    source = repository / "sample.py"
    source.write_text("def public_item():\n    return 1\n", encoding="utf-8")
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    evidence = service.analyze(repository)
    finding = next(item for item in evidence.findings if item.rule_id == "undocumented-public-symbol")
    source.write_text(
        'def public_item():\n    """Now documented."""\n    return 1\n',
        encoding="utf-8",
    )

    with pytest.raises(AnalysisCancelled):
        service.analyze(repository, cancelled=lambda: True)

    assert service.finding_detail(finding.finding_id)["evidence_state"] == "active"


def test_ambiguous_relationships_do_not_contribute_to_resolved_fan_metrics(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "relationships"
    shutil.copytree(FIXTURES / "relationships", repository)
    evidence = RepositoryReviewService(data_directory=tmp_path / "data").analyze(repository)
    resolved_imports = [
        item
        for item in evidence.relationships
        if item.relationship_type == "imports"
        and item.resolution_status in {"resolved-static", "probable-static"}
    ]
    ambiguous_imports = [
        item
        for item in evidence.relationships
        if item.relationship_type == "imports" and item.resolution_status == "ambiguous"
    ]
    fan_out_total = sum(
        item.numeric_value
        for item in evidence.metrics
        if item.subject_type == "module" and item.metric_name == "resolved_fan_out"
    )

    assert ambiguous_imports
    assert fan_out_total == len(resolved_imports)
