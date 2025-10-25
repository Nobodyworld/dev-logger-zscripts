"""Extension loading and contracts for zscripts."""

from zscripts.extensions.base import ExtensionContext, ToolkitExtensionProtocol
from zscripts.extensions.registry import ExtensionLoadError, load_extensions

__all__ = [
    "ExtensionContext",
    "ToolkitExtensionProtocol",
    "ExtensionLoadError",
    "load_extensions",
]
