"""Structured log parsing helpers reused by multiple adapters."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from adapters.utils import (
    issue_from_line,
    parse_key_value_pairs,
    testcase_from_line,
    tests_from_line,
)
from zscripts.schemas import NormalizedLog, TestSummary

_META_KEYS = {"tool", "ecosystem", "command", "status", "summary", "timestamp"}


class _StructuredLogBuilder:
    """Accumulates normalized log data while parsing structured lines."""

    def __init__(self, default_tool: str, ecosystem: str, default_status: str) -> None:
        self.tool = default_tool
        self.ecosystem = ecosystem
        self.command = ""
        self.status = default_status
        self.summary = ""
        self.timestamp: datetime | None = None
        self.errors: list = []
        self.warnings: list = []
        self.tests: TestSummary | None = None
        self.artifacts: list[str] = []
        self.metadata: dict[str, str] = {}
        self._handlers: dict[str, Callable[[str], None]] = {
            "META": self._handle_meta,
            "ERROR": lambda payload: self._append_issue(payload, self.errors),
            "WARNING": lambda payload: self._append_issue(payload, self.warnings),
            "TESTS": self._handle_tests,
            "TESTCASE": self._handle_testcase,
            "ARTIFACT": self._handle_artifact,
            "INFO": self._handle_info,
        }

    def handle(self, token: str, payload: str) -> None:
        handler = self._handlers.get(token)
        if handler:
            handler(payload)

    def _handle_meta(self, payload: str) -> None:
        data = parse_key_value_pairs(payload)
        self.tool = data.get("tool", self.tool)
        self.ecosystem = data.get("ecosystem", self.ecosystem)
        self.command = data.get("command", self.command)
        self.status = data.get("status", self.status)
        self.summary = data.get("summary", self.summary)
        timestamp_text = data.get("timestamp")
        if timestamp_text:
            try:
                self.timestamp = datetime.fromisoformat(timestamp_text)
            except ValueError:
                self.metadata["timestamp_parse_error"] = timestamp_text
        metadata_updates = {k: v for k, v in data.items() if k not in _META_KEYS}
        self.metadata.update(metadata_updates)

    def _append_issue(self, payload: str, bucket: list) -> None:
        bucket.append(issue_from_line(payload))

    def _handle_tests(self, payload: str) -> None:
        self.tests = tests_from_line(payload)

    def _handle_testcase(self, payload: str) -> None:
        if self.tests is None:
            self.tests = TestSummary(passed=0, failed=0, skipped=0)
        self.tests.cases.append(testcase_from_line(payload))

    def _handle_artifact(self, payload: str) -> None:
        data = parse_key_value_pairs(payload)
        self.artifacts.append(data.get("path", payload))

    def _handle_info(self, payload: str) -> None:
        self.metadata.update(parse_key_value_pairs(payload))

    def finalize(self, default_status: str) -> NormalizedLog:
        timestamp = self.timestamp or datetime.utcnow()
        if self.tests and self.tests.cases:
            counts = {
                "passed": sum(1 for case in self.tests.cases if case.status.lower() == "passed"),
                "failed": sum(1 for case in self.tests.cases if case.status.lower() == "failed"),
                "skipped": sum(1 for case in self.tests.cases if case.status.lower() == "skipped"),
            }
            self.tests.passed = counts["passed"] or self.tests.passed
            self.tests.failed = counts["failed"] or self.tests.failed
            self.tests.skipped = counts["skipped"] or self.tests.skipped
        return NormalizedLog(
            tool=self.tool,
            ecosystem=self.ecosystem,
            command=self.command,
            status=self.status or default_status,
            summary=self.summary or "No summary provided.",
            timestamp=timestamp,
            errors=list(self.errors),
            warnings=list(self.warnings),
            tests=self.tests,
            artifacts=list(self.artifacts),
            metadata=dict(self.metadata),
        )


def parse_structured_log(
    raw: str,
    *,
    default_tool: str,
    ecosystem: str,
    default_status: str = "unknown",
) -> NormalizedLog:
    """Parse a structured log format used across adapters.

    Args:
        raw: Raw log text.
        default_tool: Tool name to assume when the log omits it.
        ecosystem: Ecosystem identifier (python, javascript, etc.).
        default_status: Status to use when the log omits a value.

    Returns:
        NormalizedLog: Parsed normalized log representation.
    """

    builder = _StructuredLogBuilder(default_tool, ecosystem, default_status)
    for line in raw.splitlines():
        normalized = line.strip()
        if not normalized or normalized.startswith("#"):
            continue
        token, _, rest = normalized.partition(" ")
        builder.handle(token.upper(), rest.strip())
    return builder.finalize(default_status)


__all__ = ["parse_structured_log"]
