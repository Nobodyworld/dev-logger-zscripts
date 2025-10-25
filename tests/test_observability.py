"""Tests for observability metrics, tracing, and telemetry utilities."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import pytest

from zscripts.observability.health import HealthTelemetryServer
from zscripts.observability.metrics import MetricsRegistry
from zscripts.observability.telemetry import TelemetryManager, TelemetrySettings
from zscripts.observability.tracing import start_span


def test_metrics_registry_prometheus_format() -> None:
    registry = MetricsRegistry()
    registry.counter("zscripts_requests_total", "Total requests").inc(
        labels={"operation": "parse", "status": "success"}
    )
    registry.histogram("zscripts_request_duration_seconds", "Durations").observe(
        0.25, labels={"operation": "parse", "status": "success"}
    )
    payload = registry.collect_prometheus()
    assert "zscripts_requests_total{operation=\"parse\",status=\"success\"} 1.0" in payload
    assert "zscripts_request_duration_seconds_bucket" in payload


def test_start_span_records_success_and_error_metrics() -> None:
    registry = MetricsRegistry()
    with start_span("demo", metrics=registry):
        pass
    with pytest.raises(ValueError):
        with start_span("demo", metrics=registry):
            raise ValueError("boom")
    payload = registry.collect_prometheus()
    assert "status=\"success\"" in payload
    assert "status=\"error\"" in payload


def test_health_server_serves_health_and_metrics() -> None:
    registry = MetricsRegistry()
    server = HealthTelemetryServer(metrics=registry)
    server.start(host="127.0.0.1", port=0)
    try:
        time.sleep(0.1)
        port = server.port
        health = urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2).read()
        payload = json.loads(health.decode("utf-8"))
        assert payload["status"] == "ok"
        registry.counter("test_metric", "Example").inc(labels={})
        metrics = urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=2).read()
        assert b"test_metric" in metrics
    finally:
        server.stop()


def test_telemetry_manager_starts_health_server() -> None:
    telemetry = TelemetryManager(
        TelemetrySettings(enabled=True, host="127.0.0.1", port=0, log_level="INFO", log_format="text")
    )
    telemetry.start()
    try:
        assert telemetry.health_server.is_running()
        with telemetry.span("demo", attributes={"adapter": "python"}):
            Path.cwd()
    finally:
        telemetry.stop()
