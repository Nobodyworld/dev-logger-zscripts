"""Extension loader utilities."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Sequence
from types import ModuleType
from typing import cast

from zscripts.extensions.base import ExtensionContext, ToolkitExtensionProtocol
from zscripts.observability.logging import get_logger


class ExtensionLoadError(RuntimeError):
    """Raised when an extension cannot be imported or initialised."""


def load_extensions(
    modules: Sequence[str],
    *,
    context: ExtensionContext,
) -> list[ToolkitExtensionProtocol]:
    """Load and initialise extensions listed in ``modules``."""

    loaded: list[ToolkitExtensionProtocol] = []
    logger = get_logger("extensions.loader")
    instrumentation = context.instrumentation
    for module_path in modules:
        with instrumentation.operation(
            "extension.load",
            attributes={"extension": module_path},
        ):
            try:
                module: ModuleType = importlib.import_module(module_path)
            except ImportError as exc:  # pragma: no cover - exercised via tests
                message = f"Failed to import extension '{module_path}': {exc}".rstrip()
                logger.error("extension.import_failed", extra={"extension": module_path})
                raise ExtensionLoadError(message) from exc
            factory: object = getattr(module, "get_extension", None)
            if callable(factory):
                extension_factory = cast(Callable[[], ToolkitExtensionProtocol], factory)
                extension = extension_factory()
            elif hasattr(module, "Extension"):
                extension_cls = cast(type[ToolkitExtensionProtocol], module.Extension)
                extension = extension_cls()
            else:
                raise ExtensionLoadError(
                    f"Extension module '{module_path}' must expose get_extension() or Extension class."
                )
            context.logger.debug(
                "extension.instantiate", extra={"extension": getattr(extension, "name", module_path)}
            )
            extension.on_load(context)
            loaded.append(extension)
    instrumentation.gauge(
        "zscripts_extensions_active",
        "Number of active toolkit extensions.",
    ).set(len(loaded), labels={"loader": "runtime"})
    return loaded


__all__ = ["load_extensions", "ExtensionLoadError"]
