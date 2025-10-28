"""Infrastructure adapters wrapping concrete log adapter implementations."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from adapters import available_adapters, get_adapter
from adapters.base import LogAdapter as ConcreteLogAdapter
from scripts import SandboxSettings
from zscripts.domain.interfaces import AdapterRegistryProtocol, LogAdapterProtocol
from zscripts.domain.models import SandboxOptions
from zscripts.schemas import NormalizedLog


class AdapterWrapper(LogAdapterProtocol):
    """Wrap a concrete adapter to satisfy :class:`LogAdapterProtocol`."""

    def __init__(self, adapter: ConcreteLogAdapter) -> None:
        self._adapter = adapter
        self.identifier = adapter.identifier
        self.ecosystem = adapter.ecosystem
        self.description = adapter.description

    def collect(self, source: Path, sandbox: SandboxOptions | None = None) -> str:
        settings = _build_sandbox_settings(sandbox) if sandbox else None
        return self._adapter.collect(source, settings)

    def parse(self, raw: str) -> NormalizedLog:
        return self._adapter.parse(raw)

    def summarize(self, normalized: NormalizedLog) -> str:
        return self._adapter.summarize(normalized)


class AdapterRegistry(AdapterRegistryProtocol):
    """Adapter registry backed by the in-repo adapter loader."""

    def __init__(self) -> None:
        self._cache: dict[str, AdapterWrapper] = {}
        self._available: Sequence[str] = tuple(available_adapters())

    def available(self) -> Sequence[str]:
        return self._available

    def resolve(self, key: str) -> LogAdapterProtocol:
        if key not in self._cache:
            self._cache[key] = AdapterWrapper(get_adapter(key))
        return self._cache[key]


def _build_sandbox_settings(options: SandboxOptions) -> SandboxSettings:
    return SandboxSettings(
        allowed_paths=options.allowed_paths,
        timeout_seconds=options.timeout_seconds,
        dangerous_mode=options.dangerous_mode,
        env_allowlist=options.env_allowlist,
    )


__all__ = ["AdapterRegistry", "AdapterWrapper"]
