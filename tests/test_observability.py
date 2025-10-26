"""Tests for observability metrics, tracing, and telemetry utilities."""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib import request

import pytest

from zscripts.observability.health import HealthTelemetryServer
from zscripts.observability.instrumentation import InstrumentationManager
from zscripts.observability.logging import bind_correlation_id, configure_logging, get_logger
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


def test_metrics_registry_gauge_support() -> None:
    registry = MetricsRegistry()
    gauge = registry.gauge("zscripts_extensions_active", "Active extensions")
    gauge.set(2, labels={"component": "loader"})
    gauge.dec(labels={"component": "loader"})
    payload = registry.collect_prometheus()
    assert "# TYPE zscripts_extensions_active gauge" in payload
    assert "zscripts_extensions_active{component=\"loader\"} 1.0" in payload


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
        health = request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2)
        payload = json.loads(health.read().decode("utf-8"))
        assert payload["status"] in {"ok", "degraded"}
        assert payload["liveness"]["status"] in {"ok", "starting", "inactive"}
        readiness = request.urlopen(f"http://127.0.0.1:{port}/healthz/ready", timeout=2)
        readiness_payload = json.loads(readiness.read().decode("utf-8"))
        assert "status" in readiness_payload
        live = request.urlopen(f"http://127.0.0.1:{port}/healthz/live", timeout=2)
        live_payload = json.loads(live.read().decode("utf-8"))
        assert "status" in live_payload
        registry.counter("test_metric", "Example").inc(labels={})
        metrics = request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=2).read()
        assert b"test_metric" in metrics
        assert b"zscripts_health_http_requests_total" in metrics
        assert b"endpoint=\"healthz\"" in metrics
        assert b"zscripts_health_http_request_duration_seconds_bucket" in metrics
    finally:
        server.stop()


def test_instrumentation_manager_tracks_success_and_failure() -> None:
    telemetry = TelemetryManager(TelemetrySettings())
    instrumentation = InstrumentationManager(telemetry=telemetry, component="tests")
    with instrumentation.operation("success") as result:
        assert result.status == "success"
    with pytest.raises(RuntimeError):
        with instrumentation.operation("failure"):
            raise RuntimeError("boom")
    metrics_text = telemetry.metrics.collect_prometheus()
    assert "zscripts_operations_total" in metrics_text
    assert "operation=\"success\"" in metrics_text
    assert "operation=\"failure\"" in metrics_text


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


def test_configure_logging_json_formatter_includes_correlation(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", "json")
    logger = get_logger("tests.logging")
    with bind_correlation_id("abc123"):
        logger.info("event", extra={"foo": "bar"})
    captured = capsys.readouterr().err.strip().splitlines()
    assert captured
    payload = json.loads(captured[-1])
    assert payload["message"] == "event"
    assert payload["correlation_id"] == "abc123"
    assert payload["extra"]["foo"] == "bar"


def test_configure_logging_rejects_unknown_level() -> None:
    with pytest.raises(ValueError):
        configure_logging("notalevel", "text")


def test_telemetry_status_payload_reports_starting_state() -> None:
    telemetry = TelemetryManager(
        TelemetrySettings(enabled=True, host="127.0.0.1", port=9464, log_level="INFO", log_format="text")
    )
    status = telemetry._status_payload()  # noqa: SLF001 - exercising private status helper
    assert status["status"] == "degraded"
    assert status["readiness"]["status"] == "starting"
    assert status["liveness"]["status"] == "starting"
