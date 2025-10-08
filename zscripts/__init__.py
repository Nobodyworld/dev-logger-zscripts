"""
Core package initialisation for the zscripts toolkit.

This module exposes key submodules so they can be imported as
`zscripts.config`, `zscripts.utils`, or `zscripts.operations`.
"""

from . import config, utils  # noqa: F401  (re-export for convenience)

__all__ = ["config", "utils"]

