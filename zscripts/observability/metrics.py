"""Lightweight metrics registry with Prometheus exposition support."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from threading import RLock

LabelTuple = tuple[tuple[str, str], ...]


def _normalize_labels(labels: Mapping[str, str] | None) -> LabelTuple:
    if not labels:
        return ()
    normalized = tuple(sorted((str(key), str(value)) for key, value in labels.items()))
    return normalized


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', "\\\"")


def _format_labels(label_items: Sequence[tuple[str, str]]) -> str:
    if not label_items:
        return ""
    encoded = ",".join(
        f"{key}=\"{_escape_label(value)}\"" for key, value in label_items
    )
    return f"{{{encoded}}}"


@dataclass
class CounterMetric:
    """Thread-safe counter metric."""

    name: str
    description: str
    _values: MutableMapping[LabelTuple, float] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def inc(self, *, amount: float = 1.0, labels: Mapping[str, str] | None = None) -> None:
        if amount < 0:
            raise ValueError("Counter increments must be non-negative.")
        key = _normalize_labels(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def samples(self) -> Iterable[tuple[LabelTuple, float]]:
        with self._lock:
            return tuple(self._values.items())


@dataclass
class _HistogramSeries:
    counts: list[int]
    cumulative: list[int]
    total_count: int = 0
    total_sum: float = 0.0


@dataclass
class HistogramMetric:
    """Fixed-bucket histogram compatible with Prometheus text exposition."""

    name: str
    description: str
    buckets: tuple[float, ...]
    _values: MutableMapping[LabelTuple, _HistogramSeries] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def observe(self, value: float, *, labels: Mapping[str, str] | None = None) -> None:
        key = _normalize_labels(labels)
        with self._lock:
            series = self._values.get(key)
            if series is None:
                series = _HistogramSeries(
                    counts=[0 for _ in range(len(self.buckets))],
                    cumulative=[0 for _ in range(len(self.buckets))],
                )
                self._values[key] = series
            for index, upper in enumerate(self.buckets):
                if value <= upper:
                    series.counts[index] += 1
            series.total_count += 1
            series.total_sum += value
            running = 0
            for index, count in enumerate(series.counts):
                running += count
                series.cumulative[index] = running

    def samples(self) -> Iterable[tuple[LabelTuple, _HistogramSeries]]:
        with self._lock:
            return tuple((key, series) for key, series in self._values.items())


_DEFAULT_BUCKETS: tuple[float, ...] = (
    0.01,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)


class MetricsRegistry:
    """Central registry for counters and histograms."""

    def __init__(self) -> None:
        self._counters: MutableMapping[str, CounterMetric] = {}
        self._histograms: MutableMapping[str, HistogramMetric] = {}
        self._lock = RLock()

    def counter(self, name: str, description: str) -> CounterMetric:
        with self._lock:
            metric = self._counters.get(name)
            if metric is None:
                metric = CounterMetric(name=name, description=description)
                self._counters[name] = metric
            return metric

    def histogram(
        self, name: str, description: str, *, buckets: Sequence[float] | None = None
    ) -> HistogramMetric:
        bucket_key = tuple(sorted(buckets)) if buckets else _DEFAULT_BUCKETS
        with self._lock:
            metric = self._histograms.get(name)
            if metric is None:
                metric = HistogramMetric(
                    name=name,
                    description=description,
                    buckets=tuple(bucket_key),
                )
                self._histograms[name] = metric
            return metric

    def collect_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            counters = list(self._counters.values())
            histograms = list(self._histograms.values())
        for metric in counters:
            lines.append(f"# HELP {metric.name} {metric.description}")
            lines.append(f"# TYPE {metric.name} counter")
            for labels, value in metric.samples():
                lines.append(f"{metric.name}{_format_labels(labels)} {value}")
        for metric in histograms:
            lines.append(f"# HELP {metric.name} {metric.description}")
            lines.append(f"# TYPE {metric.name} histogram")
            for labels, series in metric.samples():
                for index, upper in enumerate(metric.buckets):
                    bucket_labels = tuple(sorted((*labels, ("le", str(upper)))))
                    lines.append(
                        f"{metric.name}_bucket{_format_labels(bucket_labels)} "
                        f"{series.cumulative[index]}"
                    )
                inf_labels = tuple(sorted((*labels, ("le", "+Inf"))))
                lines.append(
                    f"{metric.name}_bucket{_format_labels(inf_labels)} {series.total_count}"
                )
                lines.append(
                    f"{metric.name}_sum{_format_labels(labels)} {series.total_sum}"
                )
                lines.append(
                    f"{metric.name}_count{_format_labels(labels)} {series.total_count}"
                )
        return "\n".join(lines) + ("\n" if lines else "")


default_registry = MetricsRegistry()
"""Singleton metrics registry shared by default."""


__all__ = ["MetricsRegistry", "CounterMetric", "HistogramMetric", "default_registry"]
