"""Build a runnable zipapp bundle for the zscripts CLI."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from zipapp import create_archive

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "build" / "zscripts.pyz"


def build_cli_bundle(output: Path) -> Path:
    """Create a zipapp for the CLI and return the generated path."""

    package_root = PROJECT_ROOT / "zscripts"
    if not package_root.exists():
        raise SystemExit(f"Package directory missing: {package_root}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        staging_root = Path(tmpdir)
        for package in ("zscripts", "adapters", "scripts"):
            source = PROJECT_ROOT / package
            if not source.exists():
                raise SystemExit(f"Package directory missing: {source}")
            shutil.copytree(source, staging_root / package, ignore=shutil.ignore_patterns("__pycache__"))
        create_archive(
            source=staging_root,
            target=output,
            main="zscripts.cli:main",
            interpreter="/usr/bin/env python3",
        )
    return output


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Path to the generated zipapp (default: {DEFAULT_OUTPUT}).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    bundle_path = build_cli_bundle(args.output)
    print(bundle_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
