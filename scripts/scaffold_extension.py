"""CLI utility for scaffolding toolkit extensions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from zscripts.extensions.scaffolding import scaffold_extension
except ImportError:  # pragma: no cover - fallback for direct execution
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from zscripts.extensions.scaffolding import scaffold_extension


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Extension module name (snake_case)")
    parser.add_argument(
        "--directory",
        default="zscripts/extensions",
        help="Directory where the extension module should be created.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        module_path = scaffold_extension(args.name, Path(args.directory))
    except (ValueError, FileExistsError) as exc:
        sys.exit(str(exc))
    print(f"Created {module_path}")


if __name__ == "__main__":
    main()
