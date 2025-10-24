"""Rust adapter for cargo build and test logs."""

from __future__ import annotations

from adapters.base import LogAdapter
from adapters.structured import parse_structured_log
from zscripts.schemas import NormalizedLog


class RustAdapter(LogAdapter):
    """Adapter that parses Cargo output."""

    identifier = "rust"
    ecosystem = "rust"
    description = "Parse cargo test output into normalized schema."

    def parse(self, raw: str) -> NormalizedLog:
        """Parse logs into :class:`NormalizedLog` data.

        Args:
            raw: Raw log text.

        Returns:
            NormalizedLog: Parsed log representation.
        """

        normalized = parse_structured_log(
            raw,
            default_tool="cargo",
            ecosystem=self.ecosystem,
            default_status="passed",
        )
        normalized.metadata.setdefault("language", "rust")
        return normalized


ADAPTER = RustAdapter()

