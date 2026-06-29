"""Health reporting utilities for the web crawler."""

from __future__ import annotations

import json
import threading
import time
from http import HTTPStatus
from typing import Any, Callable, Iterable

StartResponse = Callable[[str, list[tuple[str, str]], Any], Any]


class CrawlerHealth:
    """Thread-safe health tracker exposed by the crawler."""

    def __init__(self) -> None:
        """Initialise the internal counters and state."""
        self._lock = threading.RLock()
        self.status = "idle"
        self.last_started: float | None = None
        self.last_finished: float | None = None
        self.last_error: str | None = None
        self.last_error_url: str | None = None
        self.pages_crawled = 0
        self.last_crawled_url: str | None = None
        self.skipped_urls: list[tuple[str, str]] = []
        self.queue_depth = 0
        self.root_url: str | None = None

    def report_start(self, root_url: str) -> None:
        """Mark the start of a crawl and reset state."""
        with self._lock:
            self.status = "running"
            self.last_started = time.time()
            self.root_url = root_url
            self.last_error = None
            self.last_error_url = None
            self.pages_crawled = 0
            self.skipped_urls = []
            self.last_crawled_url = None

    def record_queue_depth(self, depth: int) -> None:
        """Update the recorded queue depth."""
        with self._lock:
            self.queue_depth = depth

    def record_page(self, url: str) -> None:
        """Record a successfully crawled page and mark the crawl healthy."""
        with self._lock:
            self.pages_crawled += 1
            self.last_finished = time.time()
            self.status = "healthy"
            self.last_error = None
            self.last_error_url = None
            self.last_crawled_url = url

    def record_skip(self, url: str, reason: str) -> None:
        """Track URLs skipped by the crawler with their reasons."""
        with self._lock:
            self.skipped_urls.append((url, reason))

    def record_error(self, url: str, error: Exception) -> None:
        """Record a terminal error encountered during the crawl."""
        with self._lock:
            self.status = "degraded"
            self.last_error = str(error)
            self.last_error_url = url
            self.last_finished = time.time()

    def report_finish(self, success: bool) -> None:
        """Record the completion of a crawl run."""
        with self._lock:
            self.last_finished = time.time()
            if success and self.status != "degraded":
                self.status = "healthy"
            elif not success:
                self.status = "degraded"

    def snapshot(self) -> dict[str, Any]:
        """Return a copy of the current health status."""
        with self._lock:
            return {
                "status": self.status,
                "root_url": self.root_url,
                "last_started": self.last_started,
                "last_finished": self.last_finished,
                "last_error": self.last_error,
                "last_error_url": self.last_error_url,
                "pages_crawled": self.pages_crawled,
                "queue_depth": self.queue_depth,
                "skipped_urls": list(self.skipped_urls),
                "last_crawled_url": self.last_crawled_url,
            }

    def wsgi_app(self) -> Callable[[dict[str, Any], StartResponse], Iterable[bytes]]:
        """Return a simple WSGI app serving health information."""

        def app(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
            path = environ.get("PATH_INFO", "")
            snapshot = self.snapshot()
            if path in {"/healthz", "/readyz"}:
                status = HTTPStatus.OK if snapshot["status"] != "degraded" else HTTPStatus.SERVICE_UNAVAILABLE
            elif path in {"/livez", "/metrics/health"}:
                status = HTTPStatus.OK
            else:
                status = HTTPStatus.NOT_FOUND
                snapshot = {"error": "unknown endpoint", "paths": ["/healthz", "/readyz", "/livez"]}

            body = json.dumps(snapshot, default=float).encode("utf-8")
            headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
            start_response(f"{status.value} {status.phrase}", headers, None)
            return [body]

        return app


__all__ = ["CrawlerHealth"]
