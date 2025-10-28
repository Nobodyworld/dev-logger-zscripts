"""Factories wiring domain interfaces to infrastructure implementations."""

from __future__ import annotations

from zscripts.application.services import ToolkitService
from zscripts.config import ToolkitConfig
from zscripts.domain.interfaces import AdapterRegistryProtocol
from zscripts.domain.models import SandboxOptions
from zscripts.infrastructure.adapters import AdapterRegistry
from zscripts.infrastructure.examples import FileSystemExampleRepository
from zscripts.infrastructure.redaction import RegexRedactor
from zscripts.infrastructure.sandbox import build_sandbox_runner
from zscripts.infrastructure.schema import JsonSchemaValidator
from zscripts.observability.instrumentation import InstrumentationManager
from zscripts.observability.telemetry import TelemetryManager


def build_toolkit_service(
    config: ToolkitConfig,
    *,
    adapter_registry: AdapterRegistryProtocol | None = None,
    telemetry: TelemetryManager | None = None,
    instrumentation: InstrumentationManager | None = None,
) -> ToolkitService:
    """Assemble a :class:`ToolkitService` wired to in-repo infrastructure."""

    sandbox_options = SandboxOptions(
        allowed_paths=tuple(config.allowed_paths),
        timeout_seconds=config.timeout_seconds,
        dangerous_mode=config.dangerous_mode,
    )
    registry_impl = adapter_registry or AdapterRegistry()
    validator = JsonSchemaValidator()
    examples = FileSystemExampleRepository(config.examples_path)
    redactor = RegexRedactor(config.redact_patterns)
    return ToolkitService(
        adapter_registry=registry_impl,
        sandbox_factory=build_sandbox_runner,
        schema_validator=validator,
        example_repository=examples,
        redactor=redactor,
        sandbox_options=sandbox_options,
        default_adapter=config.default_adapter,
        telemetry=telemetry,
        instrumentation=instrumentation,
    )


__all__ = ["build_toolkit_service"]
