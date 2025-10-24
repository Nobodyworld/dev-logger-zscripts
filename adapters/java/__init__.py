"""Java adapter for Maven or Gradle build logs."""

from __future__ import annotations

from adapters.base import LogAdapter
from adapters.structured import parse_structured_log
from zscripts.schemas import NormalizedLog


class JavaAdapter(LogAdapter):
    """Adapter that parses Maven-style logs."""

    identifier = "java"
    ecosystem = "java"
    description = "Parse Maven build logs into normalized schema."

    def parse(self, raw: str) -> NormalizedLog:
        """Parse logs into :class:`NormalizedLog` data.

        Args:
            raw: Raw log text.

        Returns:
            NormalizedLog: Parsed log representation.
        """

        normalized = parse_structured_log(
            raw,
            default_tool="maven",
            ecosystem=self.ecosystem,
            default_status="failed",
        )
        normalized.metadata.setdefault("language", "java")
        return normalized


ADAPTER = JavaAdapter()

