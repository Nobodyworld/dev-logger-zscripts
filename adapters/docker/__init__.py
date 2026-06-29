"""Docker adapter for container build logs."""

from __future__ import annotations

from adapters.base import LogAdapter
from adapters.structured import parse_structured_log
from zscripts.schemas import NormalizedLog


class DockerAdapter(LogAdapter):
    """Adapter that parses docker build output."""

    identifier = "docker"
    ecosystem = "docker"
    description = "Parse docker build logs into normalized schema."

    def parse(self, raw: str) -> NormalizedLog:
        """Parse logs into :class:`NormalizedLog` data.

        Args:
            raw: Raw log text.

        Returns:
            NormalizedLog: Parsed log representation.
        """

        normalized = parse_structured_log(
            raw,
            default_tool="docker build",
            ecosystem=self.ecosystem,
            default_status="failed",
        )
        normalized.metadata.setdefault("language", "dockerfile")
        return normalized


ADAPTER = DockerAdapter()
