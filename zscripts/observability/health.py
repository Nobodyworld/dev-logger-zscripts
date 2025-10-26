"""HTTP health and metrics server for local observability."""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast

from zscripts.observability.logging import get_logger
from zscripts.observability.metrics import (
    CounterMetric,
    GaugeMetric,
    HistogramMetric,
    MetricsRegistry,
    default_registry,
)

StatusProvider = Callable[[], Mapping[str, object]]


@dataclass(slots=True)
class _RequestMetrics:
    counter: CounterMetric
    duration: HistogramMetric
    inflight: GaugeMetric


@dataclass(slots=True)
class _HandlerContext:
    metrics: MetricsRegistry
    status_provider: StatusProvider
    requests: _RequestMetrics


class HealthTelemetryServer:
    """Expose health and metrics endpoints over HTTP."""

    def __init__(
        self,
        *,
        metrics: MetricsRegistry | None = None,
        status_provider: StatusProvider | None = None,
    ) -> None:
        self._metrics = metrics or default_registry
        self._status_provider: StatusProvider = status_provider or (lambda: {"status": "ok"})
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._host = "127.0.0.1"
        self._port = 0
        self._logger = get_logger("telemetry.health")
        self._request_counter = self._metrics.counter(
            "zscripts_health_http_requests_total",
            "HTTP requests served by the telemetry health endpoints.",
        )
        self._request_duration = self._metrics.histogram(
            "zscripts_health_http_request_duration_seconds",
            "Duration of telemetry health HTTP requests in seconds.",
        )
        self._request_inflight = self._metrics.gauge(
            "zscripts_health_http_requests_inflight",
            "Number of in-flight telemetry health HTTP requests.",
        )
        request_metrics = _RequestMetrics(
            counter=self._request_counter,
            duration=self._request_duration,
            inflight=self._request_inflight,
        )
        self._handler_context = _HandlerContext(
            metrics=self._metrics,
            status_provider=self._status_provider,
            requests=request_metrics,
        )

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    def start(self, *, host: str = "127.0.0.1", port: int = 9464) -> None:
        """Start the background HTTP server."""

        with self._lock:
            if self._server is not None:
                return
            handler = _build_handler(self._handler_context)
            server = ThreadingHTTPServer((host, port), handler)
            server.daemon_threads = True
            server.timeout = 0.5
            self._server = server
            host_value, port_value = cast(tuple[str, int], server.server_address)
            self._host = host_value
            self._port = port_value
            self._thread = threading.Thread(
                target=server.serve_forever,
                name="zscripts-health-server",
                daemon=True,
            )
            self._thread.start()
            self._logger.info(
                "health-server.started",
                extra={"host": self._host, "port": self._port},
            )

    def stop(self) -> None:
        """Stop the server and release the bound port."""

        with self._lock:
            if self._server is None:
                return
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            if self._thread is not None:
                self._thread.join(timeout=1)
            self._thread = None
            self._logger.info("health-server.stopped")

    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()


class _HealthRequestHandler(BaseHTTPRequestHandler):
    """Serve health and metrics endpoints."""

    server_version = "zscripts-health/1.0"

    def __init__(
        self,
        request: socket.socket,
        client_address: tuple[str, int],
        server: ThreadingHTTPServer,
        *,
        context_bundle: _HandlerContext,
    ) -> None:
        self._metrics = context_bundle.metrics
        self._status_provider = context_bundle.status_provider
        self._request_metrics = context_bundle.requests
        super().__init__(request, client_address, server)

    def do_GET(self) -> None:  # noqa: D401 - HTTP handler contract
        # agent-entrypoint: central hook for health/metrics HTTP automation.
        endpoint = _canonical_endpoint(self.path)
        labels = {"method": "GET", "endpoint": endpoint}
        self._request_metrics.inflight.inc(labels=labels)
        status_code = 500
        start = time.perf_counter()
        try:
            handlers: dict[str, Callable[[], int]] = {
                "/healthz": partial(self._serve_snapshot, None),
                "/healthz/live": partial(self._serve_snapshot, "liveness"),
                "/healthz/ready": partial(self._serve_snapshot, "readiness"),
                "/metrics": self._handle_metrics,
            }
            handler = handlers.get(self.path)
            if handler is None:
                self.send_error(404, "Not Found")
                status_code = 404
            else:
                status_code = handler()
        finally:
            duration = time.perf_counter() - start
            enriched = {**labels, "status": str(status_code)}
            self._request_metrics.duration.observe(duration, labels=enriched)
            self._request_metrics.counter.inc(labels=enriched)
            self._request_metrics.inflight.dec(labels=labels)

    def log_message(self, format_string: str, *args: object) -> None:  # noqa: D401 - silence default
        logger = get_logger("telemetry.http")
        message = format_string % args if args else format_string
        logger.debug("health-server.access", extra={"message": message})

    def _handle_metrics(self) -> int:
        body = self._metrics.collect_prometheus().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return 200

    def _serve_snapshot(self, section: str | None = None) -> int:
        payload = _normalize_health_snapshot(self._status_provider())
        if section is None:
            status_value = payload.get("status", "ok")
            body: Mapping[str, object] = payload
        else:
            subsection = cast(dict[str, object], payload.get(section, {}))
            status_value = subsection.get("status", payload.get("status", "ok"))
            body = subsection
        status_code = _status_to_code(status_value)
        return self._respond_json(body, status_code)

    def _respond_json(self, payload: Mapping[str, object], status_code: int) -> int:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return status_code


def _build_handler(context_bundle: _HandlerContext) -> type[_HealthRequestHandler]:
    class Handler(_HealthRequestHandler):
        def __init__(
            self,
            request: socket.socket,
            client_address: tuple[str, int],
            server: ThreadingHTTPServer,
        ) -> None:
            super().__init__(
                request,
                client_address,
                server,
                context_bundle=context_bundle,
            )

    return Handler


def _canonical_endpoint(path: str) -> str:
    match path:
        case "/healthz":
            return "healthz"
        case "/healthz/ready":
            return "healthz_ready"
        case "/healthz/live":
            return "healthz_live"
        case "/metrics":
            return "metrics"
        case _:
            return "unknown"


def _normalize_health_snapshot(raw: Mapping[str, object]) -> dict[str, object]:
    """Ensure health snapshots contain readiness and liveness sections."""

    snapshot = dict(raw)
    status = str(snapshot.get("status", "ok"))
    snapshot["status"] = status
    liveness_candidate = snapshot.get("liveness")
    if isinstance(liveness_candidate, Mapping):
        liveness: dict[str, object] = {
            str(key): value for key, value in liveness_candidate.items()
        }
    else:
        liveness = {"status": status}
    liveness.setdefault("status", status)
    readiness_candidate = snapshot.get("readiness")
    if isinstance(readiness_candidate, Mapping):
        readiness: dict[str, object] = {
            str(key): value for key, value in readiness_candidate.items()
        }
    else:
        readiness = {"status": status}
    readiness.setdefault("status", status)
    checks_candidate = snapshot.get("checks")
    if isinstance(checks_candidate, Mapping):
        checks: dict[str, object] = {
            str(key): value for key, value in checks_candidate.items()
        }
    else:
        checks = {}
    snapshot["liveness"] = liveness
    snapshot["readiness"] = readiness
    snapshot["checks"] = checks
    return snapshot


def _status_to_code(status: object) -> int:
    """Map human-readable status strings to HTTP status codes."""

    value = str(status).strip().lower()
    if value in {"ok", "pass", "ready", "live"}:
        return 200
    return 503


__all__ = ["HealthTelemetryServer"]
