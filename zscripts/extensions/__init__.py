"""Extension loading and contracts for zscripts."""

from zscripts.extensions.base import ExtensionContext, ToolkitExtensionProtocol
from zscripts.extensions.manifest import ExtensionManifest
from zscripts.extensions.registry import ExtensionLoadError, load_extensions
from zscripts.extensions.scaffolding import scaffold_extension

__all__ = [
    "ExtensionContext",
    "ToolkitExtensionProtocol",
    "ExtensionManifest",
    "ExtensionLoadError",
    "load_extensions",
    "scaffold_extension",
]
