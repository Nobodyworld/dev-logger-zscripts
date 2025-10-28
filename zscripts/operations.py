"""
High-level orchestration utilities for the zscripts toolkit.

The public helpers in this module wrap the lower-level functions from
``zscripts.utils`` and expose them in a more composable fashion that can
be invoked both programmatically and through the CLI entry point.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, MutableSequence, Set

from . import config as _config
from . import utils

# --------------------------------------------------------------------------- #
# Context helpers


def _dedupe_preserving_order(items: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            ordered.append(item)
            seen.add(item)
    return tuple(ordered)


def _normalize_suffixes(suffixes: Iterable[str]) -> Set[str]:
    """
    Normalise a collection of suffixes so that every item begins with ``.``.
    """
    normalised: Set[str] = set()
    for suffix in suffixes:
        normalised.add(suffix if suffix.startswith(".") else f".{suffix}")
    return normalised


_SKIP_DIR_PATTERNS = _dedupe_preserving_order(
    pattern for name in _config.SKIP_DIRS for pattern in (name, f"{name}/", f"*/{name}", f"*/{name}/*")
)


@dataclass(frozen=True)
class ProjectContext:
    """
    Captures shared configuration used by higher-level operations.

    Attributes:
        project_root: Absolute path to the repository root.
        ignore_patterns: Patterns passed to ``utils.file_matches_any_pattern``.
        skip_dir_names: Simple directory names that should be skipped by
            directory walkers that do not rely on glob patterns.
    """

    project_root: Path
    ignore_patterns: tuple[str, ...]
    skip_dir_names: tuple[str, ...] = _config.SKIP_DIRS

    @classmethod
    def build(
        cls,
        *,
        extra_patterns: Iterable[str] = (),
        include_skip_dir_patterns: bool = True,
    ) -> "ProjectContext":
        """
        Create a new ``ProjectContext``.

        Args:
            extra_patterns: Additional ignore patterns to inject.
            include_skip_dir_patterns: When true (default), expand the directory
                names listed in :data:`SKIP_DIRS` into glob patterns that are
                added to the ignore list.
        """

        base_patterns = utils.load_gitignore_patterns(_config.PROJECT_ROOT)
        if include_skip_dir_patterns:
            base_patterns.extend(_SKIP_DIR_PATTERNS)
        base_patterns.extend(extra_patterns)

        return cls(
            project_root=_config.PROJECT_ROOT,
            ignore_patterns=_dedupe_preserving_order(base_patterns),
        )

    @staticmethod
    def ensure_dir(path: Path) -> Path:
        """
        Ensure ``path`` exists as a directory and return it.
        """
        path.mkdir(parents=True, exist_ok=True)
        return path


# --------------------------------------------------------------------------- #
# Logging helpers


def _app_log_destinations() -> Mapping[str, Path]:
    return {
        "python": _config.PYTHON_LOG_DIR,
        "html": _config.HTML_LOG_DIR,
        "css": _config.CSS_LOG_DIR,
        "javascript": _config.JS_LOG_DIR,
        "python-html": _config.BOTH_LOG_DIR,
        "all": _config.ALL_LOG_DIR,
    }


def _single_log_destinations() -> Mapping[str, Path]:
    return {
        "python": _config.CAPTURE_ALL_PYTHON_LOG,
        "html": _config.CAPTURE_ALL_HTML_LOG,
        "css": _config.CAPTURE_ALL_CSS_LOG,
        "javascript": _config.CAPTURE_ALL_JS_LOG,
        "python-html": _config.CAPTURE_ALL_PYTHON_HTML_LOG,
        "all": _config.CAPTURE_ALL_LOG,
    }


_PRESET_ALIASES = {
    "js": "javascript",
}


def _resolve_preset_name(preset: str) -> str:
    canonical = preset.lower().strip()
    canonical = _PRESET_ALIASES.get(canonical, canonical)
    if canonical not in _config.FILE_TYPE_PRESETS:
        raise KeyError(f"Unknown file-type preset: {preset!r}")
    return canonical


def generate_app_logs(
    file_types: Iterable[str],
    log_dir: Path,
    *,
    context: ProjectContext | None = None,
) -> Path:
    """
    Generate per-app logs for the supplied ``file_types`` into ``log_dir``.

    Args:
        file_types: Sequence of suffixes such as {'.py', '.html'}.
        log_dir: Destination directory for the generated logs.
        context: Optional ``ProjectContext`` overriding the defaults.

    Returns:
        Path to the directory containing the generated logs.
    """
    context = context or ProjectContext.build()
    ProjectContext.ensure_dir(log_dir)
    utils.create_app_logs(
        context.project_root,
        log_dir,
        _normalize_suffixes(file_types),
        list(context.ignore_patterns),
    )
    return log_dir


def generate_app_logs_for_preset(
    preset: str,
    *,
    context: ProjectContext | None = None,
) -> Path:
    """
    Convenience wrapper producing app-level logs for one of the presets defined
    in :data:`_config.FILE_TYPE_PRESETS`.
    """
    preset_name = _resolve_preset_name(preset)
    destination = _app_log_destinations()[preset_name]
    return generate_app_logs(
        _config.FILE_TYPE_PRESETS[preset_name],
        destination,
        context=context,
    )


def consolidate_file_types(
    file_types: Iterable[str],
    output_path: Path,
    *,
    context: ProjectContext | None = None,
) -> Path:
    """
    Consolidate the contents of ``file_types`` into a single file at
    ``output_path``.
    """
    context = context or ProjectContext.build()
    ProjectContext.ensure_dir(output_path.parent)
    utils.consolidate_files(
        context.project_root,
        output_path,
        _normalize_suffixes(file_types),
        list(context.ignore_patterns),
    )
    return output_path


def consolidate_file_types_for_preset(
    preset: str,
    *,
    context: ProjectContext | None = None,
) -> Path:
    """
    Convenience wrapper for consolidating one of the pre-defined presets.
    """
    preset_name = _resolve_preset_name(preset)
    destination = _single_log_destinations()[preset_name]
    return consolidate_file_types(
        _config.FILE_TYPE_PRESETS[preset_name],
        destination,
        context=context,
    )


def create_tree_snapshot(
    *,
    destination: Path | None = None,
    file_types: Iterable[str] | None = None,
    context: ProjectContext | None = None,
) -> Path:
    """
    Create a filtered directory tree snapshot rooted at the project.

    Args:
        destination: Optional explicit path for the resulting log file. When
            omitted, a timestamped file inside ``_config.TREE_LOG_DIR`` is created.
        file_types: Optional iterable of suffixes that should be included in
            the snapshot. Defaults to the ``all`` preset.
        context: Optional project context override.

    Returns:
        Path to the generated tree snapshot file.
    """
    context = context or ProjectContext.build()
    if destination is None:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        destination = _config.TREE_LOG_DIR / f"tree_{timestamp}.txt"

    suffixes = _normalize_suffixes(file_types) if file_types is not None else _config.FILE_TYPE_PRESETS["all"]
    suffixes = _normalize_suffixes(suffixes)

    ProjectContext.ensure_dir(destination.parent)
    utils.create_filtered_tree(
        context.project_root,
        destination,
        suffixes,
        list(context.ignore_patterns),
    )
    return destination


# --------------------------------------------------------------------------- #
# Build directory utilities


def convert_work_directory(
    *,
    work_dir: Path | None = None,
    build_dir: Path | None = None,
) -> list[Path]:
    """
    Convert ``*_files.txt`` entries from ``work_dir`` into Python files stored
    inside ``build_dir``.

    Returns:
        List of files that were written.
    """
    work_dir = work_dir if work_dir is not None else _config.WORK_DIR
    build_dir = build_dir if build_dir is not None else _config.BUILD_DIR

    ProjectContext.ensure_dir(build_dir)
    if not work_dir.exists():
        return []

    written: MutableSequence[Path] = []
    for input_file in sorted(work_dir.glob("*.txt")):
        target_name = input_file.name.replace("_files.txt", ".py")
        if not target_name.endswith(".py"):
            continue

        content = input_file.read_text(encoding="utf-8")
        if not content.strip():
            continue

        target_path = build_dir / target_name
        target_path.write_text(content, encoding="utf-8")
        written.append(target_path)

    return list(written)


def analyse_build_directory(
    *,
    source_dir: Path | None = None,
    analysis_dir: Path | None = None,
) -> list[Path]:
    """
    Extract class/function definitions from ``source_dir`` into ``analysis_dir``.
    """
    source_dir = source_dir if source_dir is not None else _config.BUILD_DIR
    analysis_dir = analysis_dir if analysis_dir is not None else _config.ANALYSIS_DIR

    ProjectContext.ensure_dir(analysis_dir)
    if not source_dir.exists():
        return []

    written: MutableSequence[Path] = []
    for python_file in sorted(source_dir.rglob("*.py")):
        utils.extract_definitions(python_file, analysis_dir)
        written.append(analysis_dir / python_file.with_suffix(".txt").name)
    return list(written)


def consolidate_directory(
    source_dir: Path,
    *,
    file_extension: str,
    output_path: Path,
) -> Path:
    """
    Concatenate every file inside ``source_dir`` that matches ``file_extension``
    into ``output_path`` with basic section delimiters.
    """
    ProjectContext.ensure_dir(output_path.parent)
    suffix = file_extension if file_extension.startswith(".") else f".{file_extension}"

    with output_path.open("w", encoding="utf-8") as handle:
        for file_path in sorted(source_dir.rglob(f"*{suffix}")):
            if not file_path.is_file():
                continue
            handle.write(f"# Start of {file_path.name}\n")
            handle.write(file_path.read_text(encoding="utf-8"))
            handle.write(f"\n# End of {file_path.name}\n\n")

    return output_path


def consolidate_default_directories() -> Mapping[str, Path]:
    """
    Run the consolidation tasks that were previously handled by
    ``make/consoli.py`` and return the resulting files.
    """
    return {
        "build": consolidate_directory(
            _config.BUILD_DIR,
            file_extension=".py",
            output_path=_config.CONSOLIDATION_DIR / "consolidated_build.py",
        ),
        "analysis": consolidate_directory(
            _config.ANALYSIS_DIR,
            file_extension=".txt",
            output_path=_config.CONSOLIDATION_DIR / "consolidated_analysis.txt",
        ),
    }


# --------------------------------------------------------------------------- #
# Convenience helpers used by the CLI and legacy scripts


def list_presets() -> Mapping[str, Set[str]]:
    """
    Return a mapping of available preset names to the suffixes they contain.
    """
    return {name: set(values) for name, values in _config.FILE_TYPE_PRESETS.items()}


def ensure_log_directories() -> None:
    """
    Create the log directories that are referenced throughout the toolkit.
    """
    for directory in {
        _config.LOG_DIR,
        _config.ALL_LOG_DIR,
        _config.PYTHON_LOG_DIR,
        _config.HTML_LOG_DIR,
        _config.CSS_LOG_DIR,
        _config.JS_LOG_DIR,
        _config.BOTH_LOG_DIR,
        _config.SINGLE_LOG_DIR,
        _config.TREE_LOG_DIR,
        _config.BUILD_DIR,
        _config.ANALYSIS_DIR,
        _config.CONSOLIDATION_DIR,
        _config.WORK_DIR,
    }:
        ProjectContext.ensure_dir(directory)
