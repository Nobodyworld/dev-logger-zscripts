"""Domain models shared across toolkit layers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SandboxOptions:
    """Configuration describing sandbox execution constraints."""

    allowed_paths: Sequence[Path] = field(default_factory=lambda: (Path.cwd(),))
    timeout_seconds: int = 120
    dangerous_mode: bool = False
    env_allowlist: Sequence[str] = field(
        default_factory=lambda: ("PATH", "HOME", "PYTHONPATH", "VIRTUAL_ENV")
    )


@dataclass(frozen=True)
class SandboxResult:
    """Outcome produced by executing a command inside the sandbox."""

    stdout: str
    stderr: str
    returncode: int


__all__ = ["SandboxOptions", "SandboxResult"]
