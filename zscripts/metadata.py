"""Metadata helpers wrapping :mod:`importlib.metadata` access."""

from __future__ import annotations

from functools import lru_cache
from importlib import metadata as importlib_metadata

PackageNotFoundError = importlib_metadata.PackageNotFoundError
"""Alias for compatibility with :mod:`importlib.metadata`."""


@lru_cache(maxsize=1)
def distribution_name() -> str:
    """Return the package name used for metadata lookups."""

    return __package__ or "zscripts"


def version(distribution: str | None = None) -> str:
    """Return the installed version of the requested distribution.

    Args:
        distribution: Optional explicit distribution name. Defaults to the
            toolkit's canonical package name.

    Raises:
        PackageNotFoundError: If metadata cannot be located for the package.
    """

    target = distribution or distribution_name()
    return importlib_metadata.version(target)


__all__ = ["PackageNotFoundError", "distribution_name", "version"]

