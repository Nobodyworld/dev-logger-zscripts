"""Infrastructure adapters for sandboxed command execution."""

from __future__ import annotations

from collections.abc import Sequence

from scripts import SandboxRunner, SandboxSettings

from zscripts.domain.interfaces import SandboxRunnerProtocol
from zscripts.domain.models import SandboxOptions, SandboxResult


class SandboxCommandRunner(SandboxRunnerProtocol):
    """Adapter that exposes ``SandboxRunner`` through the domain protocol."""

    def __init__(self, runner: SandboxRunner) -> None:
        self._runner = runner

    def run(self, command: Sequence[str]) -> SandboxResult:
        completed = self._runner.run(command)
        return SandboxResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
        )


def build_sandbox_runner(options: SandboxOptions) -> SandboxRunnerProtocol:
    """Create a sandbox runner configured from domain options."""

    settings = SandboxSettings(
        allowed_paths=options.allowed_paths,
        timeout_seconds=options.timeout_seconds,
        dangerous_mode=options.dangerous_mode,
        env_allowlist=options.env_allowlist,
    )
    return SandboxCommandRunner(SandboxRunner(settings))


__all__ = ["SandboxCommandRunner", "build_sandbox_runner"]
