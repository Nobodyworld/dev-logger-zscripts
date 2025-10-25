"""Utilities for loading and validating toolkit configuration."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final, cast

import tomllib

from zscripts.config import DEFAULT_CONFIG, ToolkitConfig, clone_config


class ConfigurationError(ValueError):
    """Raised when configuration parsing or validation fails."""


_STR_TRUE: Final[set[str]] = {"1", "true", "yes", "on"}
_STR_FALSE: Final[set[str]] = {"0", "false", "no", "off"}


def parse_override_pairs(raw: Sequence[str] | None) -> dict[str, str]:
    """Parse ``KEY=VALUE`` CLI overrides into a mapping."""

    if not raw:
        return {}
    overrides: dict[str, str] = {}
    for entry in raw:
        if "=" not in entry:
            raise ConfigurationError(
                f"Override '{entry}' must be in KEY=VALUE format."
            )
        key, value = entry.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ConfigurationError("Override keys cannot be empty.")
        overrides[key] = value
    return overrides


def load_toolkit_config(
    *,
    path: Path | None,
    overrides: Mapping[str, str],
    base: ToolkitConfig | None = None,
) -> ToolkitConfig:
    """Compose a :class:`ToolkitConfig` from defaults, an optional file, and overrides."""

    config = clone_config(base) if base is not None else ToolkitConfig(**DEFAULT_CONFIG)
    file_values: Mapping[str, object] = {}
    if path is not None:
        file_values = _load_file(path)
    config = _apply_config_values(
        config,
        file_values,
        source=str(path) if path else "defaults",
    )
    config = _apply_config_values(config, overrides, source="CLI overrides")
    return config


def _load_file(path: Path) -> Mapping[str, object]:
    if not path.exists():
        raise ConfigurationError(f"Configuration file '{path}' does not exist.")
    if path.is_dir():
        raise ConfigurationError(f"Configuration path '{path}' is a directory.")
    suffix = path.suffix.lower()
    try:
        data: Mapping[str, object]
        if suffix in {".toml", ""}:
            with path.open("rb") as handle:
                data = cast(dict[str, object], tomllib.load(handle))
        elif suffix == ".json":
            with path.open("r", encoding="utf-8") as handle:
                data = cast(dict[str, object], json.load(handle))
        else:
            raise ConfigurationError(
                "Unsupported configuration format. Use TOML or JSON files."
            )
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"Failed to parse configuration file '{path}': {exc}") from exc
    if not isinstance(data, Mapping):
        raise ConfigurationError(
            f"Configuration file '{path}' must contain a top-level mapping."
        )
    return data


_KNOWN_KEYS: Final[tuple[str, ...]] = (
    "allowed_paths",
    "timeout_seconds",
    "dangerous_mode",
    "default_adapter",
    "redact_patterns",
    "examples_path",
    "telemetry_enabled",
    "telemetry_host",
    "telemetry_port",
    "log_level",
    "log_format",
    "extensions",
)


def _apply_config_values(  # noqa: PLR0912 - configuration fan-out requires explicit branches
    config: ToolkitConfig,
    values: Mapping[str, object],
    *,
    source: str,
) -> ToolkitConfig:
    if not values:
        return config
    for key, raw in values.items():
        if key not in _KNOWN_KEYS:
            raise ConfigurationError(
                f"Unknown configuration keys in {source}: {key}."
            )
        if key == "allowed_paths":
            config.allowed_paths = _coerce_allowed_paths(raw, source)
        elif key == "timeout_seconds":
            config.timeout_seconds = _coerce_timeout(raw, source)
        elif key == "dangerous_mode":
            config.dangerous_mode = _coerce_bool(raw, source)
        elif key == "default_adapter":
            config.default_adapter = _coerce_string(raw, source, field="default_adapter")
        elif key == "redact_patterns":
            config.redact_patterns = _coerce_patterns(raw, source)
        elif key == "examples_path":
            config.examples_path = _coerce_path(raw, source)
        elif key == "telemetry_enabled":
            config.telemetry_enabled = _coerce_bool(raw, source)
        elif key == "telemetry_host":
            config.telemetry_host = _coerce_string(raw, source, field="telemetry_host")
        elif key == "telemetry_port":
            config.telemetry_port = _coerce_positive_int(raw, source, field="telemetry_port")
        elif key == "log_level":
            config.log_level = _coerce_string(raw, source, field="log_level").upper()
        elif key == "log_format":
            candidate = _coerce_string(raw, source, field="log_format").lower()
            if candidate not in {"text", "json"}:
                raise ConfigurationError(
                    f"log_format in {source} must be 'text' or 'json'."
                )
            config.log_format = candidate
        elif key == "extensions":
            config.extensions = _coerce_string_sequence(raw, source, field="extensions")
    return config


def _coerce_allowed_paths(value: object, source: str) -> tuple[Path, ...]:
    paths: list[str] = []
    if isinstance(value, list | tuple):
        paths = [str(item) for item in value]
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ConfigurationError(
                f"allowed_paths in {source} must contain at least one path."
            )
        separators = {os.pathsep, ";", ","}
        tokens: list[str] = [text]
        for sep in separators:
            tokens = [part for token in tokens for part in token.split(sep)]
        paths = [token for token in (token.strip() for token in tokens) if token]
    else:
        raise ConfigurationError(
            f"allowed_paths in {source} must be a string or list of strings."
        )
    if not paths:
        raise ConfigurationError(
            f"allowed_paths in {source} must contain at least one path."
        )
    return tuple(Path(item).expanduser() for item in paths)


def _coerce_patterns(value: object, source: str) -> tuple[str, ...]:
    patterns: list[str]
    if isinstance(value, list | tuple):
        patterns = [str(item) for item in value if str(item).strip()]
    elif isinstance(value, str):
        candidates = value.replace("\r", "\n").replace(";", "\n").split("\n")
        patterns = [candidate.strip() for candidate in candidates if candidate.strip()]
    else:
        raise ConfigurationError(
            f"redact_patterns in {source} must be a string or list of strings."
        )
    return tuple(patterns)


def _coerce_timeout(value: object, source: str) -> int:
    return _coerce_positive_int(value, source, field="timeout_seconds")


def _coerce_bool(value: object, source: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        numeric = float(value)
        if numeric == 0:
            return False
        if numeric == 1:
            return True
        raise ConfigurationError(
            f"dangerous_mode in {source} must be true/false or 0/1."
        )
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _STR_TRUE:
            return True
        if normalized in _STR_FALSE:
            return False
        raise ConfigurationError(
            f"dangerous_mode in {source} must be a boolean-like string."
        )
    raise ConfigurationError(
        f"dangerous_mode in {source} must be a boolean or boolean-like value."
    )


def _coerce_string(value: object, source: str, *, field: str) -> str:
    if isinstance(value, str):
        candidate = value.strip()
        if candidate:
            return candidate
    raise ConfigurationError(f"{field} in {source} must be a non-empty string.")


def _coerce_path(value: object, source: str) -> Path:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value.strip():
        return Path(value).expanduser()
    raise ConfigurationError(
        f"examples_path in {source} must be a non-empty path string."
    )


def _coerce_positive_int(value: object, source: str, *, field: str) -> int:
    if isinstance(value, bool):
        raise ConfigurationError(f"{field} in {source} must be an integer.")
    if isinstance(value, int | float):
        candidate = int(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ConfigurationError(f"{field} in {source} must not be empty.")
        try:
            candidate = int(text)
        except ValueError as exc:
            raise ConfigurationError(
                f"{field} in {source} must be an integer: {text!r}."
            ) from exc
    else:
        raise ConfigurationError(f"{field} in {source} must be an integer.")
    if candidate <= 0:
        raise ConfigurationError(f"{field} in {source} must be greater than zero.")
    return candidate


def _coerce_string_sequence(value: object, source: str, *, field: str) -> tuple[str, ...]:
    items: list[str]
    if isinstance(value, list | tuple):
        items = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        normalized = value.replace("\r", "\n").replace(";", "\n").replace(",", "\n")
        items = [segment.strip() for segment in normalized.split("\n") if segment.strip()]
    else:
        raise ConfigurationError(f"{field} in {source} must be a string or list of strings.")
    return tuple(items)


__all__ = [
    "ConfigurationError",
    "load_toolkit_config",
    "parse_override_pairs",
]
