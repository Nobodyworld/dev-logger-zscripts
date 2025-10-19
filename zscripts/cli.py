"""Command line interface for the :mod:`zscripts` toolkit."""

from __future__ import annotations

import argparse
import difflib
import functools
import logging
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import cast

from .config import DEFAULT_CONFIG_PATH, Config, load_config, resolve_paths
from .utils import (
    collect_app_logs,
    consolidate_files,
    create_filtered_tree,
    group_source_files_by_app,
    iter_filtered_tree_lines,
    list_matching_source_files,
    load_gitignore_patterns,
)

SCRIPT_DIR = Path(__file__).resolve().parent
LOGGER = logging.getLogger("zscripts.cli")
ERROR_ID_UNKNOWN_TYPE = "CLI001"
ERROR_ID_PROJECT_ROOT = "CLI002"
ERROR_ID_RUNTIME = "CLI999"

JAVASCRIPT_EXTENSIONS = (
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".mts",
    ".cts",
)


def _normalise_extensions(source: Mapping[str, Iterable[str]]) -> dict[str, frozenset[str]]:
    return {key: frozenset(ext.lower() for ext in value) for key, value in source.items()}


_BASE_EXTENSION_PRESETS = {
    "python": (".py",),
    "html": (".html",),
    "css": (".css",),
    "js": JAVASCRIPT_EXTENSIONS,
    "python_html": (".py", ".html"),
}

_NORMALISED_BASE_PRESETS = _normalise_extensions(_BASE_EXTENSION_PRESETS)

COLLECT_TYPE_EXTENSIONS = dict(_NORMALISED_BASE_PRESETS)
COLLECT_TYPE_EXTENSIONS["all"] = frozenset().union(*COLLECT_TYPE_EXTENSIONS.values())

SINGLE_TYPE_EXTENSIONS = dict(_NORMALISED_BASE_PRESETS)
SINGLE_TYPE_EXTENSIONS["any"] = COLLECT_TYPE_EXTENSIONS["all"]


class UnknownTypeError(ValueError):
    """Raised when an unknown log type is requested."""


def _parse_type_list(raw: str, *, allowed: Mapping[str, frozenset[str]]) -> tuple[str, ...]:
    """Normalise and validate a comma separated list of type names.

    The CLI historically accepted only lower-case identifiers exactly matching the
    keys in *allowed*. This function now treats the input as case-insensitive and
    silently de-duplicates repeated values while preserving the order of first
    appearance. These small affordances make the CLI more forgiving when users
    supply values manually or via environment variables.
    """

    normalised: list[str] = []
    seen: set[str] = set()
    for value in raw.split(","):
        stripped = value.strip()
        if not stripped:
            continue
        candidate = stripped.lower()
        if candidate not in allowed:
            suggestions = difflib.get_close_matches(candidate, allowed.keys(), n=1)
            hint = f" Did you mean '{suggestions[0]}'?" if suggestions else ""
            choices = ", ".join(sorted(allowed))
            raise UnknownTypeError(
                f"Unsupported type '{stripped}'. Choose from {choices}.{hint}"
            )
        if candidate not in seen:
            normalised.append(candidate)
            seen.add(candidate)
    return tuple(normalised)


def _build_log_paths(config: Config, base_dir: Path | None = None) -> dict[str, Path]:
    resolved = resolve_paths(config)
    root = base_dir or resolved.log_dir
    logs = config.collection_logs
    # TODO - Validate configured log filenames to flag characters invalid on Windows.
    return {
        "all": root / logs.get("all", "logs_apps_all"),
        "python": root / logs.get("python", "logs_apps_pyth"),
        "html": root / logs.get("html", "logs_apps_html"),
        "css": root / logs.get("css", "logs_apps_css"),
        "js": root / logs.get("js", "logs_apps_js"),
        "python_html": root / logs.get("python_html", "logs_apps_both"),
        "single": root / logs.get("single", "logs_single_files"),
    }


def _build_single_targets(config: Config, base_dir: Path | None = None) -> dict[str, Path]:
    resolved = resolve_paths(config)
    root = base_dir or resolved.single_log_dir.parent
    single_dir = root / config.collection_logs.get("single", "logs_single_files")
    targets = config.single_targets
    # TODO - Consolidate target naming with COLLECT_TYPE_EXTENSIONS for shared typing.
    return {
        "python": single_dir / targets.get("python", "capture_all_pyth.txt"),
        "html": single_dir / targets.get("html", "capture_all_html.txt"),
        "css": single_dir / targets.get("css", "capture_all_css.txt"),
        "js": single_dir / targets.get("js", "capture_all_js.txt"),
        "python_html": single_dir / targets.get("python_html", "capture_all_python_html.txt"),
        "any": single_dir / targets.get("any", "capture_all.txt"),
    }


@functools.lru_cache(maxsize=64)
def _augment_ignore_patterns_cached(
    project_root: Path, skip: tuple[str, ...], user_patterns: tuple[str, ...]
) -> tuple[str, ...]:
    return tuple(
        load_gitignore_patterns(
            project_root,
            skip_dirs=skip,
            user_ignore_patterns=user_patterns,
        )
    )


def _augment_ignore_patterns(project_root: Path, config: Config) -> list[str]:
    sorted_user_patterns = tuple(sorted(config.user_ignore_patterns))
    return list(
        _augment_ignore_patterns_cached(project_root.resolve(), config.skip, sorted_user_patterns)
    )


def _resolve_project_root(raw_root: str, *, sample: bool) -> Path:
    if sample:
        project_root = SCRIPT_DIR.parent / "sample_project"
    else:
        project_root = Path(raw_root).expanduser()

    # TODO - Preserve the original user input in error messages for clarity.
    resolved = project_root.resolve()
    if not resolved.exists():
        raise FileNotFoundError(
            f"Project root does not exist: {raw_root} (resolved to {resolved})"
        )
    # TODO - Detect repository root automatically when project_root is omitted.
    return resolved


def collect_command(args: argparse.Namespace) -> None:
    config_arg = cast(Path | str | None, getattr(args, "config", None))
    project_root_arg = cast(str, getattr(args, "project_root", "."))
    types_arg = cast(str, getattr(args, "types", "python"))
    output_dir_arg = cast(str | None, getattr(args, "output_dir", None))
    sample_flag = cast(bool, getattr(args, "sample", False))
    dry_run = cast(bool, getattr(args, "dry_run", False))

    LOGGER.info("event=collect start project_root=%s", project_root_arg)
    config = load_config(config_arg)
    type_names = _parse_type_list(types_arg, allowed=COLLECT_TYPE_EXTENSIONS)
    if not type_names:
        type_names = ("python",)
        # TODO - Emit a warning when fallbacks override an empty --types argument.

    project_root = _resolve_project_root(project_root_arg, sample=sample_flag)
    output_base = Path(output_dir_arg).expanduser().resolve() if output_dir_arg else None

    # TODO - Cache log path calculations when invoked repeatedly within same process.
    log_paths = _build_log_paths(config, output_base)
    base_output_dir = next(iter(log_paths.values())).parent
    ignore_patterns = _augment_ignore_patterns(project_root, config)

    # TODO - Route user-facing output through a reporter abstraction for testability.
    # TODO - Emit periodic progress updates for long scans to reassure users.
    print(f"Scanning project: {project_root}")
    print(f"Output directory: {base_output_dir}")
    if dry_run:
        print("Dry run enabled: no files will be written.\n")
        # TODO - Provide JSON output for dry-run details to enable scripting hooks.

    for type_name in type_names:
        log_dir = log_paths[type_name]
        if dry_run:
            grouped = group_source_files_by_app(
                project_root,
                COLLECT_TYPE_EXTENSIONS[type_name],
                ignore_patterns,
            )
            LOGGER.info("event=collect_planned type=%s output=%s", type_name, log_dir)
            print(f"• {type_name} -> {log_dir}")
            if not grouped:
                print("  - No matching files found")
            else:
                for app_name, files in grouped.items():
                    print(f"  - [{app_name}] ({len(files)} files)")
                    for relative_path in files:
                        print(f"    · {relative_path.as_posix()}")
                        # TODO - Show file size metadata to estimate log volume upfront.
            continue

        log_dir.mkdir(parents=True, exist_ok=True)
        # TODO - Reset target directories when stale files from previous runs are detected.
        collect_app_logs(
            project_root,
            log_dir,
            COLLECT_TYPE_EXTENSIONS[type_name],
            ignore_patterns,
        )
        LOGGER.info("event=collect_completed type=%s output=%s", type_name, log_dir)
        print(f"✓ Created {type_name} logs at {log_dir}")

    if dry_run:
        print(f"\n📝 Dry run complete. Planned logs directory: {base_output_dir}")
        return

    print(f"\n📁 View logs at: {base_output_dir}")


def consolidate_command(args: argparse.Namespace) -> None:
    config_arg = cast(Path | str | None, getattr(args, "config", None))
    project_root_arg = cast(str, getattr(args, "project_root", "."))
    types_arg = cast(str, getattr(args, "types", "python"))
    output_dir_arg = cast(str | None, getattr(args, "output_dir", None))
    output_arg = cast(str | None, getattr(args, "output", None))
    sample_flag = cast(bool, getattr(args, "sample", False))
    dry_run = cast(bool, getattr(args, "dry_run", False))

    LOGGER.info("event=consolidate start project_root=%s", project_root_arg)
    config = load_config(config_arg)
    type_names = _parse_type_list(types_arg, allowed=SINGLE_TYPE_EXTENSIONS)
    if len(type_names) != 1:
        raise UnknownTypeError("Consolidate command accepts a single type value")

    type_name = type_names[0] if type_names else "python"
    project_root = _resolve_project_root(project_root_arg, sample=sample_flag)

    output_base = Path(output_dir_arg).expanduser().resolve() if output_dir_arg else None
    targets = _build_single_targets(config, output_base)

    stream_stdout = output_arg == "-"
    output_path = (
        None
        if stream_stdout
        else Path(output_arg).expanduser().resolve() if output_arg else targets[type_name]
    )
    # TODO - Warn when output_path resides outside of the configured log directory.
    ignore_patterns = _augment_ignore_patterns(project_root, config)
    if dry_run:
        planned = list_matching_source_files(
            project_root,
            SINGLE_TYPE_EXTENSIONS[type_name],
            ignore_patterns,
        )
        LOGGER.info("event=consolidate_planned type=%s output=%s", type_name, output_path or "-")
        target_display = "stdout" if stream_stdout else output_path
        print(f"Dry run: would consolidate {len(planned)} files into {target_display}")
        for relative_path in planned:
            print(f"  - {relative_path.as_posix()}")
        if not planned:
            print("  (no matching files found)")
        # TODO - Return a non-zero exit code when dry-run detects unresolved issues.
        return

    if stream_stdout:
        LOGGER.info("event=consolidate_stream type=%s", type_name)
        for relative_path in list_matching_source_files(
            project_root,
            SINGLE_TYPE_EXTENSIONS[type_name],
            ignore_patterns,
        ):
            file_path = project_root / relative_path
            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError) as exc:
                LOGGER.warning(
                    "event=consolidate_skipped error_id=FS002 file=%s reason=%s",
                    file_path,
                    exc,
                )
                continue
            print(f"# {relative_path.as_posix()}")
            print(content)
            print()
        print(f"✓ Consolidated {type_name} sources to stdout", file=sys.stderr)
        return

    assert output_path is not None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # TODO - Clean up orphaned directories when consolidation is interrupted mid-run.
    consolidate_files(
        project_root,
        output_path,
        SINGLE_TYPE_EXTENSIONS[type_name],
        ignore_patterns,
    )
    LOGGER.info("event=consolidate_completed type=%s output=%s", type_name, output_path)
    print(f"✓ Consolidated {type_name} sources into {output_path}")
    # TODO - Offer to open the generated log automatically when running interactively.


def tree_command(args: argparse.Namespace) -> None:
    config_arg = cast(Path | str | None, getattr(args, "config", None))
    project_root_arg = cast(str, getattr(args, "project_root", "."))
    output_dir_arg = cast(str | None, getattr(args, "output_dir", None))
    output_arg = cast(str | None, getattr(args, "output", None))
    include_contents = cast(bool, getattr(args, "include_contents", False))
    max_bytes = cast(int, getattr(args, "max_bytes", 4096))
    sample_flag = cast(bool, getattr(args, "sample", False))
    dry_run = cast(bool, getattr(args, "dry_run", False))

    LOGGER.info("event=tree start project_root=%s", project_root_arg)
    config = load_config(config_arg)
    project_root = _resolve_project_root(project_root_arg, sample=sample_flag)

    stream_stdout = False
    if output_dir_arg:
        output_base = Path(output_dir_arg).expanduser().resolve()
        output_path: Path | None = output_base / "project_tree.txt"
    elif output_arg:
        if output_arg == "-":
            stream_stdout = True
            output_path = None
        else:
            output_path = Path(output_arg).expanduser().resolve()
    else:
        default_base = next(iter(_build_log_paths(config).values())).parent
        output_path = default_base / "project_tree.txt"
    # TODO - Validate that output_path is writable before starting the traversal.

    ignore_patterns = _augment_ignore_patterns(project_root, config)
    # TODO - Allow include/exclude filters to be provided at runtime for tree snapshots.
    # TODO - Offer machine-readable output (JSON/NDJSON) alongside the text tree view.
    if dry_run:
        LOGGER.info("event=tree_planned output=%s", output_path or "-")
        target_display = "stdout" if stream_stdout else output_path
        print(f"Dry run: would write project tree to {target_display}")
        for line in iter_filtered_tree_lines(
            project_root,
            ignore_patterns,
            include_content=include_contents,
            max_bytes=max_bytes,
        ):
            print(line)
        # TODO - Display a summary of ignored paths during dry-run previews.
        return

    if stream_stdout:
        LOGGER.info("event=tree_stream")
        for line in iter_filtered_tree_lines(
            project_root,
            ignore_patterns,
            include_content=include_contents,
            max_bytes=max_bytes,
        ):
            print(line)
        print("✓ Wrote project tree to stdout", file=sys.stderr)
        return

    assert output_path is not None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    create_filtered_tree(
        project_root,
        output_path,
        ignore_patterns,
        include_content=include_contents,
        max_bytes=max_bytes,
    )
    LOGGER.info("event=tree_completed output=%s", output_path)
    print(f"✓ Wrote project tree to {output_path}")
    # TODO - Provide guidance for piping output directly to stdout for scripting.


def _add_shared_arguments(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--config",
        default=None,
        help=f"Path to a zscripts configuration file (default: {DEFAULT_CONFIG_PATH})",
    )
    subparser.add_argument(
        "--project-root",
        default=".",
        help="Root directory to scan (default: current directory)",
    )
    subparser.add_argument(
        "--output-dir",
        default=None,
        help="Custom output directory for logs (default: configuration log root)",
    )
    subparser.add_argument(
        "--sample",
        action="store_true",
        help="Run against the included sample project",
    )
    subparser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without writing any files",
    )
    subparser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging for troubleshooting",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI front-end for zscripts utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)
    # TODO - Auto-register commands via entry points to support external plugins.

    collect_parser = subparsers.add_parser(
        "collect", help="Generate per-app logs for selected stacks"
    )
    _add_shared_arguments(collect_parser)
    collect_parser.add_argument(
        "--types",
        default="python",
        help="Comma separated list of stacks to capture (choices: python, html, css, js, python_html, all)",
    )
    # TODO - Provide shell completion scripts for --types argument values.
    collect_parser.set_defaults(func=collect_command)

    consolidate_parser = subparsers.add_parser(
        "consolidate", help="Create a single consolidated log file"
    )
    _add_shared_arguments(consolidate_parser)
    consolidate_parser.add_argument(
        "--types",
        default="python",
        help="Select the source stack to consolidate (choices: python, html, css, js, python_html, any)",
    )
    consolidate_parser.add_argument(
        "--output",
        help="Optional custom output path for the consolidated log",
    )
    # TODO - Support --append flag to accumulate new snapshots instead of overwriting.
    # TODO - Add --encoding option for writing logs with alternative character sets.
    consolidate_parser.set_defaults(func=consolidate_command)

    tree_parser = subparsers.add_parser(
        "tree", help="Snapshot the project tree with filtered sources"
    )
    _add_shared_arguments(tree_parser)
    tree_parser.add_argument(
        "--output",
        help="Optional custom output file for the tree snapshot",
    )
    tree_parser.add_argument(
        "--include-contents",
        action="store_true",
        help="Include file contents in the tree output",
    )
    tree_parser.add_argument(
        "--max-bytes",
        type=int,
        default=4096,
        help="Maximum number of bytes to read per file when including contents",
    )
    tree_parser.set_defaults(func=tree_command)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    verbose_flag = cast(bool, getattr(args, "verbose", False))
    log_level = logging.INFO if verbose_flag else logging.WARNING
    # TODO - Switch to structured logging to ease downstream ingestion.
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger().setLevel(log_level)
    # TODO - Allow configuring log destinations (file/syslog) via CLI flags.

    command = cast(str, getattr(args, "command", ""))
    handler: Callable[[argparse.Namespace], None] | None = getattr(args, "func", None)
    if handler is None:
        parser.error("No command specified")

    try:
        handler(args)
    except UnknownTypeError as exc:
        LOGGER.error(
            "event=cli_error error_id=%s command=%s reason=%s",
            ERROR_ID_UNKNOWN_TYPE,
            command,
            exc,
        )
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        LOGGER.error(
            "event=cli_error error_id=%s command=%s reason=%s",
            ERROR_ID_PROJECT_ROOT,
            command,
            exc,
        )
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        LOGGER.error(
            "event=cli_error error_id=%s command=%s reason=%s",
            ERROR_ID_RUNTIME,
            command,
            exc,
        )
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        LOGGER.error(
            "event=cli_error error_id=%s command=%s reason=%s",
            ERROR_ID_RUNTIME,
            command,
            exc,
        )
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        LOGGER.exception("event=cli_error error_id=%s command=%s", ERROR_ID_RUNTIME, command)
        print(f"os error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
