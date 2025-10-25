"""Generate a starter extension module under zscripts/extensions."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from string import Template
from textwrap import dedent

TEMPLATE = Template(
    dedent(
        """\"\"\"Create a new toolkit extension.\"\"\"

from __future__ import annotations

import argparse
from typing import Any

from zscripts.extensions.base import ExtensionContext, ToolkitExtension


class ${class_name}(ToolkitExtension):
    \"\"\"Describe the behavior of this extension.\"\"\"

    name = \"${name}\"
    description = \"Describe what this extension does\"

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

    def handle_cli(self, args: argparse.Namespace, service: Any) -> None:
        from zscripts.observability.logging import get_logger  # noqa: PLC0415

        logger = get_logger(f\"extensions.{self.name}\")
        payload = getattr(args, \"message\", \"\")
        extra = {\"extension\": self.name, \"payload\": payload}
        logger.info(\"extension.message\", extra=extra)
        print(payload)


def get_extension() -> ${class_name}:
    \"\"\"Return the extension instance used by the loader.\"\"\"

    return ${class_name}()
"""
    )
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Extension module name (snake_case)")
    parser.add_argument(
        "--directory",
        default="zscripts/extensions",
        help="Directory where the extension module should be created.",
    )
    return parser.parse_args(argv)


def validate_name(name: str) -> None:
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*", name):
        sys.exit(f"Invalid extension name: {name!r}")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    validate_name(args.name)
    target_dir = Path(args.directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    module_path = target_dir / f"{args.name}.py"
    if module_path.exists():
        sys.exit(f"Extension module {module_path} already exists")
    class_name = "".join(part.capitalize() for part in args.name.split("_")) + "Extension"
    module_path.write_text(
        TEMPLATE.substitute(name=args.name, class_name=class_name),
        encoding="utf-8",
    )
    print(f"Created {module_path}")


if __name__ == "__main__":
    main()
