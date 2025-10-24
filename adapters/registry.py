"""Adapter discovery and lookup utilities."""

from __future__ import annotations

from collections.abc import Iterable

from adapters.base import LogAdapter, build_registry


class AdapterNotFoundError(KeyError):
    """Raised when a requested adapter is not available."""


_registry = build_registry([])


def register_adapters(adapters: Iterable[LogAdapter]) -> None:
    """Register adapter instances in the global registry.

    Args:
        adapters: Iterable of adapters to register.
    """

    _registry.update(build_registry(adapters))


def get_adapter(identifier: str) -> LogAdapter:
    """Return a registered adapter by its identifier.

    Args:
        identifier: Adapter key.

    Returns:
        LogAdapter: Registered adapter instance.

    Raises:
        AdapterNotFoundError: Raised when no adapter matches ``identifier``.
    """

    try:
        return _registry[identifier]
    except KeyError as exc:
        raise AdapterNotFoundError(identifier) from exc


def available_adapters() -> list[str]:
    """Return the list of registered adapter identifiers.

    Returns:
        List[str]: Sorted adapter identifiers.
    """

    return sorted(_registry)


__all__ = ["register_adapters", "get_adapter", "available_adapters", "AdapterNotFoundError"]
