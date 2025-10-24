"""Base classes and helper utilities for log adapters."""

from __future__ import annotations

import abc
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from zscripts.schemas import NormalizedLog

if False:  # pragma: no cover - for type checkers only
    from scripts.sandbox import SandboxSettings


class LogAdapter(abc.ABC):
    """Abstract base class for log adapters."""

    identifier: str
    ecosystem: str
    description: str

    def __init__(self) -> None:
        self.identifier = getattr(self, "identifier", self.__class__.__name__.lower())

    @abc.abstractmethod
    def parse(self, raw: str) -> NormalizedLog:
        """Parse raw log text into a :class:`NormalizedLog` instance.

        Args:
            raw: Raw log text.

        Returns:
            NormalizedLog: Normalized representation of the log.
        """

    def collect(self, source: Path, sandbox: SandboxSettings | None = None) -> str:
        """Collect log text from the given path.

        Args:
            source: Path pointing to a log file.
            sandbox: Optional sandbox configuration for command execution.

        Returns:
            str: The raw log contents.
        """

        if source.is_file():
            return source.read_text(encoding="utf-8")
        msg = f"Unsupported source for adapter '{self.identifier}': {source}"
        raise ValueError(msg)

    def summarize(self, normalized: NormalizedLog) -> str:
        """Produce a compact textual summary of normalized log data."""

        parts = [
            f"[{normalized.status.upper()}] {normalized.tool} run for {normalized.ecosystem}",
            normalized.summary,
        ]
        if normalized.tests:
            parts.append(
                "Tests: "
                f"passed={normalized.tests.passed} "
                f"failed={normalized.tests.failed} "
                f"skipped={normalized.tests.skipped}"
            )
        if normalized.errors:
            parts.append(f"Errors: {len(normalized.errors)}")
        if normalized.warnings:
            parts.append(f"Warnings: {len(normalized.warnings)}")
        return " | ".join(parts)

    @staticmethod
    def now() -> datetime:
        """Return the current UTC timestamp.

        Returns:
            datetime: Current timestamp with timezone information omitted.
        """

        return datetime.utcnow()


AdapterRegistry = dict[str, LogAdapter]


def build_registry(adapters: Iterable[LogAdapter]) -> AdapterRegistry:
    """Construct a registry mapping adapter identifiers to instances.

    Args:
        adapters: Iterable of adapter instances to register.

    Returns:
        AdapterRegistry: Mapping of adapter identifier to instance.
    """

    return {adapter.identifier: adapter for adapter in adapters}


__all__ = ["LogAdapter", "build_registry", "AdapterRegistry"]
