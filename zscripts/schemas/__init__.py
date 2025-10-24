"""Schema utilities for the zscripts toolkit."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from zscripts.schemas.normalized import LogIssue, NormalizedLog, TestCaseResult, TestSummary


def load_normalized_schema() -> dict[str, Any]:
    """Load the JSON schema that describes :class:`NormalizedLog` objects.

    Returns:
        dict[str, Any]: Parsed JSON schema data.
    """

    with resources.files("schemas").joinpath("normalized_log.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


__all__ = [
    "load_normalized_schema",
    "NormalizedLog",
    "TestSummary",
    "TestCaseResult",
    "LogIssue",
]
