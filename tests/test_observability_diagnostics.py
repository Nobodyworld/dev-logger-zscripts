from __future__ import annotations

from zscripts import get_default_config
from zscripts.extensions import ExtensionContext, ExtensionHookRegistry, load_extensions
from zscripts.infrastructure.adapters import AdapterRegistry
from zscripts.observability.diagnostics import collect_runtime_diagnostics
from zscripts.observability.instrumentation import InstrumentationManager
from zscripts.observability.logging import get_logger
from zscripts.observability.telemetry import TelemetryManager, TelemetrySettings


def _build_context(telemetry: TelemetryManager) -> ExtensionContext:
    instrumentation = InstrumentationManager(telemetry=telemetry, component="test")
    return ExtensionContext(
        config=get_default_config(),
        adapter_registry=AdapterRegistry(),
        telemetry=telemetry,
        instrumentation=instrumentation,
        logger=get_logger("extensions.test"),
        hook_registry=ExtensionHookRegistry(instrumentation),
        health_checks=telemetry.health_checks,
    )


def test_collect_runtime_diagnostics_includes_hooks() -> None:
    telemetry = TelemetryManager(TelemetrySettings(enabled=False))
    context = _build_context(telemetry)
    manager = load_extensions(["zscripts.extensions.examples.plugin_metrics"], context=context)

    snapshot = collect_runtime_diagnostics(
        telemetry=telemetry,
        instrumentation=context.instrumentation,
        extensions=manager,
        include_metrics=True,
    )

    payload = snapshot.to_dict()
    assert payload["component"] == "test"
    telemetry_data = payload["telemetry"]
    assert isinstance(telemetry_data, dict)
    assert "metrics" in telemetry_data
    assert "health_checks" in telemetry_data
    assert telemetry_data["health_checks"]["summary"]["total"] >= 0
    extension_data = payload["extensions"]
    assert extension_data["count"] == 1
    assert extension_data["hooks"].get("service_ready") == 1
