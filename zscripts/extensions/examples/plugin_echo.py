"""Reference extension demonstrating CLI integration."""

from __future__ import annotations

import argparse
from typing import Any

from zscripts.extensions.base import ExtensionContext, ToolkitExtension


class EchoExtension(ToolkitExtension):
    """Emit a greeting to demonstrate extension wiring."""

    name = "echo"
    description = "Echo input using the ToolkitService"
    version = "1.0.0"
    capabilities = ("cli", "demo")

    def register_cli(
        self,
        subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
        context: ExtensionContext,
    ) -> None:
        parser = subparsers.add_parser(
            "echo",
            help="Echo a message using the extension framework.",
        )
        parser.add_argument("message", help="Message to echo back to the caller.")
        parser.set_defaults(func=self.handle_cli)
        context.logger.debug("extension.cli.registered", extra={"extension": self.name})

    def handle_cli(self, args: argparse.Namespace, service: Any) -> None:
        message = getattr(args, "message", "")
        with self.context.instrumentation.operation(
            "extension.echo.cli",
            attributes={"extension": self.name},
        ):
            self.context.logger.info(
                "extension.echo",
                extra={"extension": self.name, "payload": message},
            )
            print(message)

    def after_service_ready(self, service: Any, context: ExtensionContext) -> None:
        """Log the registered manifest when the service is initialised."""

        super().after_service_ready(service, context)
        manifest = self.manifest
        if manifest is not None:
            context.logger.debug(
                "extension.echo.manifest", extra={"manifest": manifest.to_dict()}
            )


def get_extension() -> EchoExtension:
    """Factory used by the extension loader."""

    return EchoExtension()
