"""Typed configuration primitives for the zscripts toolkit."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Dataclass definitions
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ToolkitConfig:
    """Runtime configuration shared across the CLI and application services.

    Attributes:
        allowed_paths: Whitelisted directories that sandboxed commands may
            access. Defaults to the current working directory.
        timeout_seconds: Maximum execution time granted to sandboxed commands.
        dangerous_mode: When ``True`` relaxes sandbox guardrails (dangerous).
        default_adapter: Adapter key used when callers omit ``--adapter``.
        redact_patterns: Patterns passed to the redactor to scrub secrets.
        examples_path: Base directory containing bundled example logs.
        telemetry_enabled: Whether telemetry services (HTTP/metrics) start.
        telemetry_host: Host interface for the telemetry HTTP server.
        telemetry_port: Port for the telemetry HTTP server.
        log_level: Log level consumed by :func:`logging.getLevelName`.
        log_format: Either ``"text"`` or ``"json"`` for structured logging.
        extensions: Python modules that expose toolkit extensions.
        report_format: Default report format (``"json"`` or ``"markdown"``).
        report_redact: Whether report payloads are redacted by default.
        report_fail_on: Severity threshold that forces a non-zero exit code
            (``"never"``, ``"warnings"``, or ``"errors"``).
    """

    allowed_paths: tuple[Path, ...] = (Path.cwd(),)
    timeout_seconds: int = 120
    dangerous_mode: bool = False
    default_adapter: str = "python"
    redact_patterns: tuple[str, ...] = ()
    examples_path: Path = Path("examples")
    telemetry_enabled: bool = False
    telemetry_host: str = "127.0.0.1"
    telemetry_port: int = 9464
    log_level: str = "INFO"
    log_format: str = "text"
    extensions: tuple[str, ...] = ()
    report_format: str = "json"
    report_redact: bool = False
    report_fail_on: str = "never"


# ---------------------------------------------------------------------------
# Defaults and cloning utilities
# ---------------------------------------------------------------------------


DEFAULT_CONFIG: dict[str, Any] = {
    "allowed_paths": (Path.cwd(),),
    "timeout_seconds": 120,
    "dangerous_mode": False,
    "default_adapter": "python",
    "redact_patterns": tuple(),
    "examples_path": Path("examples"),
    "telemetry_enabled": False,
    "telemetry_host": "127.0.0.1",
    "telemetry_port": 9464,
    "log_level": "INFO",
    "log_format": "text",
    "extensions": tuple(),
    "report_format": "json",
    "report_redact": False,
    "report_fail_on": "never",
}


_TEMPLATE_CONFIG = ToolkitConfig(**DEFAULT_CONFIG)


def get_default_config() -> ToolkitConfig:
    """Return a fresh :class:`ToolkitConfig` populated with default values."""

    return clone_config(_TEMPLATE_CONFIG)


def clone_config(config: ToolkitConfig) -> ToolkitConfig:
    """Create a deep copy of ``config`` suitable for further mutation."""

    return ToolkitConfig(
        allowed_paths=tuple(Path(path) for path in config.allowed_paths),
        timeout_seconds=int(config.timeout_seconds),
        dangerous_mode=bool(config.dangerous_mode),
        default_adapter=str(config.default_adapter),
        redact_patterns=tuple(str(pattern) for pattern in config.redact_patterns),
        examples_path=Path(config.examples_path),
        telemetry_enabled=bool(config.telemetry_enabled),
        telemetry_host=str(config.telemetry_host),
        telemetry_port=int(config.telemetry_port),
        log_level=str(config.log_level),
        log_format=str(config.log_format),
        extensions=tuple(str(module) for module in config.extensions),
        report_format=str(config.report_format),
        report_redact=bool(config.report_redact),
        report_fail_on=str(config.report_fail_on),
    )


__all__ = ["ToolkitConfig", "DEFAULT_CONFIG", "get_default_config", "clone_config"]


# ---------------------------------------------------------------------------
# Legacy constants retained for backwards compatibility with legacy scripts
# and operations helpers. These values mirror the historical configuration
# module so existing workflows continue to function while the new configuration
# layer evolves.
# ---------------------------------------------------------------------------

SKIP_DIRS = tuple(
    dict.fromkeys(
        [
            "zscripts",
            "zbuild",
            "migrations",
            "static",
            "yayay",
            "asgi",
            "wsgi",
            "staticfiles",
            "logs",
            "media",
            "__pycache__",
            "build",
            "dist",
            "venv",
            "env",
            "envs",
            "node_modules",
            "public",
            "assets",
            ".git.txt",
        ]
    )
)

FILE_TYPES = {
    "admin.py": "admin_files",
    "apps.py": "apps_files",
    "forms.py": "forms_files",
    "models.py": "models_files",
    "signals.py": "signals_files",
    "tests.py": "tests_files",
    "urls.py": "urls_files",
    "views.py": "views_files",
    "utils.py": "utils_files",
}

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
LOG_DIR = SCRIPT_DIR / "logs"
BUILD_DIR = LOG_DIR / "build_files"
ANALYSIS_DIR = LOG_DIR / "analysis_logs"
CONSOLIDATION_DIR = LOG_DIR / "consoli_files"
WORK_DIR = LOG_DIR / "logs_files"
TREE_LOG_DIR = LOG_DIR / "logs_tree"

ALL_LOG_DIR = LOG_DIR / "logs_apps_all"
PYTHON_LOG_DIR = LOG_DIR / "logs_apps_pyth"
HTML_LOG_DIR = LOG_DIR / "logs_apps_html"
CSS_LOG_DIR = LOG_DIR / "logs_apps_css"
JS_LOG_DIR = LOG_DIR / "logs_apps_js"
BOTH_LOG_DIR = LOG_DIR / "logs_apps_both"
SINGLE_LOG_DIR = LOG_DIR / "logs_single_files"

CAPTURE_ALL_PYTHON_LOG = SINGLE_LOG_DIR / "capture_all_pyth.txt"
CAPTURE_ALL_HTML_LOG = SINGLE_LOG_DIR / "capture_all_html.txt"
CAPTURE_ALL_CSS_LOG = SINGLE_LOG_DIR / "capture_all_css.txt"
CAPTURE_ALL_JS_LOG = SINGLE_LOG_DIR / "capture_all_js.txt"
CAPTURE_ALL_PYTHON_HTML_LOG = SINGLE_LOG_DIR / "capture_all_python_html.txt"
CAPTURE_ALL_LOG = SINGLE_LOG_DIR / "capture_all.txt"

FILE_TYPE_PRESETS = {
    "python": {".py"},
    "html": {".html"},
    "css": {".css"},
    "javascript": {".js"},
    "python-html": {".py", ".html"},
    "all": {".py", ".html", ".css", ".js"},
}


__all__.extend(
    [
        "SKIP_DIRS",
        "FILE_TYPES",
        "SCRIPT_DIR",
        "PROJECT_ROOT",
        "LOG_DIR",
        "BUILD_DIR",
        "ANALYSIS_DIR",
        "CONSOLIDATION_DIR",
        "WORK_DIR",
        "TREE_LOG_DIR",
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
        "FILE_TYPE_PRESETS",
    ]
)
