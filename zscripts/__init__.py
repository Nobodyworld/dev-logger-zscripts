"""Top-level package for the zscripts universal build log toolkit.

This package exposes helper utilities used by the CLI entry point and
adapter modules. Import :func:`get_version` to discover the current package
version or :func:`get_default_config` to obtain configuration defaults.
"""

from __future__ import annotations

from importlib import metadata

from zscripts.config import DEFAULT_CONFIG, ToolkitConfig


def get_version() -> str:
    """Return the installed package version.

    Returns:
        str: The version string resolved from package metadata. Defaults to
        ``"0.0.0"`` when metadata is unavailable (such as during editable
        installs).
    """

    try:
        return metadata.version("zscripts")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def get_default_config() -> ToolkitConfig:
    """Create a copy of the default toolkit configuration.

    Returns:
        ToolkitConfig: Configuration object describing sandbox defaults and
        adapter preferences.
    """

    return ToolkitConfig(**DEFAULT_CONFIG)


__all__ = ["get_version", "get_default_config", "ToolkitConfig"]
