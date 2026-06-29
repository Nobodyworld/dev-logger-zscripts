"""Python ecosystem adapter for pytest and build logs."""

from __future__ import annotations

from adapters.base import LogAdapter
from adapters.structured import parse_structured_log
from zscripts.schemas import NormalizedLog


class PythonAdapter(LogAdapter):
    """Adapter that parses pytest-oriented structured logs."""

    identifier = "python"
    ecosystem = "python"
    description = "Parse pytest output into normalized schema."

    def parse(self, raw: str) -> NormalizedLog:
        """Parse pytest logs into :class:`NormalizedLog` data.

        Args:
            raw: Raw log text.

        Returns:
            NormalizedLog: Parsed log representation.
        """

        normalized = parse_structured_log(
            raw,
            default_tool="pytest",
            ecosystem=self.ecosystem,
            default_status="failed",
        )
        normalized.metadata.setdefault("language", "python")
        return normalized


ADAPTER = PythonAdapter()
