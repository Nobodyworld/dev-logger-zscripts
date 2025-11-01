# Automation Roles & Safe Tasks

This catalog describes recommended agent responsibilities and the guardrails that keep
automation safe within the zscripts repository. Each role references concrete commands
and `# agent-entrypoint` / `# agent-safe-task` tags inside the codebase.

## Roles

### Test Maintainer

- **Responsibilities**: Execute `pytest`, run the coverage-enforced quality gate (`python scripts/dev_start.py`), and refresh
  repository metrics via `python scripts/collect_quality_metrics.py --output artifacts/quality/metrics.json`. Confirm the generated report
  includes `cli_guardrails_latency_seconds`. When coverage wheels are unavailable, fall back to `python -m trace --count
  --coverdir trace_cov --module pytest`.
- **Entry Points**: CLI command dispatch in `zscripts/cli.py` (`# agent-entrypoint`) and metrics helper (`# agent-safe-task`).
- **Guardrails**: Clean up `trace_cov/` artifacts after fallback runs; never bypass `_fail` error handling.

### Documentation Steward

- **Responsibilities**: Refresh README, steward reports, and extension guides after significant behavioral changes.
- **Entry Points**: Markdown documentation under the repository root and `docs/`.
- **Guardrails**: Align doc updates with observed behavior; cross-check instructions with automated tests before publishing.

### Observability Watcher

- **Responsibilities**: Monitor telemetry outputs, adjust metric naming, and verify health endpoints stay consistent.
- **Entry Points**: `zscripts/observability/*` modules and CLI telemetry wrappers. Automation may hook into
  `HealthTelemetryServer.do_GET` (`# agent-entrypoint`) for HTTP probes.
- **Guardrails**: Use `TelemetryManager.span()` for new instrumentation; avoid introducing blocking calls inside `main()`.

### Perf Optimizer

- **Responsibilities**: Profile CLI latency, propose caching/backpressure strategies, and validate improvements via targeted tests.
- **Entry Points**: CLI dispatch code and adapter implementations under `zscripts/infrastructure`.
- **Guardrails**: Preserve exception semantics and `_record_cli_metrics` updates; document any stateful caching decisions.

## Automation Hooks

- `# agent-entrypoint` identifies orchestration hotspots where agents may wrap additional
  automation logic (e.g., invoking commands before/after handler execution).
- `# agent-safe-task` marks helper functions that agents can extend (e.g., adding labels
  or metrics) without risking control-flow regressions.

Agents should cross-reference `EXEC_PLAN_STEWARD_AUDIT.md` and `STEWARDS_REPORT.md` for the
latest constraints and to record new discoveries.
