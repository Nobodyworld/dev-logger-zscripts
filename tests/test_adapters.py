"""Smoke tests for ecosystem adapters using bundled example logs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from adapters import available_adapters, get_adapter
from zscripts.schemas import load_normalized_schema

try:  # pragma: no cover - optional dependency
    import jsonschema  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - fallback when jsonschema missing
    jsonschema = None

EXAMPLES = Path("examples")
EXPECTED_ADAPTERS = {
    "python",
    "javascript",
    "java",
    "go",
    "rust",
    "dotnet",
    "docker",
    "ci",
}


def test_available_adapters_match_supported_set() -> None:
    assert set(available_adapters()) == EXPECTED_ADAPTERS


@pytest.mark.parametrize("adapter_key", available_adapters())
def test_adapter_parses_example_log(adapter_key: str) -> None:
    """Each adapter should parse its bundled sample log without errors."""

    adapter = get_adapter(adapter_key)
    sample = EXAMPLES / adapter_key / "sample.log"
    assert sample.exists(), f"Missing sample log for {adapter_key}"
    normalized = adapter.parse(sample.read_text(encoding="utf-8"))
    assert normalized.tool
    assert normalized.ecosystem
    assert normalized.summary
    assert adapter.summarize(normalized)
    if jsonschema:
        jsonschema.validate(
            instance=normalized.to_dict(), schema=load_normalized_schema()
        )
