"""Go adapter for go test and go build logs."""

from __future__ import annotations

from adapters.base import LogAdapter
from adapters.structured import parse_structured_log
from zscripts.schemas import NormalizedLog


class GoAdapter(LogAdapter):
    """Adapter that parses Go tooling output."""

    identifier = "go"
    ecosystem = "go"
    description = "Parse go test output into normalized schema."

    def parse(self, raw: str) -> NormalizedLog:
        """Parse logs into :class:`NormalizedLog` data.

        Args:
            raw: Raw log text.

        Returns:
            NormalizedLog: Parsed log representation.
        """

        normalized = parse_structured_log(
            raw,
            default_tool="go test",
            ecosystem=self.ecosystem,
            default_status="passed",
        )
        normalized.metadata.setdefault("language", "go")
        return normalized


ADAPTER = GoAdapter()

