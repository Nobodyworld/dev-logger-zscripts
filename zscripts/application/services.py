"""Application services coordinating domain interfaces for the toolkit."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from zscripts.domain.interfaces import (
    AdapterRegistryProtocol,
    ExampleRepositoryProtocol,
    LogAdapterProtocol,
    RedactorProtocol,
    SandboxRunnerFactory,
    SchemaValidatorProtocol,
)
from zscripts.domain.models import SandboxOptions, SandboxResult
from zscripts.schemas import NormalizedLog


class ToolkitService:
    """Coordinates adapters, sandboxing, and validation for CLI use cases."""

    def __init__(
        self,
        *,
        adapter_registry: AdapterRegistryProtocol,
        sandbox_factory: SandboxRunnerFactory,
        schema_validator: SchemaValidatorProtocol,
        example_repository: ExampleRepositoryProtocol,
        redactor: RedactorProtocol,
        sandbox_options: SandboxOptions,
        default_adapter: str,
    ) -> None:
        self._registry = adapter_registry
        self._sandbox_factory = sandbox_factory
        self._validator = schema_validator
        self._examples = example_repository
        self._redactor = redactor
        self._sandbox_options = sandbox_options
        self._default_adapter = default_adapter

    def collect_logs(
        self,
        *,
        adapter_key: str | None,
        input_path: Path | None,
        command: Sequence[str] | None,
        stdin_fallback: str | None,
        redact: bool,
    ) -> str:
        """Collect raw logs from a file, STDIN, or sandboxed command."""

        adapter = self._resolve_adapter(adapter_key)
        payload: str
        if command:
            payload = self._run_command(command)
        elif input_path:
            payload = adapter.collect(input_path, self._sandbox_options)
        elif stdin_fallback is not None:
            payload = stdin_fallback
        else:
            payload = ""
        if redact:
            payload = self._redactor.redact(payload)
        return payload

    def parse_logs(self, *, adapter_key: str | None, raw_text: str) -> NormalizedLog:
        """Parse raw logs into a normalized representation."""

        adapter = self._resolve_adapter(adapter_key)
        return self._parse_with_adapter(adapter, raw_text)

    def summarize_logs(self, *, adapter_key: str | None, raw_text: str) -> str:
        """Parse raw logs and return a concise summary."""

        adapter = self._resolve_adapter(adapter_key)
        normalized = self._parse_with_adapter(adapter, raw_text)
        return adapter.summarize(normalized)

    def explain_logs(self, *, adapter_key: str | None, raw_text: str) -> str:
        """Parse raw logs and build a detailed explanation."""

        adapter = self._resolve_adapter(adapter_key)
        normalized = self._parse_with_adapter(adapter, raw_text)
        return self._build_explanation(normalized)

    def guardrails_snapshot(self) -> dict[str, object]:
        """Expose sandbox configuration for inspection."""

        return {
            "allowed_paths": [str(path) for path in self._sandbox_options.allowed_paths],
            "timeout_seconds": self._sandbox_options.timeout_seconds,
            "dangerous_mode": self._sandbox_options.dangerous_mode,
        }

    def redact_text(self, text: str) -> str:
        """Redact sensitive information using configured patterns."""

        return self._redactor.redact(text)

    def list_examples(self, adapter_filter: str | None = None) -> list[str]:
        """Return example log paths as strings for display."""

        examples = self._examples.list_examples(adapter_filter)
        return [str(path) for path in examples]

    def _resolve_adapter(self, adapter_key: str | None) -> LogAdapterProtocol:
        key = adapter_key or self._default_adapter
        return self._registry.resolve(key)

    def _run_command(self, command: Sequence[str]) -> str:
        runner = self._sandbox_factory(self._sandbox_options)
        result = runner.run(command)
        return self._format_command_output(result)

    @staticmethod
    def _format_command_output(result: SandboxResult) -> str:
        sections = [segment for segment in (result.stdout, result.stderr) if segment]
        payload = "\n".join(sections)
        if result.returncode != 0:
            if payload:
                payload += "\n"
            payload += f"Command exited with {result.returncode}"
        return payload

    def _parse_with_adapter(
        self, adapter: LogAdapterProtocol, raw_text: str
    ) -> NormalizedLog:
        normalized = adapter.parse(raw_text)
        self._validator.validate(normalized)
        return normalized

    @staticmethod
    def _build_explanation(normalized: NormalizedLog) -> str:
        lines = [
            f"Tool: {normalized.tool}",
            f"Ecosystem: {normalized.ecosystem}",
            f"Status: {normalized.status}",
            f"Summary: {normalized.summary}",
        ]
        if normalized.tests:
            lines.append(
                "Tests: "
                f"passed={normalized.tests.passed} "
                f"failed={normalized.tests.failed} "
                f"skipped={normalized.tests.skipped}"
            )
        if normalized.errors:
            lines.append("Errors:")
            for issue in normalized.errors:
                lines.append(f"  - {issue.message} ({issue.file}:{issue.line})")
        if normalized.warnings:
            lines.append("Warnings:")
            for issue in normalized.warnings:
                lines.append(f"  - {issue.message} ({issue.file}:{issue.line})")
        if normalized.artifacts:
            lines.append("Artifacts:")
            for artifact in normalized.artifacts:
                lines.append(f"  - {artifact}")
        if normalized.metadata:
            lines.append("Metadata:")
            for key, value in normalized.metadata.items():
                lines.append(f"  - {key}: {value}")
        return "\n".join(lines)


__all__ = ["ToolkitService"]
