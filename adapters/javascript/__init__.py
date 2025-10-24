"""JavaScript and TypeScript adapter for Node-based tooling."""

from __future__ import annotations

from adapters.base import LogAdapter
from adapters.structured import parse_structured_log
from zscripts.schemas import NormalizedLog


class JavaScriptAdapter(LogAdapter):
    """Adapter that parses Jest test logs."""

    identifier = "javascript"
    ecosystem = "javascript"
    description = "Parse Jest output into normalized schema."

    def parse(self, raw: str) -> NormalizedLog:
        """Parse logs into :class:`NormalizedLog` data.

        Args:
            raw: Raw log text.

        Returns:
            NormalizedLog: Parsed log representation.
        """

        normalized = parse_structured_log(
            raw,
            default_tool="jest",
            ecosystem=self.ecosystem,
            default_status="passed",
        )
        normalized.metadata.setdefault("language", "javascript")
        normalized.metadata.setdefault("supports_typescript", "true")
        return normalized


ADAPTER = JavaScriptAdapter()

