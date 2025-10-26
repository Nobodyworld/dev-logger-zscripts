"""Reporting utilities combining normalized logs with presentation metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone

from zscripts.schemas import NormalizedLog, TestSummary

_ERROR_STATUSES: tuple[str, ...] = ("failed", "error", "failure", "fatal")
_WARNING_STATUSES: tuple[str, ...] = ("warning", "warn", "warnings")


@dataclass(slots=True)
class ReportBundle:
    """Aggregate artifact produced by the ``report`` workflow."""

    normalized: NormalizedLog
    summary: str
    explanation: str
    guardrails: Mapping[str, object]
    collected_text: str
    redacted_text: str | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    severity: str = "ok"

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable mapping describing the report bundle."""

        payload: dict[str, object] = {
            "normalized": self.normalized.to_dict(),
            "summary": self.summary,
            "explanation": self.explanation,
            "guardrails": dict(self.guardrails),
            "collected_text": self.collected_text,
            "redacted_text": self.redacted_text,
            "generated_at": self.generated_at.isoformat(),
            "severity": self.severity,
        }
        return payload


def evaluate_report_severity(normalized: NormalizedLog) -> str:
    """Infer a severity label from a normalized log document."""

    status = normalized.status.strip().lower()
    if status in _ERROR_STATUSES:
        return "error"
    if normalized.errors:
        return "error"
    tests: TestSummary | None = normalized.tests
    if tests is not None and tests.failed > 0:
        return "error"
    if normalized.warnings:
        return "warning"
    if status in _WARNING_STATUSES:
        return "warning"
    return "ok"


__all__ = ["ReportBundle", "evaluate_report_severity"]
