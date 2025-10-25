"""Lightweight tracing spans layered atop the metrics registry."""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from zscripts.observability import logging as obs_logging
from zscripts.observability.metrics import MetricsRegistry, default_registry

_TRACE_ID: ContextVar[str | None] = ContextVar("zscripts_trace_id", default=None)
_SPAN_STACK: ContextVar[tuple[str, ...]] = ContextVar("zscripts_span_stack", default=())


@dataclass(slots=True)
class Span:
    """Runtime information about an active tracing span."""

    trace_id: str
    span_id: str
    parent_id: str | None
    operation: str
    start_time: float
    attributes: Mapping[str, str]
    end_time: float | None = None
    status: str | None = None


@contextmanager
def start_span(
    operation: str,
    *,
    attributes: Mapping[str, str] | None = None,
    metrics: MetricsRegistry | None = None,
) -> Iterator[Span]:
    """Context manager recording span metrics and structured logs."""

    registry = metrics or default_registry
    trace_id = _TRACE_ID.get()
    token_trace = None
    if trace_id is None:
        trace_id = uuid.uuid4().hex
        token_trace = _TRACE_ID.set(trace_id)
    parent_stack = _SPAN_STACK.get()
    parent_id = parent_stack[-1] if parent_stack else None
    span_id = uuid.uuid4().hex
    token_stack = _SPAN_STACK.set(parent_stack + (span_id,))
    attrs = dict(attributes or {})
    start = time.perf_counter()
    logger = obs_logging.get_logger("trace")
    with obs_logging.bind_correlation_id(trace_id):
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_id=parent_id,
            operation=operation,
            start_time=start,
            attributes=attrs,
        )
        logger.info(
            "span.start",
            extra={"operation": operation, "span_id": span_id, "parent_id": parent_id, **attrs},
        )
        status = "success"
        try:
            yield span
        except Exception:
            status = "error"
            logger.exception(
                "span.error",
                extra={
                    "operation": operation,
                    "span_id": span_id,
                    "parent_id": parent_id,
                    **attrs,
                },
            )
            raise
        finally:
            end_time = time.perf_counter()
            duration = end_time - start
            span.end_time = end_time
            span.status = status
            registry.counter(
                "zscripts_requests_total",
                "Total toolkit service requests processed.",
            ).inc(labels={"operation": operation, "status": status})
            registry.histogram(
                "zscripts_request_duration_seconds",
                "Toolkit service request duration in seconds.",
            ).observe(duration, labels={"operation": operation, "status": status})
            logger.info(
                "span.end",
                extra={
                    "operation": operation,
                    "span_id": span_id,
                    "parent_id": parent_id,
                    "duration_seconds": duration,
                    "status": status,
                    **attrs,
                },
            )
            _SPAN_STACK.reset(token_stack)
            if token_trace is not None:
                _TRACE_ID.reset(token_trace)


__all__ = ["Span", "start_span"]
