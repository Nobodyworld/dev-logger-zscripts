"""Set up a local development environment for the zscripts toolkit."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_REQUIREMENTS = Path("requirements.txt")


def _run(command: list[str]) -> None:
    subprocess.check_call(command)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--requirements",
        default=str(DEFAULT_REQUIREMENTS),
        help="Primary requirements file for the editable development environment.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip pip install commands and only print the planned actions.",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Show the commands that would run without executing them.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    requirements_path = Path(args.requirements)
    if requirements_path.exists():
        commands = [[sys.executable, "-m", "pip", "install", "-r", str(requirements_path)]]
    else:
        commands = [[sys.executable, "-m", "pip", "install", "-e", ".[dev,helpers]"]]

    for cmd in commands:
        print("$", " ".join(cmd))
        if args.print_only or args.skip_install:
            continue
        _run(cmd)

    if not args.print_only and not args.skip_install:
        for hook_cmd in (
            ["pre-commit", "install"],
            ["pre-commit", "install", "--hook-type", "commit-msg"],
        ):
            print("$", " ".join(hook_cmd))
            try:
                _run(hook_cmd)
            except FileNotFoundError:
                print("pre-commit is not installed; skipping hook setup.")
                break
            except subprocess.CalledProcessError as exc:  # noqa: PERF203 - explicit logging
                print(f"pre-commit installation failed: {exc}")
                break

    print("Environment bootstrap complete.")


if __name__ == "__main__":
    main()
