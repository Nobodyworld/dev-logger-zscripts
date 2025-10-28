"""Dataclasses describing normalized log documents."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import ClassVar, cast


@dataclass(slots=True)
class LogIssue:
    """Represents a compiler or test issue.

    Attributes:
        message: Human-readable description of the issue.
        file: Optional file path associated with the issue.
        line: Optional line number related to the issue.
        column: Optional column number related to the issue.
        code: Optional machine-readable identifier, such as an error code.
    """

    message: str
    file: str | None = None
    line: int | None = None
    column: int | None = None
    code: str | None = None


@dataclass(slots=True)
class TestCaseResult:
    """Represents an individual test case result."""

    name: str
    status: str
    duration: float | None = None
    message: str | None = None
    __test__: ClassVar[bool] = False


@dataclass(slots=True)
class TestSummary:
    """Summary of test execution results."""

    passed: int
    failed: int
    skipped: int
    duration: float | None = None
    cases: list[TestCaseResult] = field(default_factory=list)
    __test__: ClassVar[bool] = False


@dataclass(slots=True)
class NormalizedLog:
    """Normalized representation of a build, compile, or test log."""

    tool: str
    ecosystem: str
    command: str
    status: str
    summary: str
    timestamp: datetime
    errors: list[LogIssue] = field(default_factory=list)
    warnings: list[LogIssue] = field(default_factory=list)
    tests: TestSummary | None = None
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Convert the dataclass hierarchy into a JSON-serializable dictionary."""

        result = cast("dict[str, object]", asdict(self))
        result["timestamp"] = self.timestamp.isoformat()
        return result


__all__ = [
    "LogIssue",
    "TestCaseResult",
    "TestSummary",
    "NormalizedLog",
]
