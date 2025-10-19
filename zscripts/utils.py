"""Filesystem utilities used by :mod:`zscripts` commands."""

from __future__ import annotations

import fnmatch
import logging
import os
import re
import warnings
from collections.abc import Collection, Iterable, Iterator
from pathlib import Path
from typing import Final, TextIO

from ._cache import typed_lru_cache
from .config import Config, get_config

_WINDOWS = os.name == "nt"


@typed_lru_cache(maxsize=256)
def _compile_pattern(pattern: str, *, case_sensitive: bool) -> re.Pattern[str]:
    flags = 0 if case_sensitive else re.IGNORECASE
    translated = fnmatch.translate(pattern)
    return re.compile(translated, flags)


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
        # TODO - Track compilation failures to surface invalid glob syntax to callers.

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


def expand_skip_dirs(skip_dirs: Iterable[str]) -> set[str]:
    """Create glob-style patterns that match skip directories."""

    patterns: set[str] = set()
    for skip_dir in skip_dirs:
        if not isinstance(skip_dir, str):
            raise TypeError("Skip directory entries must be strings")

        cleaned = skip_dir.strip("/")
        if not cleaned:
            continue
        # TODO - Preserve ordering to make debugging merged skip patterns easier.
        patterns.update(
            {
                cleaned,
                f"{cleaned}/",
                f"*/{cleaned}",
                f"*/{cleaned}/",
                f"*/{cleaned}/*",
                f"{cleaned}/*",
            }
        )
        # TODO - Detect conflicting skip directives that shadow required directories.
    return patterns


def _normalise_user_ignore_patterns(patterns: Iterable[str]) -> set[str]:
    """Validate and normalise user-provided ignore patterns."""

    normalised: set[str] = set()
    for pattern in patterns:
        if not isinstance(pattern, str):
            raise TypeError("User ignore patterns must be strings")

        stripped = pattern.strip()
        if not stripped:
            continue
        if any(control in stripped for control in ("\n", "\r")):
            raise ValueError("User ignore patterns cannot contain newline characters")

        normalised.add(stripped)
    # TODO - Persist custom ignore patterns alongside generated logs for auditing.
    # TODO - Preserve insertion order so downstream tooling can respect priority.
    return normalised


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
        tuple(sorted(_normalise_user_ignore_patterns(user_ignore_patterns)))
        if user_ignore_patterns is not None
        else tuple(sorted(config.user_ignore_patterns) if config else ())
    )

    return list(
        _load_gitignore_patterns_cached(
            root_path.resolve(), effective_skip, effective_user_patterns
        )
    )


def _ingest_ignore_file(path: Path, patterns: set[str]) -> None:
    if not path.is_file():
        return
    try:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith("#"):
                    patterns.add(stripped_line)
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
    patterns: set[str] = set(BASE_IGNORE_PATTERNS)
    patterns.update(expand_skip_dirs(skip_dirs))
    patterns.update(user_ignore_patterns)

    gitignore_path = root_path / ".gitignore"
    info_exclude = root_path / ".git" / "info" / "exclude"
    _ingest_ignore_file(gitignore_path, patterns)
    _ingest_ignore_file(info_exclude, patterns)
    # TODO - Parse gitignore escape sequences to mirror Git's matching semantics.
    return tuple(sorted(patterns))


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
) -> None:
    """Collect matching files grouped by app and write per-app log files."""

    matcher = IgnoreMatcher(ignore_patterns)
    log_dir.mkdir(parents=True, exist_ok=True)

    handles: dict[str, TextIO] = {}

    try:
        for relative_root, file_path, relative_file in _iter_source_files(
            project_root, extensions, matcher
        ):
            app_name = relative_root.parts[0] if relative_root.parts else "root"
            handle = handles.get(app_name)
            if handle is None:
                log_file_path = log_dir / f"{app_name}.txt"
                log_file_path.parent.mkdir(parents=True, exist_ok=True)
                handle = log_file_path.open("w", encoding="utf-8")
                handle.write(f"# {app_name}\n\n")
                handles[app_name] = handle

            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError) as exc:
                LOGGER.warning(
                    "event=collect_app_logs_skipped error_id=FS001 file=%s reason=%s",
                    file_path,
                    exc,
                )
                continue

            handle.write(f"# {relative_file.as_posix()}\n{content}\n\n")
            # TODO - Allow configurable separators to ease downstream parsing.
            # TODO - Stream output to gzip files when log compression is desired.
    finally:
        for handle in handles.values():
            handle.close()
        # TODO - Ensure file handles are flushed even if the close operation fails.


def consolidate_files(
    project_root: Path,
    output_path: Path,
    extensions: Collection[str],
    ignore_patterns: Collection[str],
) -> None:
    """Write all matching source files into a single consolidated log."""

    matcher = IgnoreMatcher(ignore_patterns)
    output_path.parent.mkdir(parents=True, exist_ok=True)

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
                continue
            output_file.write(f"# {relative_file.as_posix()}\n{content}\n\n")
            # TODO - Stream writes incrementally to support multi-gigabyte projects.
            # TODO - Embed file metadata headers to aid downstream tooling analysis.


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

    def _walk_tree(current: Path, prefix: str = "") -> Iterator[str]:
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
                extension = "    " if is_last else "│   "
                yield from _walk_tree(entry, prefix + extension)
            elif include_content and entry.is_file():
                try:
                    content = entry.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError) as exc:
                    LOGGER.warning(
                        "event=tree_content_skipped error_id=FS004 path=%s reason=%s",
                        entry,
                        exc,
                    )
                    continue
                trimmed = content[:max_bytes]
                if trimmed:
                    for line in trimmed.splitlines():
                        yield f"{prefix}│   {line}"
                # TODO - Add elided content markers when files exceed max_bytes.

    yield root_resolved.as_posix()
    yield from _walk_tree(root_resolved)
    # TODO - Append summary statistics (counts, sizes) at the end of the tree output.


def create_filtered_tree(
    project_root: Path,
    output_path: Path,
    ignore_patterns: Collection[str],
    *,
    include_content: bool = True,
    max_bytes: int = 4096,
) -> None:
    """Write a filtered tree view of *project_root* to *output_path*."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        for line in iter_filtered_tree_lines(
            project_root,
            ignore_patterns,
            include_content=include_content,
            max_bytes=max_bytes,
        ):
            output_file.write(f"{line}\n")
    # TODO - Provide an option to emit ANSI colors when the tree targets terminal output.


__all__ = [
    "IgnoreMatcher",
    "load_gitignore_patterns",
    "expand_skip_dirs",
    "file_matches_any_pattern",
    "group_source_files_by_app",
    "list_matching_source_files",
    "collect_app_logs",
    "consolidate_files",
    "iter_filtered_tree_lines",
    "create_filtered_tree",
]
