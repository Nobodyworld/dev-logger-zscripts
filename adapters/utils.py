"""Utility helpers shared across log adapters."""

from __future__ import annotations

import re

from zscripts.schemas import LogIssue, TestCaseResult, TestSummary

_KEY_VALUE_PATTERN = re.compile(
    r"(?P<key>[A-Za-z0-9_]+)=(\"(?P<quoted>[^\"]+)\"|(?P<bare>[^\s]+))"
)


def parse_key_value_pairs(text: str) -> dict[str, str]:
    """Parse key-value pairs from a line of text.

    Args:
        text: Line containing ``key=value`` tokens.

    Returns:
        Dict[str, str]: Mapping of keys to their lowercase string values.
    """

    result: dict[str, str] = {}
    for match in _KEY_VALUE_PATTERN.finditer(text):
        value = match.group("quoted") or match.group("bare") or ""
        result[match.group("key").lower()] = value
    return result


def issue_from_line(line: str) -> LogIssue:
    """Create a :class:`LogIssue` from a structured log line.

    Args:
        line: Log line containing ``file``, ``line``, and ``message`` data.

    Returns:
        LogIssue: Parsed issue representation.
    """

    data = parse_key_value_pairs(line)
    return LogIssue(
        message=data.get("message", line.strip()),
        file=data.get("file"),
        line=int(data["line"]) if "line" in data else None,
        code=data.get("code"),
    )


def tests_from_line(line: str) -> TestSummary:
    """Create a :class:`TestSummary` from a structured line.

    Args:
        line: Log line with ``passed``, ``failed``, ``skipped``, and ``duration``.

    Returns:
        TestSummary: Parsed test summary information.
    """

    data = parse_key_value_pairs(line)
    return TestSummary(
        passed=int(data.get("passed", 0)),
        failed=int(data.get("failed", 0)),
        skipped=int(data.get("skipped", 0)),
        duration=float(data["duration"]) if "duration" in data else None,
    )


def testcase_from_line(line: str) -> TestCaseResult:
    """Create a :class:`TestCaseResult` from a structured line.

    Args:
        line: Log line containing case ``name`` and ``status`` tokens.

    Returns:
        TestCaseResult: Parsed case result information.
    """

    data = parse_key_value_pairs(line)
    return TestCaseResult(
        name=data.get("name", "unknown"),
        status=data.get("status", "unknown"),
        duration=float(data["duration"]) if "duration" in data else None,
        message=data.get("message"),
    )


__all__ = [
    "parse_key_value_pairs",
    "issue_from_line",
    "tests_from_line",
    "testcase_from_line",
]
