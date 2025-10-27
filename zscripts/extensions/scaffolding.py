"""Helpers for generating starter extension modules."""

from __future__ import annotations

import re
from pathlib import Path
from string import Template
from textwrap import dedent

_EXTENSION_TEMPLATE = Template(
    dedent(
        """\"\"\"Describe the behavior of this extension.\"\"\"

from __future__ import annotations

import argparse
from typing import Any

from zscripts.extensions.base import ExtensionContext, ToolkitExtension


class ${class_name}(ToolkitExtension):
    \"\"\"Describe what this extension accomplishes.\"\"\"

    name = \"${name}\"
    description = \"Describe what this extension does\"
    version = \"0.1.0\"
    capabilities = (\"cli\",)
    config_keys: tuple[str, ...] = ()

    def on_load(self, context: ExtensionContext) -> None:
        super().on_load(context)
        self.register_hook(\"service_ready\", self._on_service_ready)
        context.logger.debug(
            \"extension.${name}.hook_registered\", extra={\"extension\": self.name, \"hook\": \"service_ready\"}
        )

    def register_cli(
        self,
        subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
        context: ExtensionContext,
    ) -> None:
        parser = subparsers.add_parser(
            \"${name}\",
            help=\"CLI command provided by the ${name} extension.\",
        )
        parser.add_argument(\"message\", help=\"Message to emit from the extension.\")
        parser.set_defaults(func=self.handle_cli)
        context.logger.debug(
            \"extension.cli.registered\", extra={\"extension\": self.name}
        )

    def handle_cli(self, args: argparse.Namespace, service: Any) -> None:
        payload = getattr(args, \"message\", \"\")
        with self.context.instrumentation.operation(
            \"extension.${name}.cli\",
            attributes={\"extension\": self.name},
        ):
            self.context.logger.info(
                \"extension.${name}.message\",
                extra={\"extension\": self.name, \"payload\": payload},
            )
            print(payload)

    def after_service_ready(self, service: Any, context: ExtensionContext) -> None:
        \"\"\"Observe the manifest once the service is initialised.\"\"\"

        manifest = self.manifest
        context.logger.debug(
            \"extension.${name}.ready\",
            extra={
                \"extension\": self.name,
                \"manifest\": manifest.to_dict() if manifest else None,
            },
        )

    def _on_service_ready(self, **_: Any) -> None:
        self.context.logger.info(
            \"extension.${name}.hook\",
            extra={\"extension\": self.name, \"hook\": \"service_ready\"},
        )


def get_extension() -> ${class_name}:
    \"\"\"Return the extension instance used by the loader.\"\"\"

    return ${class_name}()
"""
    )
)

_NAME_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9_]*$")


def validate_extension_name(name: str) -> None:
    """Ensure the provided name matches toolkit naming rules."""

    if not _NAME_PATTERN.fullmatch(name):
        raise ValueError(
            "Extension names must start with a letter and contain only letters, numbers, or underscores."
        )


def scaffold_extension(name: str, directory: Path) -> Path:
    """Create a new extension module and return its path."""

    validate_extension_name(name)
    directory.mkdir(parents=True, exist_ok=True)
    module_path = directory / f"{name}.py"
    if module_path.exists():
        raise FileExistsError(f"Extension module {module_path} already exists.")
    class_name = "".join(part.capitalize() for part in name.split("_")) + "Extension"
    module_path.write_text(
        _EXTENSION_TEMPLATE.substitute(name=name, class_name=class_name),
        encoding="utf-8",
    )
    return module_path


__all__ = ["scaffold_extension", "validate_extension_name"]
