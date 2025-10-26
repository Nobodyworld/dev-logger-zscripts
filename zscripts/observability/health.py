"""HTTP health and metrics server for local observability."""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast

from zscripts.observability.logging import get_logger
from zscripts.observability.metrics import MetricsRegistry, default_registry

StatusProvider = Callable[[], Mapping[str, object]]


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
            handler = _build_handler(self._metrics, self._status_provider)
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
        metrics: MetricsRegistry,
        status_provider: StatusProvider,
    ) -> None:
        self._metrics = metrics
        self._status_provider = status_provider
        super().__init__(request, client_address, server)

    def do_GET(self) -> None:  # noqa: D401 - HTTP handler contract
        if self.path == "/healthz":
            self._handle_health()
        elif self.path == "/healthz/live":
            self._handle_liveness()
        elif self.path == "/healthz/ready":
            self._handle_readiness()
        elif self.path == "/metrics":
            self._handle_metrics()
        else:
            self.send_error(404, "Not Found")

    def log_message(self, format_string: str, *args: object) -> None:  # noqa: D401 - silence default
        logger = get_logger("telemetry.http")
        message = format_string % args if args else format_string
        logger.debug("health-server.access", extra={"message": message})

    def _handle_health(self) -> None:
        payload = _normalize_health_snapshot(self._status_provider())
        status_code = _status_to_code(payload.get("status", "ok"))
        self._respond_json(payload, status_code)

    def _handle_metrics(self) -> None:
        body = self._metrics.collect_prometheus().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_liveness(self) -> None:
        payload = _normalize_health_snapshot(self._status_provider())
        liveness = cast(dict[str, object], payload.get("liveness", {}))
        status_code = _status_to_code(liveness.get("status", payload.get("status", "ok")))
        self._respond_json(liveness, status_code)

    def _handle_readiness(self) -> None:
        payload = _normalize_health_snapshot(self._status_provider())
        readiness = cast(dict[str, object], payload.get("readiness", {}))
        status_code = _status_to_code(readiness.get("status", payload.get("status", "ok")))
        self._respond_json(readiness, status_code)

    def _respond_json(self, payload: Mapping[str, object], status_code: int) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _build_handler(
    metrics: MetricsRegistry, status_provider: StatusProvider
) -> type[_HealthRequestHandler]:
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
                metrics=metrics,
                status_provider=status_provider,
            )

    return Handler


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
