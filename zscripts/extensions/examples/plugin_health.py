from __future__ import annotations

from typing import Any

from zscripts.extensions.base import ExtensionContext, ToolkitExtension


class HealthMonitorExtension(ToolkitExtension):
    """Expose extension-level health information to telemetry consumers."""

    name = "health_monitor"
    description = "Publishes readiness checks for extension subsystems"
    version = "1.0.0"
    capabilities = ("health", "diagnostics")
    config_keys: tuple[str, ...] = ()

    def on_load(self, context: ExtensionContext) -> None:
        super().on_load(context)
        context.health_checks.register(
            "extensions.health_monitor",
            self._health_snapshot,
            kind="extension",
            description="Reports health-monitor extension readiness.",
        )
        self.register_hook("service_ready", self._on_service_ready)
        context.logger.debug(
            "extension.health_monitor.hook_registered",
            extra={"extension": self.name, "hook": "service_ready"},
        )

    def _on_service_ready(self, **_: Any) -> None:
        with self.context.instrumentation.operation(
            "extension.health_monitor.ready",
            attributes={"extension": self.name},
        ):
            self.context.logger.info(
                "extension.health_monitor.ready",
                extra={"extension": self.name, "status": "ok"},
            )

    def _health_snapshot(self) -> dict[str, object]:
        manifest = self.manifest
        registry = self.context.hook_registry
        return {
            "status": "ok",
            "extension": self.name,
            "version": manifest.version if manifest is not None else self.version,
            "hooks": tuple(sorted(registry.summary().keys())) if registry else (),
        }


def get_extension() -> HealthMonitorExtension:
    """Factory used by the extension loader."""

    return HealthMonitorExtension()
