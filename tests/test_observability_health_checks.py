from __future__ import annotations

from zscripts.observability.health_checks import HealthCheckRegistry


def test_health_check_registry_snapshot_counts_statuses() -> None:
    registry = HealthCheckRegistry()

    registry.register("ok_check", lambda: {"status": "ok", "detail": "healthy"}, kind="service")
    registry.register("warn_check", lambda: {"status": "warning"}, kind="dependency")
    registry.register("fail_check", lambda: {"status": "fail"}, kind="dependency")

    snapshot = registry.snapshot()
    assert snapshot["status"] == "error"
    summary = snapshot["summary"]
    assert summary == {"total": 3, "ok": 1, "degraded": 1, "error": 1}
    checks = snapshot["checks"]
    assert checks["ok_check"]["status"] == "ok"
    assert checks["warn_check"]["status"] == "degraded"
    assert checks["fail_check"]["status"] == "error"
    assert checks["ok_check"]["kind"] == "service"


def test_health_check_registry_unregister_and_describe() -> None:
    registry = HealthCheckRegistry()
    registry.register("transient", lambda: {"status": "ok"})
    registry.unregister("transient")
    snapshot = registry.snapshot()
    assert snapshot["summary"] == {"total": 0, "ok": 0, "degraded": 0, "error": 0}
    description = registry.describe()
    assert description == {"total": 0, "names": []}
