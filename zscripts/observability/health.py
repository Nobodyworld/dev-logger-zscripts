"""HTTP health and metrics server for local observability."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Mapping
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from zscripts.observability.logging import get_logger
from zscripts.observability.metrics import MetricsRegistry, default_registry


class HealthTelemetryServer:
    """Expose health and metrics endpoints over HTTP."""

    def __init__(
        self,
        *,
        metrics: MetricsRegistry | None = None,
        status_provider: Callable[[], Mapping[str, object]] | None = None,
    ) -> None:
        self._metrics = metrics or default_registry
        self._status_provider = status_provider or (lambda: {"status": "ok"})
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
            handler = partial(
                _HealthRequestHandler,
                metrics=self._metrics,
                status_provider=self._status_provider,
            )
            server = ThreadingHTTPServer((host, port), handler)
            server.daemon_threads = True
            server.timeout = 0.5
            self._server = server
            self._host, self._port = server.server_address[0], server.server_address[1]
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
        *args,
        metrics: MetricsRegistry,
        status_provider: Callable[[], Mapping[str, object]],
        **kwargs,
    ) -> None:
        self._metrics = metrics
        self._status_provider = status_provider
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: D401 - HTTP handler contract
        if self.path == "/healthz":
            self._handle_health()
        elif self.path == "/metrics":
            self._handle_metrics()
        else:
            self.send_error(404, "Not Found")

    def log_message(self, format: str, *args: object) -> None:  # noqa: D401 - silence default
        logger = get_logger("telemetry.http")
        logger.debug("health-server.access", extra={"message": format % args})

    def _handle_health(self) -> None:
        payload = self._status_provider()
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_metrics(self) -> None:
        body = self._metrics.collect_prometheus().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


__all__ = ["HealthTelemetryServer"]
