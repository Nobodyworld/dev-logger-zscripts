"""Telemetry utilities for the web crawler.

The crawler does not require any particular monitoring stack but exposing a
small interface makes it easy to integrate with Prometheus, OpenTelemetry, or
custom logging sinks. The telemetry layer focuses on producing structured
events that mirror the crawler lifecycle while remaining dependency optional.
"""

from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING, Any, Iterable, Iterator, Protocol

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


class CrawlerTelemetry(Protocol):
    """Protocol describing telemetry hooks consumed by the crawler."""

    def record_queue_depth(self, depth: int) -> None:
        """Record the length of the pending queue."""

    def record_fetch(self, url: str, outcome: str, elapsed: float) -> None:
        """Record the outcome of an HTTP fetch."""

    def record_page_crawled(self, url: str, text_bytes: int) -> None:
        """Record the size of the harvested text for a page."""

    def record_error(self, url: str, error: Exception) -> None:
        """Record a terminal error for a URL."""


class NullCrawlerTelemetry:
    """No-op telemetry implementation used when instrumentation is disabled."""

    def record_queue_depth(self, depth: int) -> None:
        """Ignore queue depth updates."""
        del depth

    def record_fetch(self, url: str, outcome: str, elapsed: float) -> None:
        """Ignore fetch recordings."""
        del url, outcome, elapsed

    def record_page_crawled(self, url: str, text_bytes: int) -> None:
        """Ignore page size recordings."""
        del url, text_bytes

    def record_error(self, url: str, error: Exception) -> None:
        """Ignore error recordings."""
        del url, error


class CompositeCrawlerTelemetry:
    """Dispatch telemetry events to multiple collectors."""

    def __init__(self, telemetry: Iterable[CrawlerTelemetry]) -> None:
        """Store the sequence of collectors that should receive events."""
        self._telemetry = list(telemetry)

    def record_queue_depth(self, depth: int) -> None:
        """Broadcast queue depth updates to all collectors."""
        for collector in self._telemetry:
            collector.record_queue_depth(depth)

    def record_fetch(self, url: str, outcome: str, elapsed: float) -> None:
        """Broadcast fetch events to all collectors."""
        for collector in self._telemetry:
            collector.record_fetch(url, outcome, elapsed)

    def record_page_crawled(self, url: str, text_bytes: int) -> None:
        """Broadcast page size events to all collectors."""
        for collector in self._telemetry:
            collector.record_page_crawled(url, text_bytes)

    def record_error(self, url: str, error: Exception) -> None:
        """Broadcast errors to all collectors."""
        for collector in self._telemetry:
            collector.record_error(url, error)


@dataclass(slots=True)
class FetchTimer:
    """Context manager for measuring fetch duration."""

    telemetry: CrawlerTelemetry
    url: str
    _start: float = 0.0

    def __enter__(self) -> "FetchTimer":
        """Record the time at which the fetch started."""
        self._start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        """Compute elapsed time and forward the telemetry event."""
        elapsed = time.perf_counter() - self._start
        outcome = "error" if exc_type else "success"
        self.telemetry.record_fetch(self.url, outcome, elapsed)
        if isinstance(exc, Exception):
            self.telemetry.record_error(self.url, exc)


class PrometheusCrawlerTelemetry:
    """Prometheus collector exporting crawler metrics."""

    def __init__(
        self,
        *,
        namespace: str = "dev_script",
        subsystem: str = "crawler",
        registry: "CollectorRegistry" | None = None,
    ) -> None:
        """Initialise metrics and optional registry for Prometheus exports."""
        try:
            from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "prometheus_client is required to use PrometheusCrawlerTelemetry"
            ) from exc

        if registry is None:
            registry = CollectorRegistry()
        self.registry = registry
        self.fetch_total: "Counter" = Counter(
            "fetch_total",
            "Total fetch attempts",
            ("outcome",),
            namespace=namespace,
            subsystem=subsystem,
            registry=registry,
        )
        self.fetch_latency: "Histogram" = Histogram(
            "fetch_seconds",
            "Histogram of fetch durations",
            namespace=namespace,
            subsystem=subsystem,
            registry=registry,
            buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
        )
        self.queue_depth: "Gauge" = Gauge(
            "queue_depth",
            "Number of URLs pending crawl",
            namespace=namespace,
            subsystem=subsystem,
            registry=registry,
        )
        self.page_size: "Histogram" = Histogram(
            "page_text_bytes",
            "Size of harvested page text",
            namespace=namespace,
            subsystem=subsystem,
            registry=registry,
            buckets=(128, 256, 512, 1024, 2048, 4096, 8192),
        )
        self.error_total: "Counter" = Counter(
            "errors_total",
            "Number of terminal crawl errors",
            namespace=namespace,
            subsystem=subsystem,
            registry=registry,
        )

    def record_queue_depth(self, depth: int) -> None:
        """Update the queue depth gauge."""
        self.queue_depth.set(depth)

    def record_fetch(self, url: str, outcome: str, elapsed: float) -> None:
        """Observe fetch latency and increment counters."""
        del url
        self.fetch_total.labels(outcome=outcome).inc()
        self.fetch_latency.observe(elapsed)

    def record_page_crawled(self, url: str, text_bytes: int) -> None:
        """Observe harvested page size."""
        del url
        self.page_size.observe(float(text_bytes))

    def record_error(self, url: str, error: Exception) -> None:
        """Increment the error counter."""
        del url, error
        self.error_total.inc()


class OpenTelemetryCrawlerTelemetry:
    """Forward metrics to OpenTelemetry spans if available."""

    def __init__(self, tracer: Any | None = None, base: CrawlerTelemetry | None = None) -> None:
        """Configure the OpenTelemetry tracer used to emit spans."""
        try:
            from opentelemetry import trace
            from opentelemetry.trace import SpanKind
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("opentelemetry-sdk is required for tracing support") from exc

        self._trace = trace
        self._span_kind = SpanKind
        self._tracer = tracer or trace.get_tracer(__name__)
        self._base = base or NullCrawlerTelemetry()

    @contextlib.contextmanager
    def _span(self, name: str, **attributes: Any) -> Iterator[None]:
        with self._tracer.start_as_current_span(
            name, kind=self._span_kind.INTERNAL, attributes=attributes
        ):
            yield

    def record_queue_depth(self, depth: int) -> None:
        """Wrap queue depth updates in an OpenTelemetry span."""
        with self._span("crawler.queue", depth=depth):
            self._base.record_queue_depth(depth)

    def record_fetch(self, url: str, outcome: str, elapsed: float) -> None:
        """Emit a span for each fetch and forward to the base collector."""
        with self._span("crawler.fetch", url=url, outcome=outcome, elapsed=elapsed):
            self._base.record_fetch(url, outcome, elapsed)

    def record_page_crawled(self, url: str, text_bytes: int) -> None:
        """Emit a span capturing the harvested page size."""
        with self._span("crawler.page", url=url, size=text_bytes):
            self._base.record_page_crawled(url, text_bytes)

    def record_error(self, url: str, error: Exception) -> None:
        """Record crawl errors while preserving the base collector behaviour."""
        with self._span("crawler.error", url=url, error=str(error)):
            self._base.record_error(url, error)


def combine_telemetry(*telemetry: CrawlerTelemetry | None) -> CrawlerTelemetry:
    """Combine the provided telemetry collectors into a composite collector."""
    active = [collector for collector in telemetry if collector is not None]
    if not active:
        return NullCrawlerTelemetry()
    if len(active) == 1:
        return active[0]
    return CompositeCrawlerTelemetry(active)


__all__ = [
    "CompositeCrawlerTelemetry",
    "CrawlerTelemetry",
    "FetchTimer",
    "NullCrawlerTelemetry",
    "OpenTelemetryCrawlerTelemetry",
    "PrometheusCrawlerTelemetry",
    "combine_telemetry",
]

