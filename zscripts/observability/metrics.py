"""In-memory metrics registry compatible with Prometheus text exposition."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from threading import RLock
from typing import Final

LabelTuple = tuple[tuple[str, str], ...]


def _normalize_labels(labels: Mapping[str, str] | None) -> LabelTuple:
    if not labels:
        return ()
    normalized = tuple(sorted((str(key), str(value)) for key, value in labels.items()))
    return normalized


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _format_labels(label_items: Sequence[tuple[str, str]]) -> str:
    if not label_items:
        return ""
    encoded = ",".join(f'{key}="{_escape_label(value)}"' for key, value in label_items)
    return f"{{{encoded}}}"


@dataclass
class CounterMetric:
    """Thread-safe counter metric."""

    name: str
    description: str
    _values: MutableMapping[LabelTuple, float] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def inc(
        self, *, amount: float = 1.0, labels: Mapping[str, str] | None = None
    ) -> None:
        if amount < 0:
            raise ValueError("Counter increments must be non-negative.")
        key = _normalize_labels(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def samples(self) -> Iterable[tuple[LabelTuple, float]]:
        with self._lock:
            return tuple(self._values.items())


@dataclass
class GaugeMetric:
    """Thread-safe gauge metric supporting set and increment operations."""

    name: str
    description: str
    _values: MutableMapping[LabelTuple, float] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def set(self, value: float, *, labels: Mapping[str, str] | None = None) -> None:
        key = _normalize_labels(labels)
        with self._lock:
            self._values[key] = float(value)

    def inc(
        self, *, amount: float = 1.0, labels: Mapping[str, str] | None = None
    ) -> None:
        key = _normalize_labels(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def dec(
        self, *, amount: float = 1.0, labels: Mapping[str, str] | None = None
    ) -> None:
        key = _normalize_labels(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) - amount

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
            series: _HistogramSeries | None = self._values.get(key)
            if series is None:
                series = _HistogramSeries(
                    counts=[0 for _ in range(len(self.buckets))],
                    cumulative=[0 for _ in range(len(self.buckets))],
                )
                self._values[key] = series
            if series is None:
                raise RuntimeError("Histogram series initialization failed")
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


_DEFAULT_BUCKETS: Final[tuple[float, ...]] = (
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
        self._gauges: MutableMapping[str, GaugeMetric] = {}
        self._lock = RLock()

    def counter(self, name: str, description: str) -> CounterMetric:
        with self._lock:
            metric: CounterMetric | None = self._counters.get(name)
            if metric is None:
                metric = CounterMetric(name=name, description=description)
                self._counters[name] = metric
            return metric

    def histogram(
        self, name: str, description: str, *, buckets: Sequence[float] | None = None
    ) -> HistogramMetric:
        bucket_key = tuple(sorted(buckets)) if buckets else _DEFAULT_BUCKETS
        with self._lock:
            metric: HistogramMetric | None = self._histograms.get(name)
            if metric is None:
                metric = HistogramMetric(
                    name=name,
                    description=description,
                    buckets=tuple(bucket_key),
                )
                self._histograms[name] = metric
            return metric

    def gauge(self, name: str, description: str) -> GaugeMetric:
        with self._lock:
            metric: GaugeMetric | None = self._gauges.get(name)
            if metric is None:
                metric = GaugeMetric(name=name, description=description)
                self._gauges[name] = metric
            return metric

    def collect_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            counters = list(self._counters.values())
            histograms = list(self._histograms.values())
            gauges = list(self._gauges.values())
        for counter_metric in counters:
            lines.append(f"# HELP {counter_metric.name} {counter_metric.description}")
            lines.append(f"# TYPE {counter_metric.name} counter")
            for labels, value in counter_metric.samples():
                lines.append(f"{counter_metric.name}{_format_labels(labels)} {value}")
        for gauge_metric in gauges:
            lines.append(f"# HELP {gauge_metric.name} {gauge_metric.description}")
            lines.append(f"# TYPE {gauge_metric.name} gauge")
            for labels, value in gauge_metric.samples():
                lines.append(f"{gauge_metric.name}{_format_labels(labels)} {value}")
        for histogram_metric in histograms:
            lines.append(
                f"# HELP {histogram_metric.name} {histogram_metric.description}"
            )
            lines.append(f"# TYPE {histogram_metric.name} histogram")
            for labels, series in histogram_metric.samples():
                for index, upper in enumerate(histogram_metric.buckets):
                    bucket_labels = tuple(sorted((*labels, ("le", str(upper)))))
                    lines.append(
                        f"{histogram_metric.name}_bucket{_format_labels(bucket_labels)} "
                        f"{series.cumulative[index]}"
                    )
                inf_labels = tuple(sorted((*labels, ("le", "+Inf"))))
                lines.append(
                    f"{histogram_metric.name}_bucket{_format_labels(inf_labels)} {series.total_count}"
                )
                lines.append(
                    f"{histogram_metric.name}_sum{_format_labels(labels)} {series.total_sum}"
                )
                lines.append(
                    f"{histogram_metric.name}_count{_format_labels(labels)} {series.total_count}"
                )
        return "\n".join(lines) + ("\n" if lines else "")


default_registry = MetricsRegistry()
"""Singleton metrics registry shared by default."""


__all__ = [
    "MetricsRegistry",
    "CounterMetric",
    "GaugeMetric",
    "HistogramMetric",
    "default_registry",
]
