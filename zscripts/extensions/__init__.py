"""Extension loading and contracts for zscripts."""

from zscripts.extensions.base import ExtensionContext, ToolkitExtensionProtocol
from zscripts.extensions.hooks import ExtensionHookRegistry
from zscripts.extensions.manifest import ExtensionManifest
from zscripts.extensions.registry import ExtensionLoadError, ExtensionManager, load_extensions
from zscripts.extensions.scaffolding import scaffold_extension

__all__ = [
    "ExtensionContext",
    "ToolkitExtensionProtocol",
    "ExtensionHookRegistry",
    "ExtensionManifest",
    "ExtensionLoadError",
    "ExtensionManager",
    "load_extensions",
    "scaffold_extension",
]
