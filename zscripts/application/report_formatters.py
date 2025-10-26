"""Report formatters used by the ``report`` CLI command."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, cast

from zscripts.application.reporting import ReportBundle
from zscripts.schemas import LogIssue, TestCaseResult, TestSummary


class ReportFormatter(Protocol):
    """Callable protocol that converts a :class:`ReportBundle` into text."""

    def __call__(self, bundle: ReportBundle) -> str:  # pragma: no cover - protocol definition
        ...


def _format_list(values: Sequence[str]) -> str:
    return "\n".join(f"  - {value}" for value in values)


def _format_issue(issue: LogIssue) -> str:
    location = ""
    if issue.file:
        location = issue.file
        if issue.line is not None:
            location += f":{issue.line}"
        if issue.column is not None:
            location += f":{issue.column}"
        location = f" ({location})"
    code = f" [{issue.code}]" if issue.code else ""
    return f"- {issue.message}{code}{location}"


def _format_cases(cases: Sequence[TestCaseResult]) -> str:
    if not cases:
        return "No individual test cases were reported."
    lines = []
    for case in cases:
        details = f"{case.name} — {case.status}"
        if case.duration is not None:
            details += f" ({case.duration:.2f}s)"
        if case.message:
            details += f": {case.message}"
        lines.append(f"- {details}")
    return "\n".join(lines)


def _format_guardrails(guardrails: Mapping[str, object]) -> str:
    if not guardrails:
        return "No guardrail configuration available."
    lines: list[str] = []
    for key in sorted(guardrails):
        value = guardrails[key]
        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            sequence = cast(Sequence[object], value)
            pretty = ", ".join(str(item) for item in sequence)
            lines.append(f"- {key}: {pretty}")
        else:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def format_report_json(bundle: ReportBundle) -> str:
    """Render a report bundle as indented JSON."""

    return json.dumps(bundle.to_dict(), indent=2, sort_keys=True)


def format_report_markdown(bundle: ReportBundle) -> str:
    """Render a report bundle as a Markdown document."""

    normalized = bundle.normalized
    header = [
        f"# {normalized.tool} Report",
        "",
        f"- **Ecosystem:** {normalized.ecosystem}",
        f"- **Command:** `{normalized.command}`",
        f"- **Status:** {normalized.status}",
        f"- **Generated:** {bundle.generated_at.isoformat()}",
    ]

    summary_section = [
        "## Summary",
        bundle.summary or normalized.summary,
    ]

    explanation_section = [
        "## Explanation",
        bundle.explanation or "No explanation available.",
    ]

    issues_section: list[str] = ["## Issues"]
    if normalized.errors:
        issues_section.append("### Errors")
        issues_section.append("\n".join(_format_issue(issue) for issue in normalized.errors))
    if normalized.warnings:
        issues_section.append("### Warnings")
        issues_section.append("\n".join(_format_issue(issue) for issue in normalized.warnings))
    if len(issues_section) == 1:
        issues_section.append("No issues were reported by this adapter.")

    tests_section: list[str] = ["## Tests"]
    summary: TestSummary | None = normalized.tests
    if summary is None:
        tests_section.append("No test results were provided.")
    else:
        overview = [
            f"- Passed: {summary.passed}",
            f"- Failed: {summary.failed}",
            f"- Skipped: {summary.skipped}",
        ]
        if summary.duration is not None:
            overview.append(f"- Duration: {summary.duration:.2f}s")
        tests_section.extend(["### Summary", "\n".join(overview), "### Cases", _format_cases(summary.cases)])

    guardrails_section = ["## Guardrails", _format_guardrails(bundle.guardrails)]

    artifacts_section = ["## Artifacts"]
    if normalized.artifacts:
        artifacts_section.append(_format_list(normalized.artifacts))
    else:
        artifacts_section.append("No artifacts recorded.")

    metadata_section = ["## Metadata"]
    if normalized.metadata:
        meta_lines = [f"- {key}: {value}" for key, value in sorted(normalized.metadata.items())]
        metadata_section.append("\n".join(meta_lines))
    else:
        metadata_section.append("No additional metadata captured.")

    document_parts = [
        "\n".join(header),
        "\n\n".join(summary_section),
        "\n\n".join(explanation_section),
        "\n\n".join(issues_section),
        "\n\n".join(tests_section),
        "\n\n".join(guardrails_section),
        "\n\n".join(artifacts_section),
        "\n\n".join(metadata_section),
    ]
    return "\n\n".join(document_parts)


_FORMATTERS: dict[str, Callable[[ReportBundle], str]] = {
    "json": format_report_json,
    "markdown": format_report_markdown,
}


def get_report_formatter(name: str) -> Callable[[ReportBundle], str]:
    """Return a formatter callable for the requested ``name``."""

    key = name.strip().lower()
    if key not in _FORMATTERS:
        raise ValueError(f"Unsupported report format: {name}")
    return _FORMATTERS[key]


__all__ = ["ReportFormatter", "format_report_json", "format_report_markdown", "get_report_formatter"]
