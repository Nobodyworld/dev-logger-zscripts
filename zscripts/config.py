"""Configuration primitives used by the zscripts toolkit."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TypedDict


@dataclass
class ToolkitConfig:
    """Runtime configuration for the zscripts CLI.

    Attributes:
        allowed_paths: Paths that sandboxed commands may read.
        timeout_seconds: Maximum runtime for sandboxed subprocesses.
        dangerous_mode: Whether to bypass guardrails.
        default_adapter: Adapter key to use when one is not specified.
        redact_patterns: Collection of string patterns that should be masked
            before presenting logs.
        examples_path: Directory containing bundled example logs exposed by the CLI.
        telemetry_enabled: Whether to expose the HTTP health and metrics server.
        telemetry_host: Interface the telemetry server should bind to.
        telemetry_port: Port number for the telemetry server.
        log_level: Minimum log level for structured logging.
        log_format: Output format for structured logs (``text`` or ``json``).
        report_format: Default formatter name for the ``report`` command.
        report_redact: Whether the ``report`` command redacts collected text by default.
        report_fail_on: Threshold controlling when the ``report`` command exits non-zero.
        extensions: Sequence of dotted module paths for toolkit extensions.
    """

    allowed_paths: Sequence[Path] = field(default_factory=lambda: (Path.cwd(),))
    timeout_seconds: int = 120
    dangerous_mode: bool = False
    default_adapter: str = "python"
    redact_patterns: Sequence[str] = field(
        default_factory=lambda: [
            r"(?i)api[_-]?key\s*=\s*([A-Za-z0-9_-]{10,})",
            r"(?i)token\s*=\s*([A-Za-z0-9_-]{10,})",
            r"([A-Fa-f0-9]{32,})",
        ]
    )
    examples_path: Path = field(default_factory=lambda: Path("examples"))
    telemetry_enabled: bool = False
    telemetry_host: str = "127.0.0.1"
    telemetry_port: int = 9464
    log_level: str = "INFO"
    log_format: str = "text"
    report_format: str = "json"
    report_redact: bool = False
    report_fail_on: str = "never"
    extensions: Sequence[str] = field(default_factory=tuple)


class ToolkitConfigDict(TypedDict):
    """Typed mapping describing :class:`ToolkitConfig` construction parameters."""

    allowed_paths: tuple[Path, ...]
    timeout_seconds: int
    dangerous_mode: bool
    default_adapter: str
    redact_patterns: tuple[str, ...]
    examples_path: Path
    telemetry_enabled: bool
    telemetry_host: str
    telemetry_port: int
    log_level: str
    log_format: str
    report_format: str
    report_redact: bool
    report_fail_on: str
    extensions: tuple[str, ...]


DEFAULT_CONFIG: ToolkitConfigDict = {
    "allowed_paths": (Path.cwd(),),
    "timeout_seconds": 120,
    "dangerous_mode": False,
    "default_adapter": "python",
    "redact_patterns": (
        r"(?i)api[_-]?key\s*=\s*([A-Za-z0-9_-]{10,})",
        r"(?i)token\s*=\s*([A-Za-z0-9_-]{10,})",
        r"([A-Fa-f0-9]{32,})",
    ),
    "examples_path": Path("examples"),
    "telemetry_enabled": False,
    "telemetry_host": "127.0.0.1",
    "telemetry_port": 9464,
    "log_level": "INFO",
    "log_format": "text",
    "report_format": "json",
    "report_redact": False,
    "report_fail_on": "never",
    "extensions": (),
}


def clone_config(config: ToolkitConfig) -> ToolkitConfig:
    """Return a shallow copy of ``config`` suitable for safe mutation."""

    return replace(
        config,
        allowed_paths=tuple(config.allowed_paths),
        redact_patterns=tuple(config.redact_patterns),
        extensions=tuple(config.extensions),
    )


__all__ = ["ToolkitConfig", "ToolkitConfigDict", "DEFAULT_CONFIG", "clone_config"]
