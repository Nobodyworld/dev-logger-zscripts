"""Utilities for loading and interpreting ``zscripts`` configuration."""

from __future__ import annotations

import functools
import json
import os
import warnings
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, TypeAlias, TypedDict, cast

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH_ENV_VAR = "ZSCRIPTS_CONFIG_PATH"
_FALLBACK_CONFIG_PATH = SCRIPT_DIR.parent / "zscripts.config.json"

if TYPE_CHECKING:  # pragma: no cover - aid static analysers without eager loading
    SKIP_DIRS: tuple[str, ...]
    FILE_TYPES: Mapping[str, str]
    USER_IGNORE_PATTERNS: frozenset[str]
    LOG_DIR: Path
    BUILD_DIR: Path
    ANALYSIS_DIR: Path
    CONSOLIDATION_DIR: Path
    WORK_DIR: Path
    ALL_LOG_DIR: Path
    PYTHON_LOG_DIR: Path
    HTML_LOG_DIR: Path
    CSS_LOG_DIR: Path
    JS_LOG_DIR: Path
    BOTH_LOG_DIR: Path
    SINGLE_LOG_DIR: Path
    CAPTURE_ALL_PYTHON_LOG: Path
    CAPTURE_ALL_HTML_LOG: Path
    CAPTURE_ALL_CSS_LOG: Path
    CAPTURE_ALL_JS_LOG: Path
    CAPTURE_ALL_PYTHON_HTML_LOG: Path
    CAPTURE_ALL_LOG: Path


def _determine_default_config_path() -> Path:
    """Return the configuration path honouring environment overrides."""

    override = os.environ.get(CONFIG_PATH_ENV_VAR)
    base = Path(override).expanduser() if override else _FALLBACK_CONFIG_PATH
    return base


DEFAULT_CONFIG_PATH = _determine_default_config_path()

JSONPrimitive: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]
JSONMapping: TypeAlias = Mapping[str, JSONValue]


class SerializableConfig(TypedDict):
    skip: list[str]
    file_types: dict[str, str]
    user_ignore_patterns: list[str]
    directories: dict[str, str]
    collection_logs: dict[str, str]
    single_targets: dict[str, str]


@dataclass(frozen=True)
class Config:
    """Immutable snapshot of configuration values loaded from JSON."""

    skip: tuple[str, ...]
    file_types: Mapping[str, str]
    user_ignore_patterns: frozenset[str]
    directories: Mapping[str, str]
    collection_logs: Mapping[str, str]
    single_targets: Mapping[str, str]

    def to_dict(self) -> SerializableConfig:
        return {
            "skip": list(self.skip),
            "file_types": dict(self.file_types),
            "user_ignore_patterns": sorted(self.user_ignore_patterns),
            "directories": dict(self.directories),
            "collection_logs": dict(self.collection_logs),
            "single_targets": dict(self.single_targets),
        }


@dataclass(frozen=True)
class ResolvedPaths:
    """Concrete filesystem locations derived from configuration settings."""

    log_dir: Path
    build_dir: Path
    analysis_dir: Path
    consolidation_dir: Path
    work_dir: Path
    all_log_dir: Path
    python_log_dir: Path
    html_log_dir: Path
    css_log_dir: Path
    js_log_dir: Path
    python_html_log_dir: Path
    single_log_dir: Path
    capture_all_python_log: Path
    capture_all_html_log: Path
    capture_all_css_log: Path
    capture_all_js_log: Path
    capture_all_python_html_log: Path
    capture_all_log: Path


def _load_raw_config(config_path: Path | None = None) -> dict[str, JSONValue]:
    path = config_path or _determine_default_config_path()
    try:
        with path.open("r", encoding="utf-8") as handle:
            data: object = json.load(handle)
    except FileNotFoundError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(
            f"Configuration file not found: {path}. Ensure zscripts.config.json exists."
        ) from exc
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(f"Configuration file {path} is not valid JSON") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Configuration root must be a JSON object")

    known_keys = {
        "skip",
        "file_types",
        "user_ignore_patterns",
        "directories",
        "collection_logs",
        "single_targets",
    }
    unknown_keys = sorted(set(data) - known_keys)
    if unknown_keys:
        raise RuntimeError(
            "Unknown configuration keys: "
            + ", ".join(unknown_keys)
            + ". Expected keys: "
            + ", ".join(sorted(known_keys))
        )

    return cast(dict[str, JSONValue], data)


def _warn_on_duplicates(name: str, duplicates: Iterable[str]) -> None:
    duplicate_list = sorted(set(duplicates))
    if duplicate_list:
        warnings.warn(
            f"Duplicate entries ignored in '{name}': {', '.join(duplicate_list)}",
            RuntimeWarning,
            stacklevel=3,
        )


def _ensure_iterable_of_strings(value: JSONValue | None, *, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str | bytes) or not isinstance(value, Iterable):
        raise RuntimeError(f"Expected '{name}' to be an iterable of strings")

    seen: list[str] = []
    duplicates: list[str] = []
    iterable_value = cast(Iterable[object], value)
    for item in iterable_value:
        if not isinstance(item, str):
            raise RuntimeError(f"Configuration entry '{name}' must contain only strings")
        normalised = item.strip()
        if normalised and normalised not in seen:
            seen.append(normalised)
        elif normalised:
            duplicates.append(normalised)
    _warn_on_duplicates(name, duplicates)
    return tuple(seen)


def _ensure_mapping_of_strings(value: JSONValue | None, *, name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise RuntimeError(f"Expected '{name}' to be a mapping of string keys to string values")

    result: dict[str, str] = {}
    mapping_value = cast(Mapping[object, object], value)
    for key, raw_value in mapping_value.items():
        if not isinstance(key, str) or not isinstance(raw_value, str):
            raise RuntimeError(f"Configuration entry '{name}' must contain only string keys/values")
        key_stripped = key.strip()
        if not key_stripped:
            continue
        result[key_stripped] = raw_value.strip()
    return result


def _freeze_mapping(mapping: Mapping[str, str]) -> Mapping[str, str]:
    return MappingProxyType(dict(mapping))


def _normalise_raw_config(raw: JSONMapping) -> Config:
    return Config(
        skip=_ensure_iterable_of_strings(raw.get("skip"), name="skip"),
        file_types=_freeze_mapping(
            _ensure_mapping_of_strings(raw.get("file_types"), name="file_types")
        ),
        user_ignore_patterns=frozenset(
            _ensure_iterable_of_strings(
                raw.get("user_ignore_patterns"), name="user_ignore_patterns"
            )
        ),
        directories=_freeze_mapping(
            _ensure_mapping_of_strings(raw.get("directories"), name="directories")
        ),
        collection_logs=_freeze_mapping(
            _ensure_mapping_of_strings(raw.get("collection_logs"), name="collection_logs")
        ),
        single_targets=_freeze_mapping(
            _ensure_mapping_of_strings(raw.get("single_targets"), name="single_targets")
        ),
    )


def _merge_config_data(defaults: Config, overrides: Config) -> Config:
    combined_skip: list[str] = list(defaults.skip)
    for value in overrides.skip:
        if value not in combined_skip:
            combined_skip.append(value)
    skip = tuple(combined_skip)
    file_types = dict(defaults.file_types)
    file_types.update(overrides.file_types)
    user_ignore_patterns = defaults.user_ignore_patterns | overrides.user_ignore_patterns
    directories = dict(defaults.directories)
    directories.update(overrides.directories)
    collection_logs = dict(defaults.collection_logs)
    collection_logs.update(overrides.collection_logs)
    single_targets = dict(defaults.single_targets)
    single_targets.update(overrides.single_targets)

    # TODO - Track the provenance of merged settings for better diagnostics.
    return Config(
        skip=skip,
        file_types=_freeze_mapping(file_types),
        user_ignore_patterns=user_ignore_patterns,
        directories=_freeze_mapping(directories),
        collection_logs=_freeze_mapping(collection_logs),
        single_targets=_freeze_mapping(single_targets),
    )


def _ensure_within_root(root: Path, candidate: Path, *, label: str) -> Path:
    try:
        candidate.resolve().relative_to(root)
    except ValueError as exc:
        raise RuntimeError(
            f"Configured path '{label}' escapes the log root {root}. Value: {candidate}"
        ) from exc
    return candidate


def resolve_paths(config: Config, *, base_dir: Path | None = None) -> ResolvedPaths:
    root_dir = (base_dir or SCRIPT_DIR).resolve()

    log_dir = _ensure_within_root(
        root_dir, root_dir / config.directories.get("log_root", "logs"), label="log_root"
    )
    analysis_dir = _ensure_within_root(
        root_dir, log_dir / config.directories.get("analysis", "analysis_logs"), label="analysis"
    )
    build_dir = _ensure_within_root(
        root_dir, log_dir / config.directories.get("build", "build_files"), label="build"
    )
    consolidation_dir = _ensure_within_root(
        root_dir,
        log_dir / config.directories.get("consolidation", "consoli_files"),
        label="consolidation",
    )
    work_dir = _ensure_within_root(
        root_dir, log_dir / config.directories.get("work", "logs_files"), label="work"
    )

    all_log_dir = _ensure_within_root(
        root_dir, log_dir / config.collection_logs.get("all", "logs_apps_all"), label="all"
    )
    python_log_dir = _ensure_within_root(
        root_dir,
        log_dir / config.collection_logs.get("python", "logs_apps_pyth"),
        label="python",
    )
    html_log_dir = _ensure_within_root(
        root_dir, log_dir / config.collection_logs.get("html", "logs_apps_html"), label="html"
    )
    css_log_dir = _ensure_within_root(
        root_dir, log_dir / config.collection_logs.get("css", "logs_apps_css"), label="css"
    )
    js_log_dir = _ensure_within_root(
        root_dir, log_dir / config.collection_logs.get("js", "logs_apps_js"), label="js"
    )
    python_html_log_dir = _ensure_within_root(
        root_dir,
        log_dir / config.collection_logs.get("python_html", "logs_apps_both"),
        label="python_html",
    )
    single_log_dir = _ensure_within_root(
        root_dir,
        log_dir / config.collection_logs.get("single", "logs_single_files"),
        label="single",
    )

    capture_all_python_log = _ensure_within_root(
        root_dir,
        single_log_dir / config.single_targets.get("python", "capture_all_pyth.txt"),
        label="capture_all_python",
    )
    capture_all_html_log = _ensure_within_root(
        root_dir,
        single_log_dir / config.single_targets.get("html", "capture_all_html.txt"),
        label="capture_all_html",
    )
    capture_all_css_log = _ensure_within_root(
        root_dir,
        single_log_dir / config.single_targets.get("css", "capture_all_css.txt"),
        label="capture_all_css",
    )
    capture_all_js_log = _ensure_within_root(
        root_dir,
        single_log_dir / config.single_targets.get("js", "capture_all_js.txt"),
        label="capture_all_js",
    )
    capture_all_python_html_log = _ensure_within_root(
        root_dir,
        single_log_dir
        / config.single_targets.get("python_html", "capture_all_python_html.txt"),
        label="capture_all_python_html",
    )
    capture_all_log = _ensure_within_root(
        root_dir,
        single_log_dir / config.single_targets.get("any", "capture_all.txt"),
        label="capture_all",
    )

    return ResolvedPaths(
        log_dir=log_dir,
        build_dir=build_dir,
        analysis_dir=analysis_dir,
        consolidation_dir=consolidation_dir,
        work_dir=work_dir,
        all_log_dir=all_log_dir,
        python_log_dir=python_log_dir,
        html_log_dir=html_log_dir,
        css_log_dir=css_log_dir,
        js_log_dir=js_log_dir,
        python_html_log_dir=python_html_log_dir,
        single_log_dir=single_log_dir,
        capture_all_python_log=capture_all_python_log,
        capture_all_html_log=capture_all_html_log,
        capture_all_css_log=capture_all_css_log,
        capture_all_js_log=capture_all_js_log,
        capture_all_python_html_log=capture_all_python_html_log,
        capture_all_log=capture_all_log,
    )


@functools.lru_cache(maxsize=1)
def _get_default_config() -> Config:
    return _normalise_raw_config(_load_raw_config())


@functools.lru_cache(maxsize=1)
def _get_default_paths() -> ResolvedPaths:
    return resolve_paths(_get_default_config())


def load_config(path: Path | str | None = None) -> Config:
    if path is None:
        return _get_default_config()

    override_path = Path(path).expanduser()
    overrides = _normalise_raw_config(_load_raw_config(override_path))
    return _merge_config_data(_get_default_config(), overrides)


def get_config() -> Config:
    return _get_default_config()


def get_file_group_resolver() -> dict[str, str]:
    return dict(_get_default_config().file_types)


_CONFIG_EXPORTS: dict[str, Callable[[], Any]] = {
    "SKIP_DIRS": lambda: _get_default_config().skip,
    "FILE_TYPES": lambda: dict(_get_default_config().file_types),
    "USER_IGNORE_PATTERNS": lambda: _get_default_config().user_ignore_patterns,
    "LOG_DIR": lambda: _get_default_paths().log_dir,
    "BUILD_DIR": lambda: _get_default_paths().build_dir,
    "ANALYSIS_DIR": lambda: _get_default_paths().analysis_dir,
    "CONSOLIDATION_DIR": lambda: _get_default_paths().consolidation_dir,
    "WORK_DIR": lambda: _get_default_paths().work_dir,
    "ALL_LOG_DIR": lambda: _get_default_paths().all_log_dir,
    "PYTHON_LOG_DIR": lambda: _get_default_paths().python_log_dir,
    "HTML_LOG_DIR": lambda: _get_default_paths().html_log_dir,
    "CSS_LOG_DIR": lambda: _get_default_paths().css_log_dir,
    "JS_LOG_DIR": lambda: _get_default_paths().js_log_dir,
    "BOTH_LOG_DIR": lambda: _get_default_paths().python_html_log_dir,
    "SINGLE_LOG_DIR": lambda: _get_default_paths().single_log_dir,
    "CAPTURE_ALL_PYTHON_LOG": lambda: _get_default_paths().capture_all_python_log,
    "CAPTURE_ALL_HTML_LOG": lambda: _get_default_paths().capture_all_html_log,
    "CAPTURE_ALL_CSS_LOG": lambda: _get_default_paths().capture_all_css_log,
    "CAPTURE_ALL_JS_LOG": lambda: _get_default_paths().capture_all_js_log,
    "CAPTURE_ALL_PYTHON_HTML_LOG": lambda: _get_default_paths().capture_all_python_html_log,
    "CAPTURE_ALL_LOG": lambda: _get_default_paths().capture_all_log,
}


def __getattr__(name: str) -> Any:  # pragma: no cover - simple delegation
    exporter = _CONFIG_EXPORTS.get(name)
    if exporter is not None:
        return exporter()
    raise AttributeError(name)


__all__ = [
    "Config",
    "DEFAULT_CONFIG_PATH",
    "ResolvedPaths",
    "SKIP_DIRS",
    "FILE_TYPES",
    "USER_IGNORE_PATTERNS",
    "SCRIPT_DIR",
    "LOG_DIR",
    "BUILD_DIR",
    "ANALYSIS_DIR",
    "CONSOLIDATION_DIR",
    "WORK_DIR",
    "ALL_LOG_DIR",
    "PYTHON_LOG_DIR",
    "HTML_LOG_DIR",
    "CSS_LOG_DIR",
    "JS_LOG_DIR",
    "BOTH_LOG_DIR",
    "SINGLE_LOG_DIR",
    "CAPTURE_ALL_PYTHON_LOG",
    "CAPTURE_ALL_HTML_LOG",
    "CAPTURE_ALL_CSS_LOG",
    "CAPTURE_ALL_JS_LOG",
    "CAPTURE_ALL_PYTHON_HTML_LOG",
    "CAPTURE_ALL_LOG",
    "load_config",
    "resolve_paths",
    "get_config",
    "get_file_group_resolver",
]
