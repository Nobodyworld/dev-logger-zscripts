# Reporting Guide

The `report` command produces a comprehensive artifact that combines
normalized log data, summaries, explanations, guardrail metadata, and optional
redacted payloads. Reports can be emitted as structured JSON for automation or
Markdown for human-readable runbooks.

## CLI usage

```bash
python cli.py report --input examples/python/sample.log --format json --output report.json
python cli.py report --input examples/python/sample.log --format markdown
python cli.py report --input examples/python/sample.log --fail-on errors
```

Key flags:

- `--format`: Choose `json` (default) or `markdown`. When omitted, the CLI uses
  the `report_format` value from configuration.
- `--redact/--no-redact`: Toggle whether textual fields (summary, explanation,
  and collected payload) are passed through the redactor. Defaults to the
  `report_redact` configuration value.
- `--fail-on`: Exit with status 1 when the computed severity meets/exceeds the
  requested threshold. Choices: `never` (default), `warnings`, `errors`.
- `--output`: Optional path for writing the rendered report. Without it the
  document is printed to STDOUT.

When `--output` is provided the CLI prepares parent directories automatically
and writes files atomically. Invalid destinations trigger descriptive errors (for
example, "destination '<path>' is a directory" or "parent directory '<path>' is
not writable") before any report content is emitted, ensuring previous
artifacts remain intact.

The command honours all global flags (`--config`, `--set`, `--adapter`,
`--enable-telemetry`, etc.) and records telemetry spans/metrics under the
`cli.report` namespace.

## Output formats

### JSON

The JSON formatter wraps the `ReportBundle` dataclass into a serializable
structure with ISO-8601 timestamps. Example (truncated for brevity):

```json
{
  "normalized": {"tool": "pytest", "status": "failed", ...},
  "summary": "Aggregated summary",
  "explanation": "Tool: pytest\nEcosystem: python\n...",
  "guardrails": {"allowed_paths": ["examples"], "timeout_seconds": 120},
  "redacted_text": null,
  "generated_at": "2024-01-01T00:00:00+00:00",
  "severity": "error"
}
```

Use this output in downstream automation or ingest it into observability
pipelines.

Severity is derived from the normalized log: errors, failed statuses, or test
failures yield `error`; warnings without errors yield `warning`; otherwise
`ok`.

### Markdown

Markdown reports are organized into sections (Summary, Explanation, Issues,
Tests, Guardrails, Artifacts, Metadata). This format is ideal for attaching to
incident tickets or sharing status updates. The formatter collapses list values
into bullet lists and includes test case breakdowns when available.

## Configuration integration

Add the following keys to your configuration to set defaults:

```toml
report_format = "markdown"  # switch default renderer
report_redact = true        # redact textual fields automatically
report_fail_on = "warnings" # fail when warnings or errors are present
```

Runtime overrides always win: pass `--format json` or `--no-redact` to change
the behavior for a single invocation without editing configuration files.
Use `--fail-on` to override the failure policy without touching configuration.

## Telemetry and metrics

Reports inherit the same telemetry instrumentation as other commands. Enabling
`--enable-telemetry` exposes Prometheus counters/histograms labelled with
`command="report"` and the execution status. Each invocation also records a
`cli.report` span containing the chosen adapter and elapsed time.

## Testing hooks

Unit tests covering `ToolkitService.generate_report`, the formatter utilities,
and the CLI integration live under `tests/test_services.py`,
`tests/test_reporting.py`, and `tests/test_cli.py` respectively. Refer to those
files when extending the workflow or adding new output formats.
