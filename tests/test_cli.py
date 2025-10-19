from __future__ import annotations

import random
import string
from pathlib import Path

import pytest

from zscripts.cli import (
    COLLECT_TYPE_EXTENSIONS,
    SINGLE_TYPE_EXTENSIONS,
    UnknownTypeError,
    _parse_type_list,
)
from zscripts.cli import (
    main as cli_main,
)
from zscripts.config import get_config

# TODO - Add CLI regression tests for misconfigured projects and I/O failures.


def test_cli_collect_writes_logs(sample_project_path: Path, tmp_path: Path) -> None:
    config = get_config()
    log_dir_name = config.collection_logs.get("python", "logs_apps_pyth")
    output_dir = tmp_path / "logs"

    exit_code = cli_main(
        [
            "collect",
            "--types",
            "python",
            "--project-root",
            str(sample_project_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    python_log_dir = output_dir / log_dir_name
    assert python_log_dir.exists()
    assert any(python_log_dir.iterdir())


def test_cli_consolidate_writes_file(sample_project_path: Path, tmp_path: Path) -> None:
    output = tmp_path / "python.txt"

    exit_code = cli_main(
        [
            "consolidate",
            "--types",
            "python",
            "--project-root",
            str(sample_project_path),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert output.exists()
    assert "backend" in output.read_text(encoding="utf-8")


def test_cli_consolidate_includes_js_variants(sample_project_path: Path, tmp_path: Path) -> None:
    output = tmp_path / "javascript.txt"

    exit_code = cli_main(
        [
            "consolidate",
            "--types",
            "js",
            "--project-root",
            str(sample_project_path),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    content = output.read_text(encoding="utf-8")
    assert "App.js" in content
    assert "App.jsx" in content
    assert "App.mjs" in content
    assert "App.cjs" in content
    assert "App.ts" in content
    assert "App.tsx" in content
    assert "App.mts" in content
    assert "App.cts" in content


def test_cli_tree_respects_include_contents(sample_project_path: Path, tmp_path: Path) -> None:
    tree_path = tmp_path / "tree.txt"

    exit_code = cli_main(
        [
            "tree",
            "--project-root",
            str(sample_project_path),
            "--output",
            str(tree_path),
            "--include-contents",
        ]
    )

    assert exit_code == 0
    content = tree_path.read_text(encoding="utf-8")
    assert "backend" in content
    assert "service.py" in content


def test_cli_collect_dry_run_skips_writes(
    sample_project_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_dir = tmp_path / "preview"

    exit_code = cli_main(
        [
            "collect",
            "--types",
            "python",
            "--project-root",
            str(sample_project_path),
            "--output-dir",
            str(output_dir),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert not output_dir.exists()
    assert "Dry run enabled" in captured.out
    assert "backend/service.py" in captured.out


def test_cli_consolidate_dry_run_lists_files(
    sample_project_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "python.txt"

    exit_code = cli_main(
        [
            "consolidate",
            "--types",
            "python",
            "--project-root",
            str(sample_project_path),
            "--output",
            str(output),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert not output.exists()
    assert "would consolidate" in captured.out
    assert "backend/service.py" in captured.out


def test_cli_consolidate_streams_to_stdout(
    sample_project_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli_main(
        [
            "consolidate",
            "--types",
            "python",
            "--project-root",
            str(sample_project_path),
            "--output",
            "-",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "# backend/service.py" in captured.out
    assert "✓ Consolidated python sources to stdout" in captured.err


def test_cli_tree_dry_run_prints_preview(
    sample_project_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tree_path = tmp_path / "tree.txt"

    exit_code = cli_main(
        [
            "tree",
            "--project-root",
            str(sample_project_path),
            "--output",
            str(tree_path),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert not tree_path.exists()
    assert "Dry run: would write project tree" in captured.out
    assert sample_project_path.resolve().as_posix() in captured.out


def test_cli_tree_streams_stdout_and_limits_bytes(
    sample_project_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli_main(
        [
            "tree",
            "--project-root",
            str(sample_project_path),
            "--output",
            "-",
            "--include-contents",
            "--max-bytes",
            "10",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "│   \"\"\"Service" in captured.out
    assert "✓ Wrote project tree to stdout" in captured.err


def test_cli_rejects_unknown_type(
    sample_project_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = cli_main(
        [
            "collect",
            "--types",
            "python,unknown",
            "--project-root",
            str(sample_project_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Unsupported type" in captured.err


def test_cli_requires_existing_project_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_root = tmp_path / "does-not-exist"
    exit_code = cli_main(
        [
            "collect",
            "--project-root",
            str(missing_root),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Project root does not exist" in captured.err


def test_parse_type_list_whitespace_normalises_fuzz() -> None:
    rng = random.Random(0)
    for _ in range(50):
        count = rng.randint(0, 6)
        segments: list[str] = []
        for _ in range(count):
            token = rng.choice(list(COLLECT_TYPE_EXTENSIONS.keys()))
            left = " " * rng.randint(0, 2)
            right = " " * rng.randint(0, 2)
            casing = token.upper() if rng.random() < 0.5 else token
            segments.append(f"{left}{casing}{right}")
        raw = ",".join(segments)
        expected: list[str] = []
        for segment in raw.split(","):
            stripped = segment.strip()
            if not stripped:
                continue
            lowered = stripped.lower()
            if lowered not in expected:
                expected.append(lowered)

        assert _parse_type_list(raw, allowed=COLLECT_TYPE_EXTENSIONS) == tuple(expected)


def test_parse_type_list_rejects_invalid_values_fuzz() -> None:
    rng = random.Random(1)
    alphabet = string.ascii_lowercase
    for _ in range(100):
        token = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 6)))
        if token in COLLECT_TYPE_EXTENSIONS:
            continue
        raw_value = token if rng.random() < 0.5 else f"{token},{token}"
        with pytest.raises(UnknownTypeError):
            _parse_type_list(raw_value, allowed=COLLECT_TYPE_EXTENSIONS)


def test_consolidate_type_parser_accepts_known_values() -> None:
    for type_name in SINGLE_TYPE_EXTENSIONS:
        parsed = _parse_type_list(type_name, allowed=SINGLE_TYPE_EXTENSIONS)
        assert parsed == (type_name,)


def test_parse_type_list_handles_duplicates_and_case() -> None:
    raw = "Python, css , PYTHON , Js"
    parsed = _parse_type_list(raw, allowed=COLLECT_TYPE_EXTENSIONS)
    assert parsed == ("python", "css", "js")
