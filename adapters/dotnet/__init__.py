""".NET adapter for dotnet build and test logs."""

from __future__ import annotations

from adapters.base import LogAdapter
from adapters.structured import parse_structured_log
from zscripts.schemas import NormalizedLog


class DotNetAdapter(LogAdapter):
    """Adapter that parses dotnet CLI output."""

    identifier = "dotnet"
    ecosystem = ".net"
    description = "Parse dotnet test output into normalized schema."

    def parse(self, raw: str) -> NormalizedLog:
        """Parse logs into :class:`NormalizedLog` data.

        Args:
            raw: Raw log text.

        Returns:
            NormalizedLog: Parsed log representation.
        """

        normalized = parse_structured_log(
            raw,
            default_tool="dotnet test",
            ecosystem=self.ecosystem,
            default_status="passed",
        )
        normalized.metadata.setdefault("language", "csharp")
        return normalized


ADAPTER = DotNetAdapter()

