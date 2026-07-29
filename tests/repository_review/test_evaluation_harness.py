from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from scripts.evaluate_repository_review import (
    evaluate_subjects,
    generate_public_fixtures,
    main,
)
from zscripts.domain.repository_review import ScanLimits

_ALLOWED_FINDING_FAMILIES = {
    "complexity",
    "coupling",
    "dependency-cycle",
    "documentation",
    "duplicate-name-candidate",
    "inheritance",
    "inheritance-cycle",
    "nesting",
    "orphan-candidate",
    "oversized",
    "parameters",
    "test-evidence-candidate",
}
_ALLOWED_SAMPLE_CLASSIFICATIONS = {
    "false-positive",
    "intentional-design",
    "unsupported-ambiguous",
    "useful-actionable",
    "valid-low-priority",
}
_REPORT_FAMILY_NAMES = {
    "Complexity": "complexity",
    "Coupling": "coupling",
    "Dependency cycle": "dependency-cycle",
    "Documentation": "documentation",
    "Duplicate name candidate": "duplicate-name-candidate",
    "Inheritance cycle": "inheritance-cycle",
    "Inheritance depth": "inheritance",
    "Nesting": "nesting",
    "Orphan candidate": "orphan-candidate",
    "Oversized": "oversized",
    "Parameters": "parameters",
    "Test-evidence candidate": "test-evidence-candidate",
}


def test_evaluation_is_sanitized_deterministic_and_bounded(tmp_path: Path) -> None:
    repository = tmp_path / "subject"
    repository.mkdir()
    (repository / "sample.py").write_text(
        "class Customer:\n    pass\n\ndef process(value: Customer) -> Customer:\n    return value\n",
        encoding="utf-8",
    )
    output = tmp_path / "external" / "result.json"
    payload = evaluate_subjects(
        (("public-sample", repository),),
        output_path=output,
        data_directory=tmp_path / "data",
        repeats=2,
        limits=ScanLimits(),
    )

    serialized = output.read_text(encoding="utf-8")
    subject = payload["subjects"][0]
    assert str(repository.resolve()) not in serialized
    assert subject["label"] == "public-sample"
    assert subject["persistence"]["repeated_snapshot_identity_equal"] is True
    assert subject["persistence"]["repeated_canonical_bytes_equal"] is True
    assert subject["persistence"]["repository_bytes_unchanged"] is True
    assert subject["relationships"]["largest_bounded_graph"]["nodes"] <= 40
    assert subject["relationships"]["largest_bounded_graph"]["relationships"] <= 80
    assert subject["findings"]["bounded_review_sample_size"] <= 20
    assert subject["comparison"]["equal_snapshots"] is True
    assert subject["handoff"]["saved_reopened_integrity"] is True


def test_evaluation_respects_scan_limits_without_path_leakage(tmp_path: Path) -> None:
    repository = tmp_path / "bounded"
    repository.mkdir()
    for index in range(4):
        (repository / f"module_{index}.py").write_text(
            f"def item_{index}():\n    return {index}\n",
            encoding="utf-8",
        )
    output = tmp_path / "result.json"
    payload = evaluate_subjects(
        (("public-bounded", repository),),
        output_path=output,
        data_directory=tmp_path / "data",
        repeats=2,
        limits=ScanLimits(max_files=1),
    )

    scan = payload["subjects"][0]["scan"]
    assert scan["truncated"] is True
    assert scan["files_analyzed"] == 1
    assert str(repository.resolve()) not in json.dumps(payload)


@pytest.mark.parametrize("destination", ("output", "data"))
def test_evaluation_rejects_repository_internal_writes(
    tmp_path: Path,
    destination: str,
) -> None:
    repository = tmp_path / "subject"
    repository.mkdir()
    (repository / "sample.py").write_text("value = 1\n", encoding="utf-8")
    output = repository / "result.json" if destination == "output" else tmp_path / "result.json"
    data = repository / "data" if destination == "data" else tmp_path / "data"

    with pytest.raises(ValueError, match="outside every analyzed repository"):
        evaluate_subjects(
            (("public-sample", repository),),
            output_path=output,
            data_directory=data,
            repeats=2,
            limits=ScanLimits(),
        )
    assert not output.exists()


def test_public_fixture_generation_is_deterministic(tmp_path: Path) -> None:
    first = generate_public_fixtures(tmp_path / "first")
    second = generate_public_fixtures(tmp_path / "second")

    assert [label for label, _ in first] == [label for label, _ in second]
    assert _fixture_digest(first) == _fixture_digest(second)
    large = dict(first)["public-large"]
    assert (large / ".gitignore").read_text(encoding="utf-8") == "generated/\n"
    assert len(list((large / "generated").glob("*.py"))) == 200


def test_cli_requires_explicit_output_and_uses_anonymous_label(tmp_path: Path) -> None:
    repository = tmp_path / "subject"
    repository.mkdir()
    (repository / "sample.py").write_text("value = 1\n", encoding="utf-8")
    output = tmp_path / "result.json"

    result = main(
        [
            "evaluate",
            "--subject",
            f"public-sample={repository}",
            "--output",
            str(output),
            "--data-directory",
            str(tmp_path / "data"),
        ]
    )

    assert result == 0
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8"))["sanitized"] is True


def test_finding_sample_manifest_is_reproducible_sanitized_and_matches_report() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    manifest_path = repository_root / "docs" / "product" / "REPOSITORY_REVIEW_DOGFOOD_FINDING_SAMPLE.json"
    report_path = repository_root / "docs" / "product" / "REPOSITORY_REVIEW_DOGFOOD_REPORT.md"
    serialized = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(serialized)
    entries = manifest["entries"]

    assert manifest["format_version"] == 1
    assert manifest["evaluated_build_sha"]["algorithm"] == "git-sha1"
    assert "".join(manifest["evaluated_build_sha"]["parts"]) == "".join(
        ("678356bf", "4e237308", "86abaffd", "84186d0c", "5d3627f7")
    )
    assert manifest["evaluated_snapshot_id"]["algorithm"] == "sha256"
    assert "".join(manifest["evaluated_snapshot_id"]["parts"]) == "".join(
        (
            "d283a162",
            "2b361e0f",
            "f4484455",
            "0525b05d",
            "a2e04683",
            "524dd3bb",
            "8d017e2b",
            "116e14d6",
        )
    )
    assert manifest["source_label"] == "zscripts-public"
    assert manifest["selection_policy"]["ordering"] == ["family", "finding_id"]
    assert manifest["selection_policy"]["maximum_per_family"] == 5
    assert set(manifest["allowed_classifications"]) == _ALLOWED_SAMPLE_CLASSIFICATIONS
    assert len(entries) == 50

    ordering = [(entry["family"], entry["selection_rank"]) for entry in entries]
    assert ordering == sorted(ordering)
    assert all(entry["family"] in _ALLOWED_FINDING_FAMILIES for entry in entries)
    assert all(entry["classification"] in _ALLOWED_SAMPLE_CLASSIFICATIONS for entry in entries)
    assert all(re.fullmatch(r"[A-Za-z0-9_.+]+", entry["finding_key"]) for entry in entries)
    assert len({(entry["family"], entry["rule_id"], entry["finding_key"]) for entry in entries}) == len(
        entries
    )
    assert max(Counter(entry["family"] for entry in entries).values()) <= 5
    for family, count in Counter(entry["family"] for entry in entries).items():
        assert [entry["selection_rank"] for entry in entries if entry["family"] == family] == list(
            range(1, count + 1)
        )

    assert re.search(r"(?i)[a-z]:[\\/]", serialized) is None
    assert re.search(r'"/', serialized) is None
    assert "source_excerpt" not in serialized
    assert "relative_path" not in serialized
    for marker in (
        "Nobod",
        "dev-logger-dogfood-worktree",
        "repository-review-dogfood-raw",
        "private-repository",
    ):
        assert marker not in serialized

    report_rows = _finding_review_rows(report_path.read_text(encoding="utf-8"))
    manifest_counts = Counter((entry["family"], entry["classification"]) for entry in entries)
    for family in _ALLOWED_FINDING_FAMILIES:
        report_row = report_rows[family]
        assert report_row["reviewed"] == sum(
            manifest_counts[(family, classification)] for classification in _ALLOWED_SAMPLE_CLASSIFICATIONS
        )
        for classification in _ALLOWED_SAMPLE_CLASSIFICATIONS:
            assert report_row[classification] == manifest_counts[(family, classification)]


def _finding_review_rows(report: str) -> dict[str, dict[str, int]]:
    row_pattern = re.compile(
        r"^\| (?P<label>[^|]+?) \| [\d,]+ \| "
        r"(?P<reviewed>\d+) \| (?P<useful>\d+) \| (?P<low>\d+) \| "
        r"(?P<intentional>\d+) \| (?P<false_positive>\d+) \| "
        r"(?P<unsupported>\d+) \|",
        re.MULTILINE,
    )
    rows: dict[str, dict[str, int]] = {}
    for match in row_pattern.finditer(report):
        label = match.group("label")
        if label not in _REPORT_FAMILY_NAMES:
            continue
        rows[_REPORT_FAMILY_NAMES[label]] = {
            "reviewed": int(match.group("reviewed")),
            "useful-actionable": int(match.group("useful")),
            "valid-low-priority": int(match.group("low")),
            "intentional-design": int(match.group("intentional")),
            "false-positive": int(match.group("false_positive")),
            "unsupported-ambiguous": int(match.group("unsupported")),
        }
    assert set(rows) == _ALLOWED_FINDING_FAMILIES
    return rows


def _fixture_digest(subjects: tuple[tuple[str, Path], ...]) -> str:
    digest = hashlib.sha256()
    for label, root in subjects:
        digest.update(label.encode())
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()
