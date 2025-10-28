"""Composable health check registry powering telemetry endpoints."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import RLock
from typing import Any, TypedDict

HealthCheckProvider = Callable[[], Mapping[str, object]]


class HealthSnapshot(TypedDict):
    """Normalized snapshot produced by :class:`HealthCheckRegistry`."""

    status: str
    summary: dict[str, int]
    checks: dict[str, dict[str, object]]

_OK_STATUSES = {"ok", "pass", "ready", "live", "available"}
_DEGRADED_STATUSES = {"warn", "warning", "degraded", "maintenance"}


def _classify_status(value: object) -> str:
    text = str(value).strip().lower()
    if text in _OK_STATUSES:
        return "ok"
    if text in _DEGRADED_STATUSES:
        return "degraded"
    return "error"


@dataclass(slots=True)
class HealthCheck:
    """Represents a single health check contribution."""

    name: str
    provider: HealthCheckProvider
    kind: str = "generic"
    description: str | None = None

    def evaluate(self) -> dict[str, object]:
        """Execute the provider and normalise the payload."""

        start = time.perf_counter()
        payload = dict(self.provider())
        status = _classify_status(payload.get("status", "unknown"))
        payload["status"] = status
        payload.setdefault("kind", self.kind)
        if self.description:
            payload.setdefault("description", self.description)
        payload["duration_seconds"] = time.perf_counter() - start
        return payload


class HealthCheckRegistry:
    """Thread-safe registry aggregating health check providers."""

    def __init__(self) -> None:
        self._checks: dict[str, HealthCheck] = {}
        self._lock = RLock()

    def register(
        self,
        name: str,
        provider: HealthCheckProvider,
        *,
        kind: str = "generic",
        description: str | None = None,
    ) -> None:
        """Register or replace a health check provider."""

        check = HealthCheck(name=name, provider=provider, kind=kind, description=description)
        with self._lock:
            self._checks[name] = check

    def unregister(self, name: str) -> None:
        """Remove a health check if registered."""

        with self._lock:
            self._checks.pop(name, None)

    def snapshot(self) -> HealthSnapshot:
        """Execute all checks and return a normalised snapshot."""

        with self._lock:
            checks = list(self._checks.items())
        summary: dict[str, int] = {"total": len(checks), "ok": 0, "degraded": 0, "error": 0}
        results: dict[str, dict[str, object]] = {}
        worst = "ok"
        order = {"ok": 0, "degraded": 1, "error": 2}
        for name, check in checks:
            payload = check.evaluate()
            status = _classify_status(payload.get("status", "unknown"))
            payload["status"] = status
            summary[status] += 1
            if order[status] > order[worst]:
                worst = status
            results[name] = {
                **payload,
                "kind": payload.get("kind", check.kind),
            }
        return {
            "status": worst,
            "summary": summary,
            "checks": results,
        }

    def __len__(self) -> int:
        with self._lock:
            return len(self._checks)

    def describe(self) -> dict[str, Any]:
        """Return metadata about registered checks without executing them."""

        with self._lock:
            names = sorted(self._checks)
            return {
                "total": len(names),
                "names": names,
            }


__all__ = ["HealthCheck", "HealthCheckRegistry", "HealthCheckProvider", "HealthSnapshot"]
