"""Public package interface for the zscripts toolkit."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from . import metadata
from .config import DEFAULT_CONFIG, ToolkitConfig, clone_config, get_default_config
from .configuration import ConfigurationError, load_toolkit_config, parse_override_pairs

__all__ = [
    "DEFAULT_CONFIG",
    "ToolkitConfig",
    "ConfigurationError",
    "clone_config",
    "get_default_config",
    "get_version",
    "load_toolkit_config",
    "metadata",
    "parse_override_pairs",
]

_PACKAGE_NAME = "zscripts"


def get_version() -> str:
    """Return the installed package version.

    Falls back to ``"0.0.0"`` when the distribution metadata is not available
    (e.g., during editable installs or source checkouts).
    """

    try:
        return metadata.version(_PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return "0.0.0"


_LAZY_MODULES = {
    "application": "zscripts.application",
    "config": "zscripts.config",
    "extensions": "zscripts.extensions",
    "infrastructure": "zscripts.infrastructure",
    "observability": "zscripts.observability",
    "schemas": "zscripts.schemas",
}

__all__.extend(_LAZY_MODULES)


def __getattr__(name: str) -> Any:
    """Provide lazy access to frequently used subpackages."""

    if name in _LAZY_MODULES:
        module = import_module(_LAZY_MODULES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_MODULES))
