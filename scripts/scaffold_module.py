"""CLI utility that scaffolds extensions or health check modules."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from string import Template
from textwrap import dedent
from typing import cast

from zscripts.extensions.scaffolding import scaffold_extension, validate_extension_name

_HEALTH_TEMPLATE = Template(
    dedent(
        '''\
        """Health check provider for ${module_name}."""

        from __future__ import annotations

        from collections.abc import Mapping

        from zscripts.observability.health_checks import HealthCheckRegistry


        def register(registry: HealthCheckRegistry) -> None:
            """Register the ${module_name} health probe with the shared registry."""

            registry.register(
                "service.${slug}",
                _${slug}_snapshot,
                kind="service",
                description="${description}",
            )


        def _${slug}_snapshot() -> Mapping[str, object]:
            """Return a placeholder health payload until real probes exist."""

            # TODO(P2, est:4h): replace placeholder implementation with concrete status probes.
            return {"status": "ok", "details": "${module_name} placeholder"}
        '''
    )
)


def _scaffold_extension(args: argparse.Namespace) -> int:
    target_dir = Path(args.directory).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    validate_extension_name(args.name)
    path = scaffold_extension(args.name, target_dir)
    print(f"Created extension skeleton at {path}")
    return 0


def _scaffold_health(args: argparse.Namespace) -> int:
    target_dir = Path(args.directory).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    module_path = target_dir / f"{args.name}.py"
    if module_path.exists() and not args.force:
        raise FileExistsError(f"Health check module {module_path} already exists; use --force to overwrite.")
    slug = args.name.replace("-", "_")
    validate_extension_name(slug)
    contents = _HEALTH_TEMPLATE.substitute(
        module_name=args.name,
        slug=slug,
        description=args.description or f"Health snapshot for {args.name}",
    )
    module_path.write_text(contents, encoding="utf-8")
    print(f"Created health check skeleton at {module_path}")
    return 0


CommandHandler = Callable[[argparse.Namespace], int]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold extensions or health check modules.")
    subparsers = parser.add_subparsers(dest="kind", required=True)

    ext_parser = subparsers.add_parser("extension", help="Create a telemetry-aware extension skeleton.")
    ext_parser.add_argument("name", help="Extension module name (snake_case).")
    ext_parser.add_argument(
        "--directory",
        default="zscripts/extensions",
        help="Target directory for the generated extension module.",
    )
    ext_parser.set_defaults(func=_scaffold_extension)

    health_parser = subparsers.add_parser(
        "health", help="Create a reusable health check provider leveraging the registry."
    )
    health_parser.add_argument("name", help="Health check identifier (snake_case).")
    health_parser.add_argument(
        "--directory",
        default="zscripts/observability/checks",
        help="Target directory for the generated health module.",
    )
    health_parser.add_argument(
        "--description",
        help="Optional description stored alongside the registry entry.",
    )
    health_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files when set.",
    )
    health_parser.set_defaults(func=_scaffold_health)

    args = parser.parse_args(argv)
    try:
        handler = cast(CommandHandler, args.func)
        return handler(args)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
