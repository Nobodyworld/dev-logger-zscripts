"""Command line interface for the :mod:`zscripts` toolkit."""

from __future__ import annotations

import argparse
import difflib
import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TextIO, cast

from ._cache import typed_lru_cache
from .config import DEFAULT_CONFIG_PATH, Config, load_config, resolve_paths
from .presets import (
    get_collect_extension_map,
    get_default_collection_logs,
    get_default_single_targets,
    get_single_extension_map,
)
from .utils import (
    CollectionStats,
    ConsolidationStats,
    TreeStats,
    collect_app_logs,
    consolidate_files,
    create_filtered_tree,
    ensure_writable_path,
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

WINDOWS_RESERVED_NAMES: Final[frozenset[str]] = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
WINDOWS_INVALID_CHARS: Final[frozenset[str]] = frozenset('<>:"/\\|?*')

COLLECT_TYPE_EXTENSIONS = get_collect_extension_map()
SINGLE_TYPE_EXTENSIONS = get_single_extension_map()
_DEFAULT_COLLECTION_LOG_NAMES = get_default_collection_logs()
_DEFAULT_SINGLE_TARGET_NAMES = get_default_single_targets()
COLLECT_TYPE_CHOICES = ", ".join(COLLECT_TYPE_EXTENSIONS.keys())
SINGLE_TYPE_CHOICES = ", ".join(SINGLE_TYPE_EXTENSIONS.keys())


BYTES_STEP = 1024.0


def _format_bytes(value: int) -> str:
    """Return *value* in bytes as a human readable string."""

    if value <= 0:
        return "0 B"

    units = ("B", "KiB", "MiB", "GiB", "TiB")
    remainder = float(value)
    for unit in units:
        if remainder < BYTES_STEP or unit == units[-1]:
            if unit == "B":
                return f"{int(remainder)} {unit}"
            return f"{remainder:.1f} {unit}"
        remainder /= BYTES_STEP
    return f"{value} B"


@dataclass(slots=True)
class _CollectTotals:
    files_written: int = 0
    files_skipped: int = 0
    bytes_written: int = 0


@dataclass(slots=True)
class _ConsolidateConfig:
    type_name: str
    project_root: Path
    ignore_patterns: Sequence[str]
    stream_stdout: bool
    target_path: Path | None


@dataclass(slots=True)
class _TreeConfig:
    project_root: Path
    ignore_patterns: Sequence[str]
    include_contents: bool
    max_bytes: int
    stream_stdout: bool
    target_path: Path | None


def _validate_log_filenames(paths: Mapping[str, Path]) -> None:
    """Ensure configured log paths are portable across operating systems."""

    for label, path in paths.items():
        parts = path.parts[1:] if path.is_absolute() else path.parts
        for segment in parts:
            if not segment:
                raise ValueError(f"Log path for '{label}' contains an empty component")
            if segment in {".", ".."}:
                raise ValueError(
                    f"Log path for '{label}' cannot include relative segments like '{segment}'"
                )
            if segment[-1] in {" ", "."}:
                raise ValueError(
                    f"Log path for '{label}' must not end with a space or period: '{segment}'"
                )
            if any(char in WINDOWS_INVALID_CHARS for char in segment):
                raise ValueError(
                    f"Log path for '{label}' contains characters incompatible with Windows: '{segment}'"
                )
            if segment.upper() in WINDOWS_RESERVED_NAMES:
                raise ValueError(f"Log path for '{label}' uses Windows-reserved name '{segment}'")


class UnknownTypeError(ValueError):
    """Raised when an unknown log type is requested."""


class Reporter:
    """Emit user-facing CLI messages in a test-friendly manner."""

    __slots__ = ("_out", "_err")

    def __init__(self, out: TextIO | None = None, err: TextIO | None = None) -> None:
        """Initialise the reporter with optional output streams."""

        self._out: TextIO = out or sys.stdout
        self._err: TextIO = err or sys.stderr

    def info(self, message: str) -> None:
        """Write a single-line informational message to stdout."""

        print(message, file=self._out)

    def detail(self, message: str) -> None:
        """Write a verbose detail line to stdout (used in dry runs)."""

        print(message, file=self._out)

    def success(self, message: str, *, to_stderr: bool = False) -> None:
        """Emit a success notification, optionally redirecting to stderr."""

        stream = self._err if to_stderr else self._out
        print(message, file=stream)

    def warning(self, message: str) -> None:
        """Emit a warning-prefixed message to stderr."""

        print(f"warning: {message}", file=self._err)

    def blank(self) -> None:
        """Print an empty line to stdout to separate message blocks."""

        print(file=self._out)


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
            raise UnknownTypeError(f"Unsupported type '{stripped}'. Choose from {choices}.{hint}")
        if candidate not in seen:
            normalised.append(candidate)
            seen.add(candidate)
    return tuple(normalised)


def _build_log_paths(config: Config, base_dir: Path | None = None) -> dict[str, Path]:
    resolved = resolve_paths(config)
    root = base_dir or resolved.log_dir
    logs = config.collection_logs
    paths = {
        key: root / logs.get(key, _DEFAULT_COLLECTION_LOG_NAMES[key])
        for key in _DEFAULT_COLLECTION_LOG_NAMES
    }
    _validate_log_filenames(paths)
    return paths


def _build_single_targets(config: Config, base_dir: Path | None = None) -> dict[str, Path]:
    resolved = resolve_paths(config)
    root = base_dir or resolved.single_log_dir.parent
    single_dir = root / config.collection_logs.get(
        "single", _DEFAULT_COLLECTION_LOG_NAMES["single"]
    )
    targets = config.single_targets
    paths = {
        key: single_dir / targets.get(key, _DEFAULT_SINGLE_TARGET_NAMES[key])
        for key in _DEFAULT_SINGLE_TARGET_NAMES
    }
    _validate_log_filenames(paths)
    return paths


def _resolve_consolidate_allowed_root(
    output_dir_arg: str | None,
    output_arg: str | None,
    config: Config,
    output_base: Path | None,
) -> Path | None:
    if output_dir_arg:
        return output_base
    if output_arg:
        return None
    return resolve_paths(config).single_log_dir


@typed_lru_cache(maxsize=64)
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


def _auto_detect_repository_root(start: Path) -> Path | None:
    for candidate in (start,) + tuple(start.parents):
        git_dir = candidate / ".git"
        pyproject = candidate / "pyproject.toml"
        if git_dir.is_dir() or pyproject.is_file():
            return candidate
    return None


def _resolve_project_root(raw_root: str | None, *, sample: bool) -> Path:
    if sample:
        project_root = SCRIPT_DIR.parent / "sample_project"
        return project_root.resolve()

    raw_display = raw_root if raw_root is not None else "."
    candidate = Path(raw_display).expanduser()
    resolved_candidate = candidate.resolve()
    if not resolved_candidate.exists():
        raise FileNotFoundError(
            f"Project root does not exist: {raw_display} (resolved to {resolved_candidate})"
        )

    if raw_root in (None, "", "."):
        detected = _auto_detect_repository_root(resolved_candidate)
        if detected is not None:
            LOGGER.info(
                "event=project_root_detected original=%s resolved=%s detected=%s",
                raw_display,
                resolved_candidate,
                detected,
            )
            return detected

    return resolved_candidate


def _collect_dry_run(
    type_names: Sequence[str],
    project_root: Path,
    log_paths: Mapping[str, Path],
    ignore_patterns: Sequence[str],
    reporter: Reporter,
) -> None:
    for type_name in type_names:
        log_dir = log_paths[type_name]
        grouped = group_source_files_by_app(
            project_root,
            COLLECT_TYPE_EXTENSIONS[type_name],
            ignore_patterns,
        )
        LOGGER.info("event=collect_planned type=%s output=%s", type_name, log_dir)
        reporter.info(f"• {type_name} -> {log_dir}")
        if not grouped:
            reporter.detail("  - No matching files found")
            continue
        for app_name, files in grouped.items():
            reporter.detail(f"  - [{app_name}] ({len(files)} files)")
            for relative_path in files:
                reporter.detail(f"    · {relative_path.as_posix()}")
                # TODO - Show file size metadata to estimate log volume upfront.

    reporter.blank()
    reporter.info("📝 Dry run complete. No files were written.")


def _collect_execute(
    type_names: Sequence[str],
    project_root: Path,
    log_paths: Mapping[str, Path],
    ignore_patterns: Sequence[str],
    reporter: Reporter,
) -> _CollectTotals:
    totals = _CollectTotals()
    for type_name in type_names:
        log_dir = log_paths[type_name]
        log_dir.mkdir(parents=True, exist_ok=True)
        stats: CollectionStats = collect_app_logs(
            project_root,
            log_dir,
            COLLECT_TYPE_EXTENSIONS[type_name],
            ignore_patterns,
        )
        LOGGER.info(
            "event=collect_completed type=%s output=%s files=%d skipped=%d bytes=%d",
            type_name,
            log_dir,
            stats.files_written,
            stats.files_skipped,
            stats.bytes_written,
        )
        details = [f"{stats.files_written} files"]
        if stats.files_skipped:
            details.append(f"{stats.files_skipped} skipped")
        details.append(f"{_format_bytes(stats.bytes_written)}")
        reporter.success(
            f"✓ Created {type_name} logs at {log_dir} ({', '.join(details)})"
        )
        totals.files_written += stats.files_written
        totals.files_skipped += stats.files_skipped
        totals.bytes_written += stats.bytes_written

    return totals


def _consolidate_dry_run(config: _ConsolidateConfig, reporter: Reporter) -> None:
    planned = list_matching_source_files(
        config.project_root,
        SINGLE_TYPE_EXTENSIONS[config.type_name],
        config.ignore_patterns,
    )
    LOGGER.info(
        "event=consolidate_planned type=%s output=%s",
        config.type_name,
        config.target_path or "-",
    )
    target_display = "stdout" if config.stream_stdout else config.target_path
    reporter.info(f"Dry run: would consolidate {len(planned)} files into {target_display}")
    for relative_path in planned:
        reporter.detail(f"  - {relative_path.as_posix()}")
    if not planned:
        reporter.detail("  (no matching files found)")
    # TODO - Return a non-zero exit code when dry-run detects unresolved issues.


def _consolidate_stream(config: _ConsolidateConfig, reporter: Reporter) -> None:
    LOGGER.info("event=consolidate_stream type=%s", config.type_name)
    files_written = 0
    files_skipped = 0
    bytes_written = 0
    for relative_path in list_matching_source_files(
        config.project_root,
        SINGLE_TYPE_EXTENSIONS[config.type_name],
        config.ignore_patterns,
    ):
        file_path = config.project_root / relative_path
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            LOGGER.warning(
                "event=consolidate_skipped error_id=FS002 file=%s reason=%s",
                file_path,
                exc,
            )
            files_skipped += 1
            continue
        entry = f"# {relative_path.as_posix()}\n{content}\n\n"
        print(entry, end="")
        files_written += 1
        bytes_written += len(entry.encode())
    LOGGER.info(
        "event=consolidate_stream_completed type=%s files=%d skipped=%d bytes=%d",
        config.type_name,
        files_written,
        files_skipped,
        bytes_written,
    )
    details = [f"{files_written} files"]
    if files_skipped:
        details.append(f"{files_skipped} skipped")
    details.append(f"{_format_bytes(bytes_written)}")
    reporter.success(
        f"✓ Consolidated {config.type_name} sources to stdout ({', '.join(details)})",
        to_stderr=True,
    )


def _consolidate_to_file(
    config: _ConsolidateConfig,
    allowed_root: Path | None,
    reporter: Reporter,
) -> None:
    if config.target_path is None:
        raise RuntimeError("Output path was not resolved for consolidate command")
    output_resolved = ensure_writable_path(config.target_path, allowed_root=allowed_root)
    # TODO - Clean up orphaned directories when consolidation is interrupted mid-run.
    stats: ConsolidationStats = consolidate_files(
        config.project_root,
        output_resolved,
        SINGLE_TYPE_EXTENSIONS[config.type_name],
        config.ignore_patterns,
    )
    LOGGER.info(
        "event=consolidate_completed type=%s output=%s files=%d skipped=%d bytes=%d",
        config.type_name,
        output_resolved,
        stats.files_written,
        stats.files_skipped,
        stats.bytes_written,
    )
    details = [f"{stats.files_written} files"]
    if stats.files_skipped:
        details.append(f"{stats.files_skipped} skipped")
    details.append(f"{_format_bytes(stats.bytes_written)}")
    reporter.success(
        f"✓ Consolidated {config.type_name} sources into {output_resolved} ({', '.join(details)})"
    )
    if stats.files_skipped:
        reporter.warning(
            "Some files were skipped during consolidation due to read errors; review logs."
        )


def _tree_dry_run(config: _TreeConfig, reporter: Reporter) -> None:
    LOGGER.info("event=tree_planned output=%s", config.target_path or "-")
    target_display = "stdout" if config.stream_stdout else config.target_path
    reporter.info(f"Dry run: would write project tree to {target_display}")
    preview_lines = 0
    preview_bytes = 0
    for line in iter_filtered_tree_lines(
        config.project_root,
        config.ignore_patterns,
        include_content=config.include_contents,
        max_bytes=config.max_bytes,
    ):
        reporter.detail(line)
        preview_lines += 1
        preview_bytes += len(f"{line}\n".encode())
    reporter.info(
        f"Preview summary: {preview_lines} lines (~{_format_bytes(preview_bytes)})"
    )


def _tree_stream(config: _TreeConfig, reporter: Reporter) -> None:
    LOGGER.info("event=tree_stream")
    lines_emitted = 0
    bytes_written = 0
    for line in iter_filtered_tree_lines(
        config.project_root,
        config.ignore_patterns,
        include_content=config.include_contents,
        max_bytes=config.max_bytes,
    ):
        print(line)
        lines_emitted += 1
        bytes_written += len(f"{line}\n".encode())
    reporter.success(
        f"✓ Wrote project tree to stdout ({lines_emitted} lines, {_format_bytes(bytes_written)})",
        to_stderr=True,
    )


def _tree_write(
    config: _TreeConfig,
    allowed_root: Path | None,
    reporter: Reporter,
) -> None:
    if config.target_path is None:
        raise RuntimeError("Output path was not resolved for tree command")
    resolved_output = ensure_writable_path(config.target_path, allowed_root=allowed_root)
    stats: TreeStats = create_filtered_tree(
        config.project_root,
        resolved_output,
        config.ignore_patterns,
        include_content=config.include_contents,
        max_bytes=config.max_bytes,
    )
    LOGGER.info(
        "event=tree_completed output=%s lines=%d bytes=%d",
        resolved_output,
        stats.lines_emitted,
        stats.bytes_written,
    )
    reporter.success(
        f"✓ Wrote project tree to {resolved_output} ({stats.lines_emitted} lines,"
        f" {_format_bytes(stats.bytes_written)})"
    )


def collect_command(args: argparse.Namespace) -> None:
    config_arg = cast(Path | str | None, getattr(args, "config", None))
    project_root_arg = cast(str | None, getattr(args, "project_root", None))
    types_arg = cast(str, getattr(args, "types", "python"))
    output_dir_arg = cast(str | None, getattr(args, "output_dir", None))
    sample_flag = cast(bool, getattr(args, "sample", False))
    dry_run = cast(bool, getattr(args, "dry_run", False))

    reporter = Reporter()
    LOGGER.info("event=collect start project_root=%s", project_root_arg)
    config = load_config(config_arg)
    type_names = _parse_type_list(types_arg, allowed=COLLECT_TYPE_EXTENSIONS)
    if not type_names:
        type_names = ("python",)
        reporter.warning("No types provided; defaulting to 'python'.")

    project_root = _resolve_project_root(project_root_arg, sample=sample_flag)
    output_base = Path(output_dir_arg).expanduser().resolve() if output_dir_arg else None

    # TODO - Cache log path calculations when invoked repeatedly within same process.
    log_paths = _build_log_paths(config, output_base)
    base_output_dir = next(iter(log_paths.values())).parent
    ignore_patterns = _augment_ignore_patterns(project_root, config)

    # TODO - Emit periodic progress updates for long scans to reassure users.
    reporter.info(f"Scanning project: {project_root}")
    reporter.info(f"Output directory: {base_output_dir}")
    if dry_run:
        reporter.info("Dry run enabled: no files will be written.")
        _collect_dry_run(type_names, project_root, log_paths, ignore_patterns, reporter)
        return

    totals = _collect_execute(type_names, project_root, log_paths, ignore_patterns, reporter)
    reporter.info(
        f"Summary: {totals.files_written} files captured"
        f" ({_format_bytes(totals.bytes_written)})"
    )
    if totals.files_skipped:
        reporter.warning(
            f"Skipped {totals.files_skipped} files due to read errors (see logs for details)."
        )
    reporter.blank()
    reporter.success(f"📁 View logs at: {base_output_dir}")


def consolidate_command(args: argparse.Namespace) -> None:
    config_arg = cast(Path | str | None, getattr(args, "config", None))
    project_root_arg = cast(str | None, getattr(args, "project_root", None))
    types_arg = cast(str, getattr(args, "types", "python"))
    output_dir_arg = cast(str | None, getattr(args, "output_dir", None))
    output_arg = cast(str | None, getattr(args, "output", None))
    sample_flag = cast(bool, getattr(args, "sample", False))
    dry_run = cast(bool, getattr(args, "dry_run", False))

    reporter = Reporter()
    LOGGER.info("event=consolidate start project_root=%s", project_root_arg)
    config = load_config(config_arg)
    type_names = _parse_type_list(types_arg, allowed=SINGLE_TYPE_EXTENSIONS)
    if not type_names:
        reporter.warning("No types provided; defaulting to 'python'.")
        type_names = ("python",)
    if len(type_names) != 1:
        raise UnknownTypeError("Consolidate command accepts a single type value")

    type_name = type_names[0]
    project_root = _resolve_project_root(project_root_arg, sample=sample_flag)

    output_base = Path(output_dir_arg).expanduser().resolve() if output_dir_arg else None
    targets = _build_single_targets(config, output_base)

    stream_stdout = output_arg == "-"
    output_path = (
        None
        if stream_stdout
        else Path(output_arg).expanduser().resolve()
        if output_arg
        else targets[type_name]
    )
    # TODO - Warn when output_path resides outside of the configured log directory.
    ignore_patterns = _augment_ignore_patterns(project_root, config)
    consolidate_ctx = _ConsolidateConfig(
        type_name=type_name,
        project_root=project_root,
        ignore_patterns=tuple(ignore_patterns),
        stream_stdout=stream_stdout,
        target_path=output_path,
    )
    if dry_run:
        _consolidate_dry_run(consolidate_ctx, reporter)
        return

    if stream_stdout:
        _consolidate_stream(consolidate_ctx, reporter)
        return

    if output_path is None:
        raise RuntimeError("Output path was not resolved for consolidate command")
    allowed_root = _resolve_consolidate_allowed_root(
        output_dir_arg, output_arg, config, output_base
    )
    _consolidate_to_file(consolidate_ctx, allowed_root, reporter)
    # TODO - Offer to open the generated log automatically when running interactively.


def tree_command(args: argparse.Namespace) -> None:
    config_arg = cast(Path | str | None, getattr(args, "config", None))
    project_root_arg = cast(str | None, getattr(args, "project_root", None))
    output_dir_arg = cast(str | None, getattr(args, "output_dir", None))
    output_arg = cast(str | None, getattr(args, "output", None))
    include_contents = cast(bool, getattr(args, "include_contents", False))
    max_bytes = cast(int, getattr(args, "max_bytes", 4096))
    sample_flag = cast(bool, getattr(args, "sample", False))
    dry_run = cast(bool, getattr(args, "dry_run", False))

    reporter = Reporter()
    LOGGER.info("event=tree start project_root=%s", project_root_arg)
    config = load_config(config_arg)
    project_root = _resolve_project_root(project_root_arg, sample=sample_flag)

    stream_stdout = False
    allowed_root: Path | None = None
    if output_dir_arg:
        output_base = Path(output_dir_arg).expanduser().resolve()
        output_path: Path | None = output_base / "project_tree.txt"
        allowed_root = output_base
    elif output_arg:
        if output_arg == "-":
            stream_stdout = True
            output_path = None
        else:
            output_path = Path(output_arg).expanduser().resolve()
            allowed_root = None
    else:
        default_base = resolve_paths(config).log_dir
        output_path = default_base / "project_tree.txt"
        allowed_root = default_base
    # TODO - Validate that output_path is writable before starting the traversal.

    ignore_patterns = _augment_ignore_patterns(project_root, config)
    tree_ctx = _TreeConfig(
        project_root=project_root,
        ignore_patterns=tuple(ignore_patterns),
        include_contents=include_contents,
        max_bytes=max_bytes,
        stream_stdout=stream_stdout,
        target_path=output_path,
    )
    # TODO - Allow include/exclude filters to be provided at runtime for tree snapshots.
    # TODO - Offer machine-readable output (JSON/NDJSON) alongside the text tree view.
    if dry_run:
        _tree_dry_run(tree_ctx, reporter)
        return

    if stream_stdout:
        _tree_stream(tree_ctx, reporter)
        return

    if output_path is None:
        raise RuntimeError("Output path was not resolved for tree command")
    _tree_write(tree_ctx, allowed_root, reporter)
    # TODO - Provide guidance for piping output directly to stdout for scripting.


def _add_shared_arguments(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "--config",
        default=None,
        help=f"Path to a zscripts configuration file (default: {DEFAULT_CONFIG_PATH})",
    )
    subparser.add_argument(
        "--project-root",
        default=None,
        help="Root directory to scan (default: auto-detect from current directory)",
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
        help=(f"Comma separated list of stacks to capture (choices: {COLLECT_TYPE_CHOICES})"),
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
        help=(f"Select the source stack to consolidate (choices: {SINGLE_TYPE_CHOICES})"),
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
