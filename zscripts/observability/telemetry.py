"""High-level telemetry manager wiring logging, metrics, and tracing."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass

from zscripts import get_version
from zscripts.observability.health import HealthTelemetryServer
from zscripts.observability.instrumentation import InstrumentationManager
from zscripts.observability.logging import configure_logging, get_logger
from zscripts.observability.metrics import MetricsRegistry, default_registry
from zscripts.observability.tracing import Span, start_span


@dataclass(frozen=True)
class TelemetrySettings:
    """User-configurable telemetry options."""

    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 9464
    log_level: str = "INFO"
    log_format: str = "text"


class TelemetryManager:
    """Coordinate logging, tracing, and optional health server."""

    def __init__(
        self,
        settings: TelemetrySettings,
        *,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self.settings = settings
        self.metrics = metrics or default_registry
        self._logger = get_logger("telemetry")
        self._logging_configured = False
        self._health_server = HealthTelemetryServer(
            metrics=self.metrics,
            status_provider=self._status_payload,
        )

    def start(self) -> None:
        """Ensure logging is configured and start the health server when enabled."""

        self._configure_logging()
        if self.settings.enabled:
            if not self._health_server.is_running():
                self._health_server.start(host=self.settings.host, port=self.settings.port)
                self._logger.info(
                    "telemetry.server.enabled",
                    extra={"host": self._health_server.host, "port": self._health_server.port},
                )

    def stop(self) -> None:
        """Stop background services if they were started."""

        if self._health_server.is_running():
            self._health_server.stop()

    @contextmanager
    def span(self, operation: str, *, attributes: Mapping[str, str] | None = None) -> Iterator[Span]:
        """Start an instrumented span."""

        self._configure_logging()
        with start_span(operation, attributes=attributes, metrics=self.metrics) as span:
            yield span

    @property
    def health_server(self) -> HealthTelemetryServer:
        return self._health_server

    def create_instrumentation(self, component: str) -> InstrumentationManager:
        """Return an instrumentation manager bound to this telemetry instance."""

        return InstrumentationManager(telemetry=self, component=component)

    def snapshot(self, *, include_metrics: bool = False) -> dict[str, object]:
        """Return a diagnostics payload describing telemetry state."""

        payload = dict(self._status_payload())
        if include_metrics:
            metrics_text = self.metrics.collect_prometheus()
            payload["metrics"] = {
                "line_count": len(metrics_text.splitlines()),
                "prometheus_text": metrics_text,
            }
        return payload

    def _configure_logging(self) -> None:
        if not self._logging_configured:
            configure_logging(self.settings.log_level, self.settings.log_format)
            self._logging_configured = True

    def _status_payload(self) -> Mapping[str, object]:
        running = self._health_server.is_running()
        host = self._health_server.host
        port = self._health_server.port
        base_url = f"http://{host}:{port}" if running else None
        enabled = self.settings.enabled
        readiness_status = "ok" if (not enabled or running) else "starting"
        liveness_status = "ok" if running else ("starting" if enabled else "inactive")
        overall_status = "ok" if readiness_status == "ok" else "degraded"
        return {
            "status": overall_status,
            "version": get_version(),
            "telemetry_enabled": self.settings.enabled,
            "health_endpoint": f"{base_url}/healthz" if base_url else None,
            "metrics_endpoint": f"{base_url}/metrics" if base_url else None,
            "liveness": {
                "status": liveness_status,
                "http_server": "running" if running else "stopped",
            },
            "readiness": {
                "status": readiness_status,
                "telemetry": "enabled" if enabled else "disabled",
            },
            "checks": {
                "http_server": {
                    "status": "ok" if running else "unavailable",
                    "host": host,
                    "port": port,
                },
            },
        }


__all__ = ["TelemetryManager", "TelemetrySettings"]
