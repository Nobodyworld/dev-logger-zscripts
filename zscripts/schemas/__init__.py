"""Schema utilities for the zscripts toolkit."""

from __future__ import annotations

import json
from importlib import resources
from typing import cast

from zscripts.schemas.normalized import LogIssue, NormalizedLog, TestCaseResult, TestSummary


def load_normalized_schema() -> dict[str, object]:
    """Load the JSON schema that describes :class:`NormalizedLog` objects.

    Returns:
        dict[str, object]: Parsed JSON schema data.
    """

    with resources.files("schemas").joinpath("normalized_log.json").open("r", encoding="utf-8") as handle:
        data: object = json.load(handle)
    return cast(dict[str, object], data)


__all__ = [
    "load_normalized_schema",
    "NormalizedLog",
    "TestSummary",
    "TestCaseResult",
    "LogIssue",
]
