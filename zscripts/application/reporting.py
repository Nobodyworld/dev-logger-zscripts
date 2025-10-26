"""Reporting utilities combining normalized logs with presentation metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone

from zscripts.schemas import NormalizedLog


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
        }
        return payload


__all__ = ["ReportBundle"]
