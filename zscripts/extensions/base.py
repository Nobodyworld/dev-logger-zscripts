"""Contracts describing toolkit extensions."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from zscripts.config import ToolkitConfig
from zscripts.domain.interfaces import AdapterRegistryProtocol
from zscripts.observability.instrumentation import InstrumentationManager
from zscripts.observability.telemetry import TelemetryManager

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from zscripts.application.services import ToolkitService


@dataclass(slots=True)
class ExtensionContext:
    """Context passed to extensions during registration."""

    config: ToolkitConfig
    adapter_registry: AdapterRegistryProtocol
    telemetry: TelemetryManager | None
    instrumentation: InstrumentationManager
    logger: logging.Logger


class ToolkitExtensionProtocol(Protocol):
    """Behavior extensions must provide to integrate with the toolkit."""

    name: str
    description: str

    def on_load(self, context: ExtensionContext) -> None:
        """Called immediately after the extension is instantiated."""

    def register_cli(
        self,
        subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
        context: ExtensionContext,
    ) -> None:
        """Allow the extension to register CLI commands."""

    def after_service_ready(self, service: ToolkitService, context: ExtensionContext) -> None:
        """Hook invoked after the application service is constructed."""


class ToolkitExtension:
    """Convenience base class implementing optional hooks."""

    name = "extension"
    description = "Toolkit extension"

    def __init__(self) -> None:
        self._context: ExtensionContext | None = None

    @property
    def context(self) -> ExtensionContext:
        """Return the most recent extension context."""

        if self._context is None:
            raise RuntimeError("Extension context has not been initialised yet.")
        return self._context

    def on_load(self, context: ExtensionContext) -> None:  # noqa: D401 - default no-op
        self._context = context
        context.logger.debug(
            "extension.loaded",
            extra={"extension": self.name},
        )

    def register_cli(
        self,
        subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
        context: ExtensionContext,
    ) -> None:  # noqa: D401 - default no-op
        context.logger.debug(
            "extension.cli.noop",
            extra={"extension": self.name},
        )

    def after_service_ready(self, service: ToolkitService, context: ExtensionContext) -> None:  # noqa: D401
        context.logger.debug(
            "extension.service.ready",
            extra={"extension": self.name},
        )


__all__ = ["ExtensionContext", "ToolkitExtensionProtocol", "ToolkitExtension"]
