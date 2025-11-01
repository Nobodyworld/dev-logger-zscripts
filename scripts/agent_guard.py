"""Run the toolkit's quality gates sequentially for automation agents."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence

MYPY_TARGETS = [
    "zscripts/application",
    "zscripts/config.py",
    "zscripts/configuration.py",
    "zscripts/observability/logging.py",
    "zscripts/observability/metrics.py",
    "zscripts/observability/health.py",
    "zscripts/observability/instrumentation.py",
    "zscripts/extensions/scaffolding.py",
    "zscripts/schemas",
]

COMMANDS: dict[str, Sequence[str]] = {
    "ruff": [sys.executable, "-m", "ruff", "check", "."],
    "mypy": [sys.executable, "-m", "mypy", *MYPY_TARGETS],
    "pytest": [sys.executable, "-m", "pytest"],
    "bandit": ["bandit", "-q", "-r", "zscripts", "examples/sample_project"],
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        action="append",
        choices=sorted(COMMANDS),
        help="Run only the specified guard (may be provided multiple times).",
    )
    parser.add_argument(
        "--skip",
        action="append",
        choices=sorted(COMMANDS),
        help="Skip the specified guard (may be provided multiple times).",
    )
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Abort immediately when a guard fails (defaults to running all).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    selected = list(COMMANDS)
    if args.only:
        selected = [name for name in selected if name in set(args.only)]
    if args.skip:
        selected = [name for name in selected if name not in set(args.skip)]

    failures: list[str] = []
    for name in selected:
        cmd = COMMANDS[name]
        print(f"\n==> Running {name}: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            failures.append(name)
            if args.stop_on_failure:
                break

    if failures:
        print(f"\nGuard failures: {', '.join(failures)}")
        sys.exit(1)
    print("\nAll guards passed.")


if __name__ == "__main__":
    main()
