"""Reference extension demonstrating CLI integration."""

from __future__ import annotations

import argparse
from typing import Any

from zscripts.extensions.base import ExtensionContext, ToolkitExtension


class EchoExtension(ToolkitExtension):
    """Emit a greeting to demonstrate extension wiring."""

    name = "echo"
    description = "Echo input using the ToolkitService"

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
        # Import deferred to avoid circular dependency at module import time.
        from zscripts.observability.logging import get_logger  # noqa: PLC0415

        logger = get_logger("extensions.echo")
        message = getattr(args, "message", "")
        logger.info("extension.echo", extra={"extension": self.name, "payload": message})
        print(message)


def get_extension() -> EchoExtension:
    """Factory used by the extension loader."""

    return EchoExtension()
