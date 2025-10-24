"""Configuration dataclasses and defaults for the toolkit."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path


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


DEFAULT_CONFIG: dict[str, object] = {
    "allowed_paths": (Path.cwd(),),
    "timeout_seconds": 120,
    "dangerous_mode": False,
    "default_adapter": "python",
    "redact_patterns": (
        r"(?i)api[_-]?key\s*=\s*([A-Za-z0-9_-]{10,})",
        r"(?i)token\s*=\s*([A-Za-z0-9_-]{10,})",
        r"([A-Fa-f0-9]{32,})",
    ),
}


__all__ = ["ToolkitConfig", "DEFAULT_CONFIG"]
