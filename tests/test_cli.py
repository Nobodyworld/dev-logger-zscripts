"""Integration tests exercising the public :mod:`zscripts.cli` entry points."""

from __future__ import annotations

import json
import random
import string
from pathlib import Path

import pytest

# TODO - (platform-parity) Extend CLI integration tests for Windows-specific path rules.

from zscripts.cli import (
    COLLECT_TYPE_EXTENSIONS,
    SINGLE_TYPE_EXTENSIONS,
    UnknownTypeError,
    _parse_type_list,
)
from zscripts.cli import main as cli_main
from zscripts.config import get_config


def test_cli_collect_writes_logs(sample_project_path: Path, tmp_path: Path) -> None:
    """Collect command should materialise language-specific logs within the target."""
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


def test_cli_collect_reports_summary(
    sample_project_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Collect command should emit a human-readable capture summary."""
    exit_code = cli_main(
        [
            "collect",
            "--types",
            "python",
            "--project-root",
            str(sample_project_path),
            "--output-dir",
            str(tmp_path / "logs"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Summary:" in captured.out
    assert "files captured" in captured.out


def test_cli_consolidate_writes_file(sample_project_path: Path, tmp_path: Path) -> None:
    """Consolidate command should write merged source content to the output file."""
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


def test_cli_consolidate_reports_summary(
    sample_project_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Consolidate command should report statistics without warnings."""
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

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "files" in captured.out
    assert "skipped" not in captured.err


def test_cli_consolidate_warns_when_output_outside_default_root(
    sample_project_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Consolidate should warn if the output directory escapes the configured root."""
    outside_output = tmp_path / "custom" / "python.txt"

    exit_code = cli_main(
        [
            "consolidate",
            "--types",
            "python",
            "--project-root",
            str(sample_project_path),
            "--output",
            str(outside_output),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Output path is outside the configured single-log directory" in captured.err


def test_cli_consolidate_includes_js_variants(
    sample_project_path: Path, tmp_path: Path
) -> None:
    """Consolidate should capture all supported JavaScript-family file extensions."""
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


def test_cli_tree_respects_include_contents(
    sample_project_path: Path, tmp_path: Path
) -> None:
    """Tree command should inline file contents when requested."""
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
    assert "Summary:" in content


def test_cli_collect_dry_run_skips_writes(
    sample_project_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Collect dry run should avoid touching the filesystem while previewing work."""
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
    assert "files, ~" in captured.out
    assert "(size unavailable)" not in captured.out


def test_cli_collect_dry_run_reports_size_errors(
    sample_project_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Collect dry run should surface file size probe failures as warnings."""
    output_dir = tmp_path / "preview"
    target_path = sample_project_path / "backend" / "service.py"
    original_stat = Path.stat

    def failing_stat(self: Path, *args, **kwargs):  # type: ignore[override]
        follow_symlinks = kwargs.get("follow_symlinks", True)
        if self == target_path and follow_symlinks:
            raise OSError("permission denied")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", failing_stat)

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
    assert exit_code == 1
    assert "backend/service.py (size unavailable)" in captured.out
    assert "warning: Failed to determine size for 1 file(s) in [backend]; review logs." in captured.err
    assert "warning: Dry run detected issues; exiting with status 1." in captured.err
    assert "warning: Collect dry run detected issues; review warnings above." in captured.err


def test_cli_consolidate_dry_run_lists_files(
    sample_project_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Consolidate dry run should list files without writing the output artifact."""
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


def test_cli_collect_warns_when_types_empty(
    sample_project_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Collect should warn when no type filters are supplied by the operator."""
    exit_code = cli_main(
        [
            "collect",
            "--types",
            " ",
            "--project-root",
            str(sample_project_path),
            "--output-dir",
            str(tmp_path / "logs"),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "warning: No types provided" in captured.err
    assert "Dry run enabled" in captured.out


def test_cli_consolidate_warns_when_types_empty(
    sample_project_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Consolidate should warn but still succeed when no types are provided."""
    output = tmp_path / "python.txt"

    exit_code = cli_main(
        [
            "consolidate",
            "--types",
            "",
            "--project-root",
            str(sample_project_path),
            "--output",
            str(output),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert output.exists()
    assert "warning: No types provided" in captured.err


def test_cli_consolidate_streams_to_stdout(
    sample_project_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Consolidate should respect stdout streaming when '-' is supplied."""
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
    """Tree dry run should preview output instead of writing to disk."""
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
    assert "Summary:" in captured.out


def test_cli_tree_streams_stdout_and_limits_bytes(
    sample_project_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Tree should stream to stdout and respect byte limits for content previews."""
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
    assert '│   """Service' in captured.out
    assert "✓ Wrote project tree to stdout" in captured.err
    assert "Summary:" in captured.out


def test_cli_tree_reports_summary(
    sample_project_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Tree command should report totals when writing to disk."""
    tree_path = tmp_path / "tree.txt"

    exit_code = cli_main(
        [
            "tree",
            "--project-root",
            str(sample_project_path),
            "--output",
            str(tree_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "lines" in captured.out
    assert "Preview summary" not in captured.out


def test_cli_collect_auto_detects_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Collect should derive the project root from the current working directory."""
    project_root = tmp_path / "auto-project"
    nested = project_root / "nested" / "deep"
    nested.mkdir(parents=True)
    (project_root / ".git").mkdir()
    (project_root / "module.py").write_text("print('hello')\n", encoding="utf-8")

    monkeypatch.chdir(nested)

    exit_code = cli_main(
        [
            "collect",
            "--types",
            "python",
            "--output-dir",
            str(tmp_path / "logs"),
        ]
    )

    assert exit_code == 0
    output_dir = tmp_path / "logs"
    python_log = output_dir / "logs_apps_pyth"
    assert python_log.exists()
    log_file = python_log / "root.txt"
    assert log_file.exists()
    contents = log_file.read_text(encoding="utf-8")
    assert "module.py" in contents


def test_cli_collect_rejects_invalid_log_filename(
    sample_project_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Collect should validate configured log filenames for portability."""
    default_config_path = Path("zscripts.config.json")
    config_data = json.loads(default_config_path.read_text(encoding="utf-8"))
    config_data["collection_logs"]["python"] = "invalid:name"
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    exit_code = cli_main(
        [
            "collect",
            "--types",
            "python",
            "--project-root",
            str(sample_project_path),
            "--config",
            str(config_file),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "invalid:name" in captured.err


def test_cli_rejects_unknown_type(
    sample_project_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Collect should reject unknown type identifiers with a helpful message."""
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
    """Collect should fail fast when the supplied project root is missing."""
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
    """Fuzz-test that type parser trims whitespace and preserves order."""
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
    """Fuzz-test that the type parser rejects unknown identifiers."""
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
    """Type parser should accept every single-target extension preset."""
    for type_name in SINGLE_TYPE_EXTENSIONS:
        parsed = _parse_type_list(type_name, allowed=SINGLE_TYPE_EXTENSIONS)
        assert parsed == (type_name,)


def test_parse_type_list_handles_duplicates_and_case() -> None:
    """Type parser should de-duplicate identifiers regardless of casing."""
    raw = "Python, css , PYTHON , Js"
    parsed = _parse_type_list(raw, allowed=COLLECT_TYPE_EXTENSIONS)
    assert parsed == ("python", "css", "js")
