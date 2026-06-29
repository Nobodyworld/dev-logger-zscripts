"""Continuous integration adapter for CI pipeline logs."""

from __future__ import annotations

from adapters.base import LogAdapter
from adapters.structured import parse_structured_log
from zscripts.schemas import NormalizedLog


class CIAdapter(LogAdapter):
    """Adapter that parses CI job logs."""

    identifier = "ci"
    ecosystem = "ci"
    description = "Parse CI workflow logs into normalized schema."

    def parse(self, raw: str) -> NormalizedLog:
        """Parse logs into :class:`NormalizedLog` data.

        Args:
            raw: Raw log text.

        Returns:
            NormalizedLog: Parsed log representation.
        """

        normalized = parse_structured_log(
            raw,
            default_tool="ci",
            ecosystem=self.ecosystem,
            default_status="failed",
        )
        normalized.metadata.setdefault("language", "automation")
        return normalized


ADAPTER = CIAdapter()
