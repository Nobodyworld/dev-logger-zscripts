"""Application services coordinating domain interfaces for the toolkit."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

from zscripts.application.reporting import ReportBundle, evaluate_report_severity
from zscripts.domain.interfaces import (
    AdapterRegistryProtocol,
    ExampleRepositoryProtocol,
    LogAdapterProtocol,
    RedactorProtocol,
    SandboxRunnerFactory,
    SandboxRunnerProtocol,
    SchemaValidatorProtocol,
)
from zscripts.domain.models import SandboxOptions, SandboxResult
from zscripts.observability.instrumentation import InstrumentationManager
from zscripts.observability.telemetry import TelemetryManager
from zscripts.schemas import NormalizedLog


class ToolkitService:
    """Coordinates adapters, sandboxing, and validation for CLI use cases."""

    def __init__(  # noqa: PLR0913 - dependency injection requires explicit parameters
        self,
        *,
        adapter_registry: AdapterRegistryProtocol,
        sandbox_factory: SandboxRunnerFactory,
        schema_validator: SchemaValidatorProtocol,
        example_repository: ExampleRepositoryProtocol,
        redactor: RedactorProtocol,
        sandbox_options: SandboxOptions,
        default_adapter: str,
        telemetry: TelemetryManager | None = None,
        instrumentation: InstrumentationManager | None = None,
    ) -> None:
        self._registry = adapter_registry
        self._sandbox_factory = sandbox_factory
        self._validator = schema_validator
        self._examples = example_repository
        self._redactor = redactor
        self._sandbox_options = sandbox_options
        self._default_adapter = default_adapter
        self._sandbox_runner: SandboxRunnerProtocol | None = None
        self._telemetry = telemetry
        self._instrumentation = instrumentation
        if self._instrumentation is None and telemetry is not None:
            self._instrumentation = telemetry.create_instrumentation(component="service")

    def collect_logs(
        self,
        *,
        adapter_key: str | None,
        input_path: Path | None,
        command: Sequence[str] | None,
        stdin_fallback: str | None,
        redact: bool,
    ) -> str:
        """Collect raw logs from the requested source.

        Args:
            adapter_key: Identifier of the adapter requested by the caller. If
                omitted, the configured default adapter is used.
            input_path: Optional path to a pre-existing log file that should be
                ingested.
            command: Command sequence to execute in the sandbox when logs need
                to be captured live.
            stdin_fallback: Raw log text read from STDIN. The value must be a
                non-empty string when provided.
            redact: Whether to apply the configured redaction patterns to the
                collected payload before returning it.

        Returns:
            The collected log text, optionally redacted.

        Raises:
            ValueError: If none of ``command``, ``input_path``, or
                ``stdin_fallback`` provide usable log content.
        """

        adapter = self._resolve_adapter(adapter_key)
        attributes = {"adapter": adapter.identifier}
        with self._instrument("collect_logs", attributes):
            payload = self._collect_from_source(
                adapter=adapter,
                input_path=input_path,
                command=command,
                stdin_fallback=stdin_fallback,
            )
            if redact:
                return self._redactor.redact(payload)
            return payload

    def parse_logs(self, *, adapter_key: str | None, raw_text: str) -> NormalizedLog:
        """Parse raw logs into a normalized representation.

        Args:
            adapter_key: Identifier of the adapter that should interpret the
                ``raw_text`` payload.
            raw_text: Raw log output collected from any source.

        Returns:
            The normalized log document produced by the chosen adapter after
            schema validation has been performed.
        """

        adapter = self._resolve_adapter(adapter_key)
        with self._instrument("parse_logs", {"adapter": adapter.identifier}):
            return self._parse_with_adapter(adapter, raw_text)

    def summarize_logs(self, *, adapter_key: str | None, raw_text: str) -> str:
        """Produce a concise summary for the supplied log text."""

        adapter = self._resolve_adapter(adapter_key)
        with self._instrument("summarize_logs", {"adapter": adapter.identifier}):
            normalized = self._parse_with_adapter(adapter, raw_text)
            return adapter.summarize(normalized)

    def explain_logs(self, *, adapter_key: str | None, raw_text: str) -> str:
        """Produce a detailed explanation for the supplied log text."""

        adapter = self._resolve_adapter(adapter_key)
        with self._instrument("explain_logs", {"adapter": adapter.identifier}):
            normalized = self._parse_with_adapter(adapter, raw_text)
            return self._build_explanation(normalized)

    def generate_report(
        self,
        *,
        adapter_key: str | None,
        raw_text: str,
        redact: bool,
    ) -> ReportBundle:
        """Create a comprehensive report bundle for downstream presentation."""

        adapter = self._resolve_adapter(adapter_key)
        with self._instrument("generate_report", {"adapter": adapter.identifier}):
            normalized = self._parse_with_adapter(adapter, raw_text)
            summary = adapter.summarize(normalized)
            explanation = self._build_explanation(normalized)
        guardrails = self.guardrails_snapshot()
        severity = evaluate_report_severity(normalized)
        redacted_text = None
        if redact:
            summary = self._redactor.redact(summary)
            explanation = self._redactor.redact(explanation)
            redacted_text = self._redactor.redact(raw_text)
        return ReportBundle(
            normalized=normalized,
            summary=summary,
            explanation=explanation,
            guardrails=guardrails,
            collected_text=raw_text,
            redacted_text=redacted_text,
            severity=severity,
        )

    def guardrails_snapshot(self) -> dict[str, object]:
        """Expose sandbox configuration for inspection.

        Returns:
            A JSON-serializable mapping describing the active sandbox guardrail
            configuration.
        """

        with self._instrument("guardrails_snapshot", None):
            return {
                "allowed_paths": [str(path) for path in self._sandbox_options.allowed_paths],
                "timeout_seconds": self._sandbox_options.timeout_seconds,
                "dangerous_mode": self._sandbox_options.dangerous_mode,
            }

    def redact_text(self, text: str) -> str:
        """Redact sensitive information using configured patterns.

        Args:
            text: Arbitrary log text that may contain secrets or identifiers.

        Returns:
            The sanitized payload after the configured redaction rules run.
        """

        with self._instrument("redact_text", None):
            return self._redactor.redact(text)

    def list_examples(self, adapter_filter: str | None = None) -> list[str]:
        """Return example log paths as strings for display.

        Args:
            adapter_filter: Optional adapter identifier used to scope results.

        Returns:
            File-system paths to bundled example logs encoded as strings for
            CLI presentation.
        """

        attributes = {"adapter_filter": adapter_filter or "<any>"}
        with self._instrument("list_examples", attributes):
            examples = self._examples.list_examples(adapter_filter)
            return [str(path) for path in examples]

    def _resolve_adapter(self, adapter_key: str | None) -> LogAdapterProtocol:
        key = adapter_key or self._default_adapter
        return self._registry.resolve(key)

    def _run_command(self, command: Sequence[str]) -> str:
        """Execute the provided command using the configured sandbox runner."""

        sanitized = self._ensure_command(command)
        runner = self._get_sandbox_runner()
        result = runner.run(sanitized)
        return self._format_command_output(result)

    @staticmethod
    def _format_command_output(result: SandboxResult) -> str:
        """Normalize sandbox output into a printable payload."""

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
        """Delegate parsing and ensure the resulting payload is validated."""

        normalized = adapter.parse(raw_text)
        self._validator.validate(normalized)
        return normalized

    def _collect_from_source(
        self,
        *,
        adapter: LogAdapterProtocol,
        input_path: Path | None,
        command: Sequence[str] | None,
        stdin_fallback: str | None,
    ) -> str:
        """Resolve the caller's desired collection source.

        The method enforces that a non-empty source is supplied so callers
        receive explicit feedback instead of silently getting an empty string
        when no inputs are provided.
        """

        if command is not None:
            return self._run_command(command)
        if input_path:
            return adapter.collect(input_path, self._sandbox_options)
        if stdin_fallback is not None:
            if stdin_fallback.strip():
                return stdin_fallback
            raise ValueError(
                "STDIN data was empty; provide a command or --input path instead."
            )
        raise ValueError(
            "No log source provided. Supply --command, --input, or pipe log data via STDIN."
        )

    def _get_sandbox_runner(self) -> SandboxRunnerProtocol:
        """Instantiate and cache the sandbox runner for reuse."""

        if self._sandbox_runner is None:
            self._sandbox_runner = self._sandbox_factory(self._sandbox_options)
        return self._sandbox_runner

    @staticmethod
    def _ensure_command(command: Sequence[str]) -> Sequence[str]:
        """Validate that a sandbox command contains an executable token."""

        sanitized = tuple(command)
        if not sanitized or not sanitized[0].strip():
            raise ValueError(
                "Command must include an executable before passing to the sandbox."
            )
        return sanitized

    @contextmanager
    def _instrument(
        self, operation: str, attributes: Mapping[str, str] | None
    ) -> Iterator[None]:
        payload = {str(key): str(value) for key, value in (attributes or {}).items()}
        if self._instrumentation is not None:
            with self._instrumentation.operation(
                operation,
                attributes=payload,
            ):
                yield
            return
        if self._telemetry is not None:
            with self._telemetry.span(operation, attributes=payload):
                yield
            return
        yield

    @staticmethod
    def _build_explanation(normalized: NormalizedLog) -> str:
        """Format an explanatory report for display in the CLI."""

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
