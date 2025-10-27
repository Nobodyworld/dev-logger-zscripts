"""Example extension that registers hook-based diagnostics callbacks."""

from __future__ import annotations

from typing import Any

from zscripts.extensions.base import ExtensionContext, ToolkitExtension


class MetricsProbeExtension(ToolkitExtension):
    """Log hook registrations and emit diagnostics when the service is ready."""

    name = "metrics_probe"
    description = "Records hook activity for diagnostics"
    version = "1.0.0"
    capabilities = ("hooks", "diagnostics")

    def on_load(self, context: ExtensionContext) -> None:
        super().on_load(context)
        self.register_hook("service_ready", self._on_service_ready)
        context.logger.debug(
            "extension.metrics_probe.hook_registered",
            extra={"extension": self.name, "hook": "service_ready"},
        )

    def _on_service_ready(self, **kwargs: Any) -> None:
        manifest = self.manifest
        payload = {
            "extension": self.name,
            "hook": "service_ready",
            "manifest": manifest.to_dict() if manifest is not None else None,
        }
        self.context.logger.info("extension.metrics_probe.ready", extra=payload)


def get_extension() -> MetricsProbeExtension:
    """Factory used by the loader."""

    return MetricsProbeExtension()
