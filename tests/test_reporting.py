from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from zscripts.application.report_formatters import (
    format_report_json,
    format_report_markdown,
    get_report_formatter,
)
from zscripts.application.reporting import ReportBundle, evaluate_report_severity
from zscripts.schemas import LogIssue, NormalizedLog, TestCaseResult, TestSummary


def _make_bundle() -> ReportBundle:
    timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
    normalized = NormalizedLog(
        tool="pytest",
        ecosystem="python",
        command="pytest -q",
        status="passed",
        summary="Suite completed",
        timestamp=timestamp,
        errors=[LogIssue(message="boom", file="tests/test_example.py", line=12, code="E001")],
        warnings=[LogIssue(message="flaky", file="tests/test_example.py", line=15)],
        tests=TestSummary(
            passed=10,
            failed=1,
            skipped=0,
            duration=12.345,
            cases=[
                TestCaseResult(name="test_ok", status="passed", duration=0.5),
                TestCaseResult(name="test_fail", status="failed", duration=1.2, message="assert 1 == 2"),
            ],
        ),
        artifacts=["coverage.xml"],
        metadata={"branch": "main"},
    )
    return ReportBundle(
        normalized=normalized,
        summary="Aggregated summary",
        explanation="Detailed explanation",
        guardrails={"timeout_seconds": 60, "allowed_paths": ["examples"]},
        collected_text="raw log contents",
        redacted_text=None,
        generated_at=timestamp,
        severity="error",
    )


@pytest.mark.parametrize(
    (
        "status",
        "has_errors",
        "failed_tests",
        "has_warnings",
        "expected",
    ),
    [
        ("failed", False, 0, False, "error"),
        ("passed", True, 0, False, "error"),
        ("passed", False, 2, False, "error"),
        ("passed", False, 0, True, "warning"),
        ("warning", False, 0, False, "warning"),
        ("passed", False, None, False, "ok"),
        ("passed", False, 0, False, "ok"),
    ],
)
def test_evaluate_report_severity(
    status: str,
    has_errors: bool,
    failed_tests: int | None,
    has_warnings: bool,
    expected: str,
) -> None:
    timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
    errors = [LogIssue(message="err")] if has_errors else []
    warnings = [LogIssue(message="warn")] if has_warnings else []
    tests = TestSummary(passed=0, failed=failed_tests, skipped=0) if failed_tests is not None else None

    normalized = NormalizedLog(
        tool="pytest",
        ecosystem="python",
        command="pytest -q",
        status=status,
        summary="",
        timestamp=timestamp,
        errors=errors,
        warnings=warnings,
        tests=tests,
    )

    assert evaluate_report_severity(normalized) == expected


def test_format_report_json_round_trips() -> None:
    bundle = _make_bundle()

    payload = format_report_json(bundle)
    data = json.loads(payload)

    assert data["summary"] == "Aggregated summary"
    assert data["normalized"]["tool"] == "pytest"
    assert data["guardrails"]["timeout_seconds"] == 60
    assert data["severity"] == "error"
    assert data["generated_at"].endswith("+00:00")


def test_format_report_markdown_contains_sections() -> None:
    bundle = _make_bundle()

    document = format_report_markdown(bundle)

    assert "# pytest Report" in document
    assert "## Guardrails" in document
    assert "### Errors" in document
    assert "- **Status:** passed" in document
    assert "- **Severity:** error" in document
    assert "- timeout_seconds: 60" in document
    assert "### Cases" in document
    assert "assert 1 == 2" in document


def test_get_report_formatter_dispatches() -> None:
    bundle = _make_bundle()

    formatter = get_report_formatter("markdown")
    assert formatter(bundle).startswith("# pytest Report")

    with pytest.raises(ValueError):
        get_report_formatter("xml")


def test_format_report_markdown_handles_empty_sections() -> None:
    timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
    normalized = NormalizedLog(
        tool="pytest",
        ecosystem="python",
        command="pytest -q",
        status="passed",
        summary="Suite completed",
        timestamp=timestamp,
    )
    bundle = ReportBundle(
        normalized=normalized,
        summary="",
        explanation="",
        guardrails={},
        collected_text="",
        redacted_text=None,
        generated_at=timestamp,
        severity="ok",
    )

    document = format_report_markdown(bundle)

    assert "No issues were reported" in document
    assert "No test results were provided." in document
    assert "No artifacts recorded." in document
    assert "No additional metadata captured." in document
