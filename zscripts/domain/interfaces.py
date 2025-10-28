"""Domain-level protocol definitions shared across application layers."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from zscripts.domain.models import SandboxOptions, SandboxResult
from zscripts.schemas import NormalizedLog


class LogAdapterProtocol(Protocol):
    """Behavior that concrete log adapters must provide."""

    identifier: str
    ecosystem: str
    description: str

    def collect(self, source: Path, sandbox: SandboxOptions | None = None) -> str:
        """Collect raw logs from a path or external source."""

    def parse(self, raw: str) -> NormalizedLog:
        """Transform raw log text into a normalized representation."""

    def summarize(self, normalized: NormalizedLog) -> str:
        """Produce a concise textual summary for presentation."""


class AdapterRegistryProtocol(Protocol):
    """Lookup surface for discovering log adapters."""

    def available(self) -> Sequence[str]:
        """Return the identifiers of all registered adapters."""

    def resolve(self, key: str) -> LogAdapterProtocol:
        """Return the adapter associated with ``key``."""


class SandboxRunnerProtocol(Protocol):
    """Execute commands within guarded sandbox constraints."""

    def run(self, command: Sequence[str]) -> SandboxResult:
        """Execute ``command`` and return the captured result."""


SandboxRunnerFactory = Callable[[SandboxOptions], SandboxRunnerProtocol]
"""Factory returning sandbox runners configured for specific options."""


class RedactorProtocol(Protocol):
    """Mask sensitive information inside log text."""

    def redact(self, text: str) -> str:
        """Return ``text`` with sensitive substrings replaced."""


class SchemaValidatorProtocol(Protocol):
    """Validate normalized logs against a contract."""

    def validate(self, data: NormalizedLog) -> None:
        """Raise if ``data`` violates schema expectations."""


class ExampleRepositoryProtocol(Protocol):
    """Discover bundled example log files."""

    def list_examples(self, adapter: str | None = None) -> Sequence[Path]:
        """Return example paths filtered by an optional adapter key."""


__all__ = [
    "AdapterRegistryProtocol",
    "ExampleRepositoryProtocol",
    "LogAdapterProtocol",
    "RedactorProtocol",
    "SandboxRunnerFactory",
    "SandboxRunnerProtocol",
    "SchemaValidatorProtocol",
]
