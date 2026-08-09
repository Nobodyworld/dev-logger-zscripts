from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict
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
_ALLOWED_SAMPLE_SUBJECT_TYPES = {"cycle", "module", "symbol", "symbol-group"}
_REPORT_FAMILY_NAMES = {
    "Complexity": "complexity",
    "Coupling": "coupling",
    "Dependency cycle": "dependency-cycle",
    "Documentation": "documentation",
    "Duplicate name candidate": "duplicate-name-candidate",
    "Duplicate-name candidate": "duplicate-name-candidate",
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
    entries = _assert_finding_sample_manifest_contract(
        serialized,
        manifest,
        expected_build_sha="".join(("678356bf", "4e237308", "86abaffd", "84186d0c", "5d3627f7")),
        expected_snapshot_id="".join(
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
        ),
    )
    report_rows = _historical_finding_review_rows(report_path.read_text(encoding="utf-8"))
    _assert_manifest_matches_report(entries, report_rows)


def test_post_polish_finding_sample_manifest_is_reproducible_sanitized_and_matches_report() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    manifest_path = repository_root / "docs" / "product" / "REPOSITORY_REVIEW_POST_POLISH_FINDING_SAMPLE.json"
    report_path = repository_root / "docs" / "product" / "REPOSITORY_REVIEW_DOGFOOD_REPORT.md"
    serialized = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(serialized)
    entries = _assert_finding_sample_manifest_contract(
        serialized,
        manifest,
        expected_build_sha="".join(("741a86c4", "a62fceb9", "e6e4c285", "84ffebfa", "32080d9d")),
        expected_snapshot_id="".join(
            (
                "74f193c8",
                "3f921f1c",
                "45040382",
                "e70afb91",
                "1d938962",
                "e33df665",
                "cbc32db8",
                "0d230735",
            )
        ),
    )

    compatibility = manifest["historical_sample_compatibility"]
    assert compatibility == {
        "historical_entries": 50,
        "historical_logical_keys_still_present": 47,
        "exact_current_selection_overlap": 17,
        "current_entries": 50,
        "compatible_for_exact_parity": False,
    }
    assert 0 <= compatibility["historical_logical_keys_still_present"] <= compatibility["historical_entries"]
    assert (
        0
        <= compatibility["exact_current_selection_overlap"]
        <= min(
            compatibility["historical_logical_keys_still_present"],
            compatibility["current_entries"],
        )
    )

    expected_totals = {
        "useful-actionable": 22,
        "valid-low-priority": 11,
        "intentional-design": 8,
        "false-positive": 0,
        "unsupported-ambiguous": 9,
    }
    classification_counts = Counter(entry["classification"] for entry in entries)
    assert {
        classification: classification_counts[classification]
        for classification in _ALLOWED_SAMPLE_CLASSIFICATIONS
    } == expected_totals

    report = report_path.read_text(encoding="utf-8")
    assert report.index("### Finding families and high-signal queue") < report.index(
        "## Finding-Family Review"
    )
    report_rows = _post_polish_finding_review_rows(report)
    _assert_manifest_matches_report(entries, report_rows)

    post_polish_section = _report_section(
        report,
        "### Finding families and high-signal queue",
        "### #100 — Exact Handoff JSON budget",
    )
    normalized_section = " ".join(post_polish_section.split())
    assert (
        "The post-polish deterministic sample contains 50 entries: 22 useful or actionable, "
        "11 valid low priority, 8 intentional design, zero false positives, and 9 unsupported "
        "or ambiguous."
    ) in normalized_section


def _assert_finding_sample_manifest_contract(
    serialized: str,
    manifest: dict[str, object],
    *,
    expected_build_sha: str,
    expected_snapshot_id: str,
) -> list[dict[str, object]]:
    assert manifest["format_version"] == 1
    build_sha = manifest["evaluated_build_sha"]
    assert isinstance(build_sha, dict)
    assert build_sha["algorithm"] == "git-sha1"
    assert all(re.fullmatch(r"[0-9a-f]{8}", part) for part in build_sha["parts"])
    assert "".join(build_sha["parts"]) == expected_build_sha

    snapshot_id = manifest["evaluated_snapshot_id"]
    assert isinstance(snapshot_id, dict)
    assert snapshot_id["algorithm"] == "sha256"
    assert all(re.fullmatch(r"[0-9a-f]{8}", part) for part in snapshot_id["parts"])
    assert "".join(snapshot_id["parts"]) == expected_snapshot_id
    assert len(expected_snapshot_id) == 64

    assert manifest["source_label"] == "zscripts-public"
    assert manifest["scan_limits"] == asdict(ScanLimits())
    selection_policy = manifest["selection_policy"]
    assert isinstance(selection_policy, dict)
    assert selection_policy == {
        "ordering": ["family", "finding_id"],
        "manifest_identifier": "stable public logical finding key",
        "maximum_per_family": 5,
        "rule": (
            "Select the first five stable finding IDs in each family, or every finding when "
            "the family contains fewer than five."
        ),
    }
    assert set(manifest["allowed_classifications"]) == _ALLOWED_SAMPLE_CLASSIFICATIONS

    entries = manifest["entries"]
    assert isinstance(entries, list)
    assert len(entries) == 50
    assert all(
        set(entry)
        == {
            "family",
            "selection_rank",
            "finding_key",
            "rule_id",
            "subject_type",
            "classification",
            "rationale_code",
        }
        for entry in entries
    )
    ordering = [(entry["family"], entry["selection_rank"]) for entry in entries]
    assert ordering == sorted(ordering)
    assert all(entry["family"] in _ALLOWED_FINDING_FAMILIES for entry in entries)
    assert all(entry["subject_type"] in _ALLOWED_SAMPLE_SUBJECT_TYPES for entry in entries)
    assert all(entry["classification"] in _ALLOWED_SAMPLE_CLASSIFICATIONS for entry in entries)
    assert all(re.fullmatch(r"[A-Za-z0-9_.+]+", entry["finding_key"]) for entry in entries)
    assert all(re.fullmatch(r"[a-z0-9-]+", entry["rationale_code"]) for entry in entries)
    assert len({(entry["family"], entry["rule_id"], entry["finding_key"]) for entry in entries}) == len(
        entries
    )
    family_counts = Counter(entry["family"] for entry in entries)
    assert max(family_counts.values()) <= 5
    for family, count in family_counts.items():
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
    return entries


def _assert_manifest_matches_report(
    entries: list[dict[str, object]],
    report_rows: dict[str, dict[str, int]],
) -> None:
    manifest_counts = Counter((entry["family"], entry["classification"]) for entry in entries)
    for family in _ALLOWED_FINDING_FAMILIES:
        report_row = report_rows[family]
        assert report_row["reviewed"] == sum(
            manifest_counts[(family, classification)] for classification in _ALLOWED_SAMPLE_CLASSIFICATIONS
        )
        for classification in _ALLOWED_SAMPLE_CLASSIFICATIONS:
            assert report_row[classification] == manifest_counts[(family, classification)]


def _historical_finding_review_rows(report: str) -> dict[str, dict[str, int]]:
    section = _report_section(report, "## Finding-Family Review", "## Performance")
    row_pattern = re.compile(
        r"^\| (?P<label>[^|]+?) \| [\d,]+ \| "
        r"(?P<reviewed>\d+) \| (?P<useful>\d+) \| (?P<low>\d+) \| "
        r"(?P<intentional>\d+) \| (?P<false_positive>\d+) \| "
        r"(?P<unsupported>\d+) \|",
        re.MULTILINE,
    )
    rows: dict[str, dict[str, int]] = {}
    for match in row_pattern.finditer(section):
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


def _post_polish_finding_review_rows(report: str) -> dict[str, dict[str, int]]:
    section = _report_section(
        report,
        "### Finding families and high-signal queue",
        "### #100 — Exact Handoff JSON budget",
    )
    assert "Before observed" in section
    assert "Current sample" in section
    row_pattern = re.compile(
        r"^\| (?P<label>[^|]+?) \| [\d,]+ \| [\d,]+ \| "
        r"(?P<reviewed>\d+) \| (?P<useful>\d+) \| (?P<low>\d+) \| "
        r"(?P<intentional>\d+) \| (?P<false_positive>\d+) \| "
        r"(?P<unsupported>\d+) \|",
        re.MULTILINE,
    )
    rows: dict[str, dict[str, int]] = {}
    for match in row_pattern.finditer(section):
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


def _report_section(report: str, start_heading: str, end_heading: str) -> str:
    start = report.index(start_heading)
    end = report.index(end_heading, start + len(start_heading))
    return report[start:end]


def _fixture_digest(subjects: tuple[tuple[str, Path], ...]) -> str:
    digest = hashlib.sha256()
    for label, root in subjects:
        digest.update(label.encode())
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()
