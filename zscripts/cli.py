"""
Command line interface for the zscripts toolkit.

Example usage::

    python -m zscripts.cli log-apps --preset python --preset html
    python -m zscripts.cli log-single --preset all
    python -m zscripts.cli tree --output logs/custom_tree.txt
    python -m zscripts.cli build convert
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Sequence

from . import operations


def _paths_as_strings(paths: Iterable[Path]) -> list[str]:
    return [str(path.resolve()) for path in paths]


def _handle_log_apps(args: argparse.Namespace) -> int:
    operations.ensure_log_directories()
    context = operations.ProjectContext.build()

    written: list[Path] = []
    try:
        if args.suffixes:
            if not args.output:
                raise SystemExit("--output is required when using --suffix.")
            destination = Path(args.output)
            written.append(
                operations.generate_app_logs(
                    args.suffixes,
                    destination,
                    context=context,
                )
            )
        else:
            presets = args.preset or ["python"]
            for preset in presets:
                written.append(
                    operations.generate_app_logs_for_preset(
                        preset,
                        context=context,
                    )
                )
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc

    print("Generated app logs:")
    for path in _paths_as_strings(written):
        print(f"  - {path}")
    return 0


def _handle_log_single(args: argparse.Namespace) -> int:
    operations.ensure_log_directories()
    context = operations.ProjectContext.build()

    written: list[Path] = []
    try:
        if args.suffixes:
            if not args.output:
                raise SystemExit("--output is required when using --suffix.")
            destination = Path(args.output)
            written.append(
                operations.consolidate_file_types(
                    args.suffixes,
                    destination,
                    context=context,
                )
            )
        else:
            presets = args.preset or ["python"]
            for preset in presets:
                written.append(
                    operations.consolidate_file_types_for_preset(
                        preset,
                        context=context,
                    )
                )
    except KeyError as exc:
        raise SystemExit(str(exc)) from exc

    print("Created consolidated logs:")
    for path in _paths_as_strings(written):
        print(f"  - {path}")
    return 0


def _handle_tree(args: argparse.Namespace) -> int:
    operations.ensure_log_directories()
    context = operations.ProjectContext.build()
    destination = (
        Path(args.output) if args.output is not None else None
    )
    suffixes = args.suffixes or None

    written = operations.create_tree_snapshot(
        destination=destination,
        file_types=suffixes,
        context=context,
    )
    print(f"Directory tree snapshot written to {written.resolve()}")
    return 0


def _handle_build(args: argparse.Namespace) -> int:
    operations.ensure_log_directories()

    subcommand = args.build_command
    if subcommand == "convert":
        written = operations.convert_work_directory()
        if not written:
            print("No files were converted from the work directory.")
        else:
            print("Converted files:")
            for path in _paths_as_strings(written):
                print(f"  - {path}")
        return 0

    if subcommand == "analyse":
        written = operations.analyse_build_directory()
        if not written:
            print("No analysis files generated (build directory empty?).")
        else:
            print("Analysis logs written:")
            for path in _paths_as_strings(written):
                print(f"  - {path}")
        return 0

    if subcommand == "consolidate":
        results = operations.consolidate_default_directories()
        print("Consolidated outputs:")
        for name, path in results.items():
            print(f"  - {name}: {path.resolve()}")
        return 0

    raise SystemExit(f"Unknown build subcommand: {subcommand}")


def _handle_list_presets(_: argparse.Namespace) -> int:
    presets = operations.list_presets()
    print("Available presets:")
    for name, suffixes in sorted(presets.items()):
        suffix_list = ", ".join(sorted(suffixes))
        print(f"  - {name}: {suffix_list}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convenient CLI for the zscripts toolkit.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # log-apps
    log_apps_parser = subparsers.add_parser(
        "log-apps",
        help="Generate per-app logs for a preset or custom suffix list.",
    )
    log_apps_parser.add_argument(
        "-p",
        "--preset",
        action="append",
        help="Preset(s) to generate. Defaults to 'python'.",
    )
    log_apps_parser.add_argument(
        "-s",
        "--suffix",
        dest="suffixes",
        action="append",
        help="Custom suffix (e.g. .py). Requires --output.",
    )
    log_apps_parser.add_argument(
        "-o",
        "--output",
        help="Directory to store logs when using --suffix.",
    )
    log_apps_parser.set_defaults(func=_handle_log_apps)

    # log-single
    log_single_parser = subparsers.add_parser(
        "log-single",
        help="Consolidate files for a preset or custom suffix list.",
    )
    log_single_parser.add_argument(
        "-p",
        "--preset",
        action="append",
        help="Preset(s) to generate. Defaults to 'python'.",
    )
    log_single_parser.add_argument(
        "-s",
        "--suffix",
        dest="suffixes",
        action="append",
        help="Custom suffix (e.g. .py). Requires --output.",
    )
    log_single_parser.add_argument(
        "-o",
        "--output",
        help="File path for the consolidated output when using --suffix.",
    )
    log_single_parser.set_defaults(func=_handle_log_single)

    # tree
    tree_parser = subparsers.add_parser(
        "tree",
        help="Create a filtered tree snapshot of the repository.",
    )
    tree_parser.add_argument(
        "-o",
        "--output",
        help="Optional explicit file path for the tree snapshot.",
    )
    tree_parser.add_argument(
        "-s",
        "--suffix",
        dest="suffixes",
        action="append",
        help="Optional suffix filter (multiple allowed).",
    )
    tree_parser.set_defaults(func=_handle_tree)

    # build
    build_parser = subparsers.add_parser(
        "build",
        help="Operate on generated build artefacts.",
    )
    build_subparsers = build_parser.add_subparsers(
        dest="build_command",
        required=True,
    )
    build_subparsers.add_parser(
        "convert",
        help="Convert *_files.txt snapshots into Python files.",
    ).set_defaults(func=_handle_build)
    build_subparsers.add_parser(
        "analyse",
        help="Extract symbols from build directory Python files.",
    ).set_defaults(func=_handle_build)
    build_subparsers.add_parser(
        "consolidate",
        help="Concatenate build and analysis outputs.",
    ).set_defaults(func=_handle_build)

    # list-presets
    subparsers.add_parser(
        "list-presets",
        help="List available file-type presets.",
    ).set_defaults(func=_handle_list_presets)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "func", None)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())

