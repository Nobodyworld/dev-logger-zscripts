"""Extension loading and lifecycle management utilities."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterator, Sequence
from types import ModuleType
from typing import cast

from zscripts.extensions.base import ExtensionContext, ToolkitExtensionProtocol
from zscripts.extensions.manifest import ExtensionManifest, build_manifest
from zscripts.observability.logging import get_logger


class ExtensionManager:
    """Wrapper around loaded extensions exposing lifecycle helpers."""

    def __init__(
        self,
        *,
        extensions: list[ToolkitExtensionProtocol],
        context: ExtensionContext,
    ) -> None:
        self._extensions = extensions
        self._context = context
        self._logger = get_logger("extensions.manager")

    def __iter__(self) -> Iterator[ToolkitExtensionProtocol]:
        return iter(self._extensions)

    def __len__(self) -> int:
        return len(self._extensions)

    def __getitem__(self, index: int, /) -> ToolkitExtensionProtocol:
        return self._extensions[index]

    def names(self) -> list[str]:
        """Return extension display names for diagnostics."""

        names: list[str] = []
        for extension in self._extensions:
            raw_name = cast(object, getattr(extension, "name", extension.__class__.__name__))
            names.append(str(raw_name))
        return names

    def manifests(self) -> dict[str, ExtensionManifest]:
        """Return a copy of registered manifests."""

        return dict(self._context.manifests)

    def manifest_for(self, name: str) -> ExtensionManifest | None:
        """Return the manifest registered for ``name`` if present."""

        return self._context.manifests.get(name)

    def emit(self, hook: str, /, *args: object, **kwargs: object) -> list[object | None]:
        """Emit ``hook`` through the shared registry if available."""

        registry = self._context.hook_registry
        if registry is None:
            self._logger.debug(
                "extension.hook.skipped",
                extra={"hook": hook, "reason": "registry-missing"},
            )
            return []
        return list(registry.emit(hook, *args, **kwargs))

    def hook_summary(self) -> dict[str, int]:
        """Return counts of registered hooks for observability."""

        registry = self._context.hook_registry
        if registry is None:
            return {}
        return dict(registry.summary())


class ExtensionLoadError(RuntimeError):
    """Raised when an extension cannot be imported or initialised."""


def load_extensions(
    modules: Sequence[str],
    *,
    context: ExtensionContext,
) -> ExtensionManager:
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
    manager = ExtensionManager(extensions=loaded, context=context)
    instrumentation.gauge(
        "zscripts_extensions_active",
        "Number of active toolkit extensions.",
    ).set(len(manager), labels={"loader": "runtime"})
    return manager


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


__all__ = ["load_extensions", "ExtensionLoadError", "ExtensionManager"]
