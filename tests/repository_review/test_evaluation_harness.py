from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.evaluate_repository_review import (
    evaluate_subjects,
    generate_public_fixtures,
    main,
)
from zscripts.domain.repository_review import ScanLimits


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


def _fixture_digest(subjects: tuple[tuple[str, Path], ...]) -> str:
    digest = hashlib.sha256()
    for label, root in subjects:
        digest.update(label.encode())
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()
