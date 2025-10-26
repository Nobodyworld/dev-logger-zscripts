"""Extension loader utilities."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Sequence
from types import ModuleType
from typing import cast

from zscripts.extensions.base import ExtensionContext, ToolkitExtensionProtocol
from zscripts.extensions.manifest import ExtensionManifest, build_manifest
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
                entrypoint = f"{module_path}:get_extension"
            elif hasattr(module, "Extension"):
                extension_cls = cast(type[ToolkitExtensionProtocol], module.Extension)
                extension = extension_cls()
                entrypoint = f"{module_path}:Extension"
            else:
                raise ExtensionLoadError(
                    f"Extension module '{module_path}' must expose get_extension() or Extension class."
                )
            context.logger.debug(
                "extension.instantiate", extra={"extension": getattr(extension, "name", module_path)}
            )
            extension.on_load(context)
            manifest = _register_manifest(
                context=context,
                extension=extension,
                module=module_path,
                entrypoint=entrypoint,
            )
            logger.debug(
                "extension.manifest.registered",
                extra={
                    "extension": manifest.name,
                    "module": manifest.module,
                },
            )
            loaded.append(extension)
    instrumentation.gauge(
        "zscripts_extensions_active",
        "Number of active toolkit extensions.",
    ).set(len(loaded), labels={"loader": "runtime"})
    return loaded


def _register_manifest(
    *,
    context: ExtensionContext,
    extension: ToolkitExtensionProtocol,
    module: str,
    entrypoint: str,
) -> ExtensionManifest:
    manifest = build_manifest(
        extension=extension,
        module=module,
        entrypoint=entrypoint,
        default_name=module.rsplit(".", maxsplit=1)[-1],
    )
    context.manifests[manifest.name] = manifest
    return manifest


__all__ = ["load_extensions", "ExtensionLoadError"]
