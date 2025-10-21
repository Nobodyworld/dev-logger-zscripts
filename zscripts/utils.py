"""Filesystem utilities used by :mod:`zscripts` commands."""

from __future__ import annotations

import fnmatch
import logging
import os
import re
import warnings
from collections.abc import Callable, Collection, Iterable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TextIO

from ._cache import typed_lru_cache
from .config import Config, get_config

_WINDOWS = os.name == "nt"


class InvalidIgnorePatternError(ValueError):
    """Raised when an ignore pattern cannot be compiled."""


@typed_lru_cache(maxsize=256)
def _compile_pattern(pattern: str, *, case_sensitive: bool) -> re.Pattern[str]:
    flags = 0 if case_sensitive else re.IGNORECASE
    translated = fnmatch.translate(pattern)
    try:
        return re.compile(translated, flags)
    except re.error as exc:  # pragma: no cover - exercised via tests with monkeypatch
        raise InvalidIgnorePatternError(
            f"Invalid ignore pattern '{pattern}': {exc.msg if hasattr(exc, 'msg') else exc}"
        ) from exc


class IgnoreMatcher:
    """Match relative paths against glob-style ignore patterns."""

    def __init__(self, patterns: Iterable[str], *, case_sensitive: bool | None = None) -> None:
        self._case_sensitive = case_sensitive if case_sensitive is not None else not _WINDOWS
        compiled: list[tuple[str, re.Pattern[str], bool]] = []
        for pattern in patterns:
            raw = pattern.strip()
            if not raw:
                continue
            is_negated = raw.startswith("!")
            candidate = raw[1:] if is_negated else raw
            regex = _compile_pattern(candidate, case_sensitive=self._case_sensitive)
            compiled.append((candidate, regex, is_negated))
        self._compiled: Final = compiled

    def matches(self, path: Path | str) -> bool:
        """Return ``True`` if *path* matches any configured ignore pattern."""

        candidate_path = Path(path)
        candidate = candidate_path.as_posix()
        if not self._case_sensitive:
            candidate = candidate.casefold()

        matched = False
        for _, regex, is_negated in self._compiled:
            if regex.match(candidate):
                matched = not is_negated
        return matched


LOGGER = logging.getLogger("zscripts.utils")


BASE_IGNORE_PATTERNS: Final[set[str]] = {
    "*.pyc",
    "__pycache__/",
    ".DS_Store",
    "*.sqlite3",
    "db.sqlite3",
    "/staticfiles/",
    "/media/",
    "error.dev.log",
    "error.base.log",
    "error.test.log",
    "error.prod.log",
    "logs",
    "logs/",
    "zscripts",
    "zscripts/",
    "static/",
    "staticfiles/",
    "migrations/",
    "migrations",
    "node_modules/",
    "yarn-error.log",
    "yarn-debug.log",
    "yarn.lock",
    "package-lock.json",
    "package.json",
    "zbuild",
    "zbuild/",
}


_BYTE_UNITS: Final[tuple[str, ...]] = ("B", "KiB", "MiB", "GiB", "TiB")


def format_bytes(value: int) -> str:
    """Return *value* expressed using binary prefixes."""

    if value <= 0:
        return "0 B"

    remainder = float(value)
    for unit in _BYTE_UNITS:
        if remainder < 1024.0 or unit == _BYTE_UNITS[-1]:
            if unit == "B":
                return f"{int(remainder)} {unit}"
            return f"{remainder:.1f} {unit}"
        remainder /= 1024.0
    return f"{value} B"


@dataclass(frozen=True)
class CollectionStats:
    """Summary of a ``collect_app_logs`` invocation."""

    apps_written: int
    files_written: int
    files_skipped: int
    bytes_written: int


@dataclass(frozen=True)
class ConsolidationStats:
    """Summary of a ``consolidate_files`` invocation."""

    files_written: int
    files_skipped: int
    bytes_written: int


@dataclass(frozen=True)
class TreeStats:
    """Summary of a ``create_filtered_tree`` invocation."""

    lines_emitted: int
    bytes_written: int


def expand_skip_dirs(skip_dirs: Iterable[str]) -> tuple[str, ...]:
    """Create glob-style patterns that match skip directories preserving order."""

    ordered: list[str] = []
    seen: set[str] = set()
    for skip_dir in skip_dirs:
        if not isinstance(skip_dir, str):
            raise TypeError("Skip directory entries must be strings")

        cleaned = skip_dir.strip("/")
        if not cleaned:
            continue
        variants = (
            cleaned,
            f"{cleaned}/",
            f"*/{cleaned}",
            f"*/{cleaned}/",
            f"*/{cleaned}/*",
            f"{cleaned}/*",
        )
        for variant in variants:
            if variant not in seen:
                ordered.append(variant)
                seen.add(variant)
        # TODO - Detect conflicting skip directives that shadow required directories.
    return tuple(ordered)


def _normalise_user_ignore_patterns(patterns: Iterable[str]) -> tuple[str, ...]:
    """Validate and normalise user-provided ignore patterns preserving order."""

    normalised: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        if not isinstance(pattern, str):
            raise TypeError("User ignore patterns must be strings")

        stripped = pattern.strip()
        if not stripped:
            continue
        if any(control in stripped for control in ("\n", "\r")):
            raise ValueError("User ignore patterns cannot contain newline characters")

        if stripped not in seen:
            normalised.append(stripped)
            seen.add(stripped)
    # TODO - Persist custom ignore patterns alongside generated logs for auditing.
    return tuple(normalised)


def load_gitignore_patterns(
    root_path: Path,
    *,
    skip_dirs: Iterable[str] | None = None,
    user_ignore_patterns: Iterable[str] | None = None,
) -> list[str]:
    """Load ignore patterns from ``.gitignore`` and configuration defaults.

    The legacy behaviour – using the globally configured skip directories and
    user ignore patterns – is preserved when optional arguments are omitted.
    Passing explicit values allows callers that load custom configuration files
    to keep the ignore set aligned with their overrides.
    """

    if not root_path.exists():
        raise FileNotFoundError(f"Project root does not exist: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Project root must be a directory: {root_path}")

    config: Config | None = None
    if skip_dirs is None or user_ignore_patterns is None:
        config = get_config()

    effective_skip = tuple(skip_dirs or (config.skip if config else ()))
    effective_user_patterns = (
        _normalise_user_ignore_patterns(user_ignore_patterns)
        if user_ignore_patterns is not None
        else tuple(sorted(config.user_ignore_patterns) if config else ())
    )

    return list(
        _load_gitignore_patterns_cached(
            root_path.resolve(), effective_skip, effective_user_patterns
        )
    )


def _ingest_ignore_file(path: Path, add_pattern: Callable[[str], None]) -> None:
    if not path.is_file():
        return
    try:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith("#"):
                    add_pattern(stripped_line)
    except OSError as exc:  # pragma: no cover - unlikely on local filesystem
        warnings.warn(
            f"Failed to read ignore file {path}: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )


@typed_lru_cache(maxsize=128)
def _load_gitignore_patterns_cached(
    root_path: Path, skip_dirs: tuple[str, ...], user_ignore_patterns: tuple[str, ...]
) -> tuple[str, ...]:
    ordered_patterns: list[str] = []
    seen: set[str] = set()

    def add_pattern(value: str) -> None:
        if value not in seen:
            ordered_patterns.append(value)
            seen.add(value)

    for base in sorted(BASE_IGNORE_PATTERNS):
        add_pattern(base)
    for variant in expand_skip_dirs(skip_dirs):
        add_pattern(variant)
    for extra in user_ignore_patterns:
        add_pattern(extra)

    gitignore_path = root_path / ".gitignore"
    info_exclude = root_path / ".git" / "info" / "exclude"
    _ingest_ignore_file(gitignore_path, add_pattern)
    _ingest_ignore_file(info_exclude, add_pattern)
    # TODO - Parse gitignore escape sequences to mirror Git's matching semantics.
    return tuple(ordered_patterns)


def file_matches_any_pattern(file_path: Path | str, patterns: Iterable[str]) -> bool:
    """Return ``True`` if *file_path* matches one of *patterns*."""

    matcher = IgnoreMatcher(patterns)
    return matcher.matches(file_path)


def safe_relative_path(project_root: Path, candidate: Path) -> Path:
    """Return *candidate* relative to *project_root* ensuring it does not escape."""

    root_resolved = project_root.resolve()
    candidate_resolved = candidate.resolve()
    try:
        return candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Path {candidate} escapes project root {project_root}") from exc
    # TODO - Offer an option to allow symlinks that resolve within the project tree.


def _normalise_extensions(extensions: Iterable[str]) -> set[str]:
    normalised: set[str] = set()
    for ext in extensions:
        if not ext.startswith("."):
            raise ValueError("File extensions must include a leading '.' character")
        normalised.add(ext.lower())
    return normalised


def _iter_source_files(
    project_root: Path,
    extensions: Collection[str],
    matcher: IgnoreMatcher,
) -> Iterator[tuple[Path, Path, Path]]:
    root_resolved = project_root.resolve()
    extension_set = _normalise_extensions(extensions)

    for root, dirs, files in os.walk(root_resolved, followlinks=False):
        root_path = Path(root)
        if root_path.is_symlink():
            continue

        try:
            relative_root = safe_relative_path(root_resolved, root_path)
        except ValueError:
            continue

        if matcher.matches(relative_root):
            dirs[:] = []
            continue

        dirs[:] = sorted(d for d in dirs if not matcher.matches(relative_root / d))
        # TODO - Allow callers to provide a custom directory sort key for stability.
        # TODO - Provide hooks to short-circuit recursion for deeply nested trees.

        for file_name in sorted(files):
            file_path = root_path / file_name
            if file_path.is_symlink():
                continue
            # TODO - Expose a toggle for following symlinks with cycle protection.

            suffix = file_path.suffix.lower()
            if suffix not in extension_set:
                continue
            # TODO - Permit callers to pass wildcard extension filters for flexibility.

            try:
                relative_file = safe_relative_path(root_resolved, file_path)
            except ValueError:
                continue

            if matcher.matches(relative_file):
                continue

            yield relative_root, file_path, relative_file
            # TODO - Surface per-file timing metrics to help spot slow directories.
            # TODO - Emit debug callbacks for observers to inspect traversal decisions.


def group_source_files_by_app(
    project_root: Path,
    extensions: Collection[str],
    ignore_patterns: Collection[str],
) -> dict[str, list[Path]]:
    """Return a mapping of app labels to matching source files."""

    matcher = IgnoreMatcher(ignore_patterns)
    grouped: dict[str, list[Path]] = {}

    def _sort_key(path: Path) -> str:
        return path.as_posix()

    for relative_root, _, relative_file in _iter_source_files(project_root, extensions, matcher):
        app_name = relative_root.parts[0] if relative_root.parts else "root"
        grouped.setdefault(app_name, []).append(relative_file)
        # TODO - Allow pluggable grouping strategies for non-app-based layouts.

    ordered: dict[str, list[Path]] = {}
    for app_name in sorted(grouped):
        ordered[app_name] = sorted(grouped[app_name], key=_sort_key)
    # TODO - Preserve insertion order when deterministic sorting is not required.
    return ordered


def list_matching_source_files(
    project_root: Path,
    extensions: Collection[str],
    ignore_patterns: Collection[str],
) -> list[Path]:
    """Return matching source files relative to *project_root* sorted by path."""

    matcher = IgnoreMatcher(ignore_patterns)

    def _sort_key(path: Path) -> str:
        return path.as_posix()

    return sorted(
        (
            relative_file
            for _, _, relative_file in _iter_source_files(project_root, extensions, matcher)
        ),
        key=_sort_key,
    )
    # TODO - Offer lazy iterators to avoid holding all paths in memory at once.


def collect_app_logs(
    project_root: Path,
    log_dir: Path,
    extensions: Collection[str],
    ignore_patterns: Collection[str],
) -> CollectionStats:
    """Collect matching files grouped by app and write per-app log files."""

    matcher = IgnoreMatcher(ignore_patterns)
    log_dir.mkdir(parents=True, exist_ok=True)

    apps_written = 0
    files_written = 0
    files_skipped = 0
    bytes_written = 0

    with ExitStack() as stack:
        handles: dict[str, TextIO] = {}

        for relative_root, file_path, relative_file in _iter_source_files(
            project_root, extensions, matcher
        ):
            app_name = relative_root.parts[0] if relative_root.parts else "root"
            handle = handles.get(app_name)
            if handle is None:
                log_file_path = log_dir / f"{app_name}.txt"
                log_file_path.parent.mkdir(parents=True, exist_ok=True)
                handle = stack.enter_context(log_file_path.open("w", encoding="utf-8"))
                handle.write(f"# {app_name}\n\n")
                handles[app_name] = handle
                apps_written += 1

            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError) as exc:
                LOGGER.warning(
                    "event=collect_app_logs_skipped error_id=FS001 file=%s reason=%s",
                    file_path,
                    exc,
                )
                files_skipped += 1
                continue

            entry = f"# {relative_file.as_posix()}\n{content}\n\n"
            handle.write(entry)
            files_written += 1
            bytes_written += len(entry.encode())
            # TODO - Allow configurable separators to ease downstream parsing.
            # TODO - Stream output to gzip files when log compression is desired.

    return CollectionStats(
        apps_written=apps_written,
        files_written=files_written,
        files_skipped=files_skipped,
        bytes_written=bytes_written,
    )


def consolidate_files(
    project_root: Path,
    output_path: Path,
    extensions: Collection[str],
    ignore_patterns: Collection[str],
) -> ConsolidationStats:
    """Write all matching source files into a single consolidated log."""

    matcher = IgnoreMatcher(ignore_patterns)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    files_written = 0
    files_skipped = 0
    bytes_written = 0

    with output_path.open("w", encoding="utf-8") as output_file:
        for _, file_path, relative_file in _iter_source_files(project_root, extensions, matcher):
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
            entry = f"# {relative_file.as_posix()}\n{content}\n\n"
            output_file.write(entry)
            files_written += 1
            bytes_written += len(entry.encode())
            # TODO - Stream writes incrementally to support multi-gigabyte projects.
            # TODO - Embed file metadata headers to aid downstream tooling analysis.

    return ConsolidationStats(
        files_written=files_written,
        files_skipped=files_skipped,
        bytes_written=bytes_written,
    )


def iter_filtered_tree_lines(
    project_root: Path,
    ignore_patterns: Collection[str],
    *,
    include_content: bool = True,
    max_bytes: int = 4096,
) -> Iterator[str]:
    """Yield lines representing the filtered tree of *project_root*."""

    if max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")

    matcher = IgnoreMatcher(ignore_patterns)
    root_resolved = project_root.resolve()
    # TODO - Make max_bytes configurable per file type for more granular control.
    # TODO - Collect traversal statistics for reporting alongside the tree snapshot.

    directory_count = 0
    file_count = 0
    truncated_files = 0
    skipped_files = 0
    total_bytes = 0

    def _walk_tree(current: Path, prefix: str = "") -> Iterator[str]:
        nonlocal directory_count, file_count, truncated_files, skipped_files, total_bytes
        try:
            entries = sorted(current.iterdir())
        except OSError as exc:
            LOGGER.warning(
                "event=tree_walk_failed error_id=FS003 path=%s reason=%s",
                current,
                exc,
            )
            return

        for index, entry in enumerate(entries):
            is_last = index == len(entries) - 1
            connector = "└── " if is_last else "├── "

            try:
                relative_entry = safe_relative_path(root_resolved, entry)
            except ValueError:
                continue

            if matcher.matches(relative_entry):
                continue

            yield f"{prefix}{connector}{entry.name}"

            if entry.is_dir():
                directory_count += 1
                extension = "    " if is_last else "│   "
                yield from _walk_tree(entry, prefix + extension)
            elif include_content and entry.is_file():
                file_count += 1
                size_bytes: int | None
                try:
                    size_bytes = entry.stat().st_size
                except OSError as exc:
                    LOGGER.warning(
                        "event=tree_stat_failed error_id=FS005 path=%s reason=%s",
                        entry,
                        exc,
                    )
                    size_bytes = None
                try:
                    content = entry.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError) as exc:
                    LOGGER.warning(
                        "event=tree_content_skipped error_id=FS004 path=%s reason=%s",
                        entry,
                        exc,
                    )
                    skipped_files += 1
                    continue
                trimmed = content[:max_bytes]
                if trimmed:
                    for line in trimmed.splitlines():
                        yield f"{prefix}│   {line}"
                actual_size = len(content.encode()) if size_bytes is None else size_bytes
                total_bytes += actual_size
                if len(content) > len(trimmed) or (
                    size_bytes is not None and size_bytes > max_bytes
                ):
                    truncated_files += 1
                    yield (
                        f"{prefix}│   … (content truncated after {max_bytes} byte"
                        f"{'s' if max_bytes != 1 else ''})"
                    )
            elif entry.is_file():
                file_count += 1
                try:
                    total_bytes += entry.stat().st_size
                except OSError as exc:
                    LOGGER.warning(
                        "event=tree_stat_failed error_id=FS005 path=%s reason=%s",
                        entry,
                        exc,
                    )
                    skipped_files += 1
                    continue

    yield root_resolved.as_posix()
    yield from _walk_tree(root_resolved)
    yield ""
    summary = (
        "Summary: "
        f"{directory_count} {'directory' if directory_count == 1 else 'directories'}, "
        f"{file_count} {'file' if file_count == 1 else 'files'}, "
        f"~{format_bytes(total_bytes)} of content"
    )
    yield summary
    if truncated_files:
        yield (
            f"Note: {truncated_files} file{'s' if truncated_files != 1 else ''} truncated"
            f" at {max_bytes} byte{'s' if max_bytes != 1 else ''}."
        )
    if skipped_files:
        yield (
            f"Warning: {skipped_files} file{'s' if skipped_files != 1 else ''} "
            "skipped due to read errors."
        )


def create_filtered_tree(
    project_root: Path,
    output_path: Path,
    ignore_patterns: Collection[str],
    *,
    include_content: bool = True,
    max_bytes: int = 4096,
) -> TreeStats:
    """Write a filtered tree view of *project_root* to *output_path*."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    line_count = 0
    byte_count = 0
    with output_path.open("w", encoding="utf-8") as output_file:
        for line in iter_filtered_tree_lines(
            project_root,
            ignore_patterns,
            include_content=include_content,
            max_bytes=max_bytes,
        ):
            output_file.write(f"{line}\n")
            line_count += 1
            byte_count += len(f"{line}\n".encode())
    # TODO - Provide an option to emit ANSI colors when the tree targets terminal output.

    return TreeStats(lines_emitted=line_count, bytes_written=byte_count)


def ensure_writable_path(
    target: Path,
    *,
    allowed_root: Path | None = None,
    create_parents: bool = True,
) -> Path:
    """Validate that *target* can be written to before heavy work begins.

    When ``create_parents`` is ``True`` (the default) the function eagerly creates
    parent directories to mirror the behaviour of the file-writing commands.
    When ``False`` the function performs the same validation checks without
    touching the filesystem, which is useful for dry-run flows that must remain
    side-effect free.
    """

    expanded = target.expanduser()
    resolved = expanded.resolve(strict=False)

    if allowed_root is not None:
        allowed_resolved = allowed_root.expanduser().resolve(strict=False)
        if allowed_resolved.exists() and not allowed_resolved.is_dir():
            raise NotADirectoryError(
                f"Allowed root {allowed_resolved} is not a directory"
            )
        try:
            resolved.relative_to(allowed_resolved)
        except ValueError as exc:
            raise RuntimeError(
                f"Output path {resolved} escapes the allowed root {allowed_resolved}"
            ) from exc

    parent = resolved.parent
    parent_exists = parent.exists()
    permission_root = parent

    if parent_exists:
        if not parent.is_dir():
            raise RuntimeError(
                f"Cannot create parent directory for output path {resolved}: {parent} is a file"
            )
    else:
        ancestor = parent
        while not ancestor.exists():
            next_ancestor = ancestor.parent
            if next_ancestor == ancestor:
                break
            ancestor = next_ancestor
        if ancestor.exists():
            if not ancestor.is_dir():
                raise RuntimeError(
                    f"Cannot create parent directory for output path {resolved}: {ancestor} is a file"
                )
            permission_root = ancestor
        else:
            permission_root = ancestor

    if not os.access(permission_root, os.W_OK | os.X_OK):
        raise PermissionError(f"Output directory is not writable: {permission_root}")

    if create_parents and not parent_exists:
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except (FileExistsError, NotADirectoryError) as exc:
            raise RuntimeError(
                f"Cannot create parent directory for output path {resolved}: {parent} is a file"
            ) from exc
        parent_exists = True

    if parent_exists and not parent.is_dir():
        raise RuntimeError(
            f"Parent path for output {resolved} is not a directory: {parent}"
        )

    if resolved.exists():
        if resolved.is_dir():
            raise IsADirectoryError(f"Output path resolves to a directory: {resolved}")
        if not os.access(resolved, os.W_OK):
            raise PermissionError(f"Existing output file is not writable: {resolved}")

    return resolved


__all__ = [
    "IgnoreMatcher",
    "InvalidIgnorePatternError",
    "load_gitignore_patterns",
    "expand_skip_dirs",
    "file_matches_any_pattern",
    "group_source_files_by_app",
    "list_matching_source_files",
    "collect_app_logs",
    "consolidate_files",
    "iter_filtered_tree_lines",
    "create_filtered_tree",
    "ensure_writable_path",
    "CollectionStats",
    "ConsolidationStats",
    "TreeStats",
    "format_bytes",
]
