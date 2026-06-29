"""Runtime diagnostics helpers for telemetry and extension state."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import cast

from zscripts.extensions.registry import ExtensionManager
from zscripts.observability.instrumentation import InstrumentationManager
from zscripts.observability.telemetry import TelemetryManager


@dataclass(slots=True)
class DiagnosticsSnapshot:
    """Structured diagnostics payload suitable for JSON encoding."""

    generated_at: str
    telemetry: Mapping[str, object]
    extensions: Mapping[str, object]
    component: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "telemetry": dict(self.telemetry),
            "extensions": dict(self.extensions),
            "component": self.component,
        }


def collect_runtime_diagnostics(
    *,
    telemetry: TelemetryManager,
    instrumentation: InstrumentationManager | None = None,
    extensions: Sequence[object] | ExtensionManager | None = None,
    include_metrics: bool = False,
) -> DiagnosticsSnapshot:
    """Collect a diagnostics snapshot combining telemetry and extension data."""

    timestamp = datetime.now(timezone.utc).isoformat()
    telemetry_payload: dict[str, object] = telemetry.snapshot(include_metrics=include_metrics)
    extension_payload = _summarize_extensions(extensions)
    component = instrumentation.component if instrumentation is not None else None
    return DiagnosticsSnapshot(
        generated_at=timestamp,
        telemetry=telemetry_payload,
        extensions=extension_payload,
        component=component,
    )


def _summarize_extensions(
    extensions: Sequence[object] | ExtensionManager | None,
) -> Mapping[str, object]:
    if extensions is None:
        return {"count": 0, "names": [], "hooks": {}}
    if isinstance(extensions, ExtensionManager):
        names = extensions.names()
        manifests: dict[str, dict[str, object]] = {
            name: manifest.to_dict() for name, manifest in extensions.manifests().items()
        }
        hooks = extensions.hook_summary()
        return {
            "count": len(names),
            "names": names,
            "hooks": hooks,
            "manifests": manifests,
        }
    resolved: list[str] = []
    for ext in extensions:
        raw_name = cast(object, getattr(ext, "name", ext.__class__.__name__))
        resolved.append(str(raw_name))
    return {"count": len(resolved), "names": resolved, "hooks": {}}


__all__ = ["DiagnosticsSnapshot", "collect_runtime_diagnostics"]
