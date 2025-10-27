"""Unified instrumentation helpers for logs, metrics, and traces."""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager, nullcontext
from dataclasses import dataclass
from typing import TYPE_CHECKING

from zscripts.observability.logging import bind_correlation_id, get_logger
from zscripts.observability.metrics import (
    CounterMetric,
    GaugeMetric,
    HistogramMetric,
    MetricsRegistry,
    default_registry,
)

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from zscripts.observability.telemetry import TelemetryManager


@dataclass(slots=True)
class OperationResult:
    """Represents the outcome of an instrumented operation."""

    status: str
    duration_seconds: float


class InstrumentationManager:
    """Coordinate metrics, logging, and tracing for a subsystem."""

    def __init__(
        self,
        *,
        telemetry: TelemetryManager | None = None,
        metrics: MetricsRegistry | None = None,
        component: str = "core",
    ) -> None:
        self._telemetry = telemetry
        self._metrics = metrics or (telemetry.metrics if telemetry is not None else default_registry)
        self._component = component
        self._logger = get_logger(f"instrumentation.{component}")
        self._inflight_gauge = self._metrics.gauge(
            "zscripts_operations_inflight",
            "Number of in-flight toolkit operations by component.",
        )
        self._result_counter = self._metrics.counter(
            "zscripts_operations_total",
            "Total toolkit operations processed.",
        )
        self._duration_histogram = self._metrics.histogram(
            "zscripts_operation_duration_seconds",
            "Toolkit operation duration in seconds.",
        )

    @contextmanager
    def operation(
        self,
        operation: str,
        *,
        attributes: Mapping[str, str] | None = None,
        correlation_id: str | None = None,
    ) -> Iterator[OperationResult]:
        """Instrument a unit of work with logs, metrics, and traces."""

        labels = {"component": self._component, "operation": operation}
        merged_attrs = dict(attributes or {})
        result = OperationResult(status="success", duration_seconds=0.0)
        start_time = time.perf_counter()
        inflight_labels = {"component": self._component}
        self._inflight_gauge.inc(labels=inflight_labels)
        self._logger.info(
            "operation.start",
            extra={"operation": operation, "component": self._component, **merged_attrs},
        )
        span_cm = (
            self._telemetry.span(
                f"{self._component}.{operation}",
                attributes={"component": self._component, **merged_attrs},
            )
            if self._telemetry is not None
            else nullcontext()
        )
        binder = bind_correlation_id(correlation_id) if correlation_id else nullcontext()
        try:
            with binder:
                with span_cm:
                    yield result
        except BaseException as exc:
            if result.status == "success" and not isinstance(exc, SystemExit):
                result.status = "error"
            log_extra = {"operation": operation, "component": self._component, **merged_attrs}
            if isinstance(exc, SystemExit) and result.status != "error":
                self._logger.info("operation.exit", extra=log_extra)
            else:
                self._logger.exception("operation.error", extra=log_extra)
            raise
        else:
            self._logger.info(
                "operation.success",
                extra={
                    "operation": operation,
                    "component": self._component,
                    **merged_attrs,
                },
            )
        finally:
            duration = time.perf_counter() - start_time
            result.duration_seconds = duration
            final_status = result.status
            self._result_counter.inc(labels={**labels, "status": final_status})
            self._duration_histogram.observe(
                duration,
                labels={**labels, "status": final_status},
            )
            self._inflight_gauge.dec(labels=inflight_labels)
            self._logger.info(
                "operation.end",
                extra={
                    "operation": operation,
                    "component": self._component,
                    "status": final_status,
                    "duration_seconds": duration,
                    **merged_attrs,
                },
            )

    def counter(self, name: str, description: str) -> CounterMetric:
        """Expose the underlying counter factory."""

        return self._metrics.counter(name, description)

    def histogram(self, name: str, description: str) -> HistogramMetric:
        """Expose the underlying histogram factory."""

        return self._metrics.histogram(name, description)

    def gauge(self, name: str, description: str) -> GaugeMetric:
        """Expose the underlying gauge factory."""

        return self._metrics.gauge(name, description)

    def bind_correlation(self, correlation_id: str) -> AbstractContextManager[None]:
        """Helper to bind a correlation ID within a context manager."""

        return bind_correlation_id(correlation_id)

    @property
    def component(self) -> str:
        return self._component


__all__ = ["InstrumentationManager", "OperationResult"]
