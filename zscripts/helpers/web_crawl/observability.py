"""Composable observability helpers for the crawler stack.

The crawler already emits metrics, tracing spans, and health snapshots through
dedicated modules. This file provides the missing glue so operators can expose a
single HTTP surface that multiplexes health probes, Prometheus metrics, and
JSON snapshots for custom dashboards or automation agents.

The implementation keeps dependencies optional - if ``prometheus_client`` is
not installed the metrics endpoint simply reports a 503 with remediation tips.
Consumers can register additional JSON endpoints at runtime to surface
extension state (for example the ``EventStreamExtension`` introduced alongside
this module).
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable, Iterable
from wsgiref.simple_server import WSGIServer, make_server

from .health import CrawlerHealth

StartResponse = Callable[[str, list[tuple[str, str]], Any | None], Any]
WSGIApp = Callable[[dict[str, Any], StartResponse], Iterable[bytes]]


def _json_response(
    payload: Any, status: str = "200 OK"
) -> tuple[str, list[tuple[str, str]], bytes]:
    """Serialise ``payload`` to JSON and produce WSGI response metadata."""
    body = json.dumps(payload, default=float).encode("utf-8")
    headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
    return status, headers, body


@dataclass(slots=True)
class JsonEndpoint:
    """Descriptor storing a callable that produces JSON serialisable output."""

    path: str
    producer: Callable[[], Any]

    def render(self) -> tuple[str, list[tuple[str, str]], bytes]:
        """Return a JSON representation of the endpoint payload."""
        return _json_response({"data": self.producer()})


class ObservabilityService:
    """Manage an aggregated observability HTTP surface."""

    def __init__(
        self,
        health: CrawlerHealth,
        *,
        metrics_app: WSGIApp | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialise the service with health tracking and optional metrics."""
        self._health = health
        self._metrics_app = metrics_app
        self._logger = logger or logging.getLogger(__name__)
        self._json_endpoints: dict[str, JsonEndpoint] = {}
        self._lock = threading.RLock()
        self._server: WSGIServer | None = None
        self._thread: threading.Thread | None = None

    def add_json_endpoint(self, path: str, producer: Callable[[], Any]) -> None:
        """Expose ``producer`` at ``path`` returning a JSON document.

        Paths must start with ``/`` and are normalised to avoid duplicates.
        Subsequent registrations override the existing producer which enables
        hot-swapping agents while the server remains online.
        """
        if not path.startswith("/"):
            raise ValueError("Endpoint paths must start with '/'")
        normalised = path.rstrip("/") or "/"
        with self._lock:
            self._json_endpoints[normalised] = JsonEndpoint(normalised, producer)

    def remove_json_endpoint(self, path: str) -> None:
        """Remove a previously registered JSON endpoint if present."""
        normalised = path.rstrip("/") or "/"
        with self._lock:
            self._json_endpoints.pop(normalised, None)

    # -- Server lifecycle -------------------------------------------------
    def start(self, host: str, port: int) -> None:
        """Start the observability HTTP server in a background thread."""
        if self._server is not None:  # pragma: no cover - guard against misuse
            raise RuntimeError("ObservabilityService is already running")
        app = self.wsgi_app()
        self._server = make_server(host, port, app)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._logger.info("Observability server listening on http://%s:%s", host, port)

    def stop(self) -> None:
        """Stop the background HTTP server if it is running."""
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        if self._thread is not None:
            self._thread.join(timeout=1)
        self._thread = None

    def wsgi_app(self) -> WSGIApp:
        """Return a WSGI application multiplexing health + metrics + JSON."""
        health_app = self._health.wsgi_app()
        metrics_app = self._metrics_app

        def app(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
            path = environ.get("PATH_INFO", "") or "/"
            with self._lock:
                endpoints_snapshot = dict(self._json_endpoints)

            if path in {"", "/"}:
                endpoints = {
                    "health": ["/healthz", "/readyz", "/livez"],
                    "json": sorted(endpoints_snapshot),
                }
                if metrics_app is not None:
                    endpoints["metrics"] = ["/metrics"]
                status, headers, body = _json_response(
                    {"status": self._health.snapshot(), "endpoints": endpoints}
                )
                start_response(status, headers, None)
                return [body]

            if path in {"/healthz", "/readyz", "/livez"}:
                return list(health_app(environ, start_response))

            if path.startswith("/metrics"):
                if metrics_app is None:
                    status, headers, body = _json_response(
                        {
                            "error": "metrics disabled",
                            "hint": "Install prometheus_client and enable Prometheus telemetry.",
                        },
                        status="503 Service Unavailable",
                    )
                    start_response(status, headers, None)
                    return [body]
                return list(metrics_app(environ, start_response))

            endpoint = endpoints_snapshot.get(path.rstrip("/") or "/")
            if endpoint is not None:
                status, headers, body = endpoint.render()
                start_response(status, headers, None)
                return [body]

            known_paths = ["/", "/healthz", "/readyz", "/livez"]
            if metrics_app is not None:
                known_paths.append("/metrics")
            known_paths.extend(sorted(endpoints_snapshot))
            status, headers, body = _json_response(
                {"error": "unknown endpoint", "paths": known_paths},
                status="404 Not Found",
            )
            start_response(status, headers, None)
            return [body]

        return app


def prometheus_wsgi_app(registry: Any) -> WSGIApp:
    """Return a Prometheus WSGI app for ``registry`` if the dependency exists."""
    try:
        from prometheus_client import make_wsgi_app
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("prometheus_client is required for the metrics endpoint") from exc
    return make_wsgi_app(registry)


__all__ = [
    "ObservabilityService",
    "prometheus_wsgi_app",
]

