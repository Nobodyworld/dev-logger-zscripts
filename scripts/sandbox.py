"""Sandboxed subprocess utilities with sensible guardrails."""

from __future__ import annotations

import os
import subprocess
from collections.abc import MutableMapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

try:  # pragma: no cover - platform specific branch
    import resource
except ImportError:  # pragma: no cover - Windows fallback
    resource = None  # type: ignore[assignment]


@dataclass
class SandboxSettings:
    """Configuration describing sandbox constraints.

    Attributes:
        allowed_paths: Iterable of directories commands may access.
        timeout_seconds: Maximum command runtime.
        dangerous_mode: If ``True`` guardrails are disabled.
        env_allowlist: Environment variables to preserve when sandboxing.
    """

    allowed_paths: Sequence[Path] = field(default_factory=lambda: (Path.cwd(),))
    timeout_seconds: int = 120
    dangerous_mode: bool = False
    env_allowlist: Sequence[str] = field(
        default_factory=lambda: ("PATH", "HOME", "PYTHONPATH", "VIRTUAL_ENV")
    )


class SandboxRunner:
    """Execute subprocesses with guardrails."""

    def __init__(self, settings: SandboxSettings) -> None:
        self.settings = settings

    def run(self, command: Sequence[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        """Run a command with sandbox restrictions.

        Args:
            command: Command tokens to execute.
            cwd: Optional working directory.

        Returns:
            subprocess.CompletedProcess[str]: Completed process result.
        """

        environment = self._build_environment()
        working_dir = cwd or Path.cwd()
        if not self.settings.dangerous_mode:
            self._assert_within_allowlist(working_dir)

        preexec_fn = self._resource_limiter if resource and not self.settings.dangerous_mode else None

        return subprocess.run(
            command,
            cwd=str(working_dir),
            env=environment,
            timeout=self.settings.timeout_seconds,
            text=True,
            capture_output=True,
            check=False,
            preexec_fn=preexec_fn,
        )

    def _build_environment(self) -> MutableMapping[str, str]:
        base_env = os.environ.copy()
        if self.settings.dangerous_mode:
            return base_env
        sanitized: MutableMapping[str, str] = {}
        for key in self.settings.env_allowlist:
            if key in base_env:
                sanitized[key] = base_env[key]
        sanitized.setdefault("PATH", "/usr/bin:/bin")
        sanitized.setdefault("LANG", "C.UTF-8")
        sanitized.setdefault("LC_ALL", "C.UTF-8")
        return sanitized

    def _assert_within_allowlist(self, path: Path) -> None:
        resolved = path.resolve()
        for allowed in self.settings.allowed_paths:
            if resolved.is_relative_to(allowed.resolve()):
                return
        msg = f"Working directory {resolved} is outside the sandbox allowlist"
        raise PermissionError(msg)

    @staticmethod
    def _resource_limiter() -> None:  # pragma: no cover - requires fork
        if resource is None:
            return
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (20 * 1024 * 1024, 20 * 1024 * 1024))


__all__ = ["SandboxRunner", "SandboxSettings"]
