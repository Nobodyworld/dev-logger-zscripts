"""Secret redaction utilities."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field


@dataclass
class Redactor:
    """Apply regular-expression based redaction to text."""

    patterns: Sequence[str] = field(default_factory=list)

    def redact(self, text: str) -> str:
        """Redact sensitive patterns from text.

        Args:
            text: Raw text containing potentially sensitive data.

        Returns:
            str: Text with matched patterns replaced by ``[REDACTED]``.
        """

        result = text
        for pattern in self.patterns:
            regex = re.compile(pattern)
            result = regex.sub(lambda match: f"{match.group(0)[:2]}[REDACTED]", result)
        return result


def redact_text(text: str, patterns: Iterable[str]) -> str:
    """Convenience wrapper around :class:`Redactor`.

    Args:
        text: Text to redact.
        patterns: Iterable of regular expression patterns.

    Returns:
        str: Redacted text.
    """

    return Redactor(tuple(patterns)).redact(text)


__all__ = ["Redactor", "redact_text"]
