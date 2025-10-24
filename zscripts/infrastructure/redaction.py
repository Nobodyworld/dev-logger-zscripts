"""Infrastructure redaction helpers that satisfy domain contracts."""

from __future__ import annotations

from collections.abc import Sequence

from scripts.redaction import Redactor

from zscripts.domain.interfaces import RedactorProtocol


class RegexRedactor(RedactorProtocol):
    """Wrap the in-repo :class:`Redactor` as a domain protocol implementation."""

    def __init__(self, patterns: Sequence[str]) -> None:
        self._delegate = Redactor(tuple(patterns))

    def redact(self, text: str) -> str:
        return self._delegate.redact(text)


__all__ = ["RegexRedactor"]
