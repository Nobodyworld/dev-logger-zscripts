"""Contract tests for public docs/examples required by release policy."""

from __future__ import annotations

import json
from pathlib import Path

from adapters import available_adapters
from zscripts.schemas import load_normalized_schema

try:  # pragma: no cover - optional dependency
    import jsonschema  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - fallback when jsonschema missing
    jsonschema = None

ROOT = Path(__file__).resolve().parents[1]


def test_required_docs_exist() -> None:
    required = [
        ROOT / "docs/adapters/SUPPORT_MATRIX.md",
        ROOT / "docs/guides/RAW_LOG_TO_REDACTED_REPORT.md",
        ROOT / "docs/guides/GITHUB_ACTIONS_USAGE.md",
        ROOT / "docs/helpers/LEGACY_OPTIONAL_HELPERS.md",
        ROOT / "docs/operations/LEGACY_HELPER_COMPATIBILITY.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    assert not missing, f"Missing required documentation files: {missing}"


def test_adapter_support_matrix_covers_registered_adapters() -> None:
    matrix_text = (ROOT / "docs/adapters/SUPPORT_MATRIX.md").read_text(encoding="utf-8")
    missing = [adapter for adapter in sorted(available_adapters()) if f"`{adapter}`" not in matrix_text]
    assert not missing, f"Adapters missing from support matrix: {missing}"


def test_raw_to_report_example_files_exist() -> None:
    fixture_dir = ROOT / "examples/raw_to_report"
    required = [
        fixture_dir / "raw.log",
        fixture_dir / "normalized.json",
        fixture_dir / "redacted_report.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    assert not missing, f"Missing raw-to-report fixtures: {missing}"


def test_normalized_example_matches_schema_when_available() -> None:
    if jsonschema is None:
        return

    normalized_path = ROOT / "examples/raw_to_report/normalized.json"
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=normalized, schema=load_normalized_schema())


def test_readme_raw_to_report_demo_uses_supported_adapter_order() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "python cli.py --adapter ci report --input examples/raw_to_report/raw.log" in readme
    assert "python cli.py report --adapter ci --input examples/raw_to_report/raw.log" not in readme
