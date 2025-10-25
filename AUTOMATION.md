# Automation & Agent Playbook

This guide summarises how automated agents should interact with the toolkit.

## Telemetry

- Enable telemetry when running long-lived commands by passing
  `--enable-telemetry` (or setting `telemetry_enabled = true` in the
  configuration). The CLI spins up an HTTP server on
  `http://<host>:<port>/healthz` and `/metrics` for liveness checks and
  Prometheus scrapes. Host and port are configurable via `telemetry_host` and
  `telemetry_port`.
- CLI invocations increment `zscripts_cli_invocations_total` and
  `zscripts_cli_duration_seconds` metrics labelled by command and status. Alert
  on sustained `status="error"` counts and track latency percentiles using the
  histogram buckets.
- Logs use structured key/value format. Set `--log-format json` for machine
  parsing or `--log-level DEBUG` to increase verbosity.
- Each CLI run binds a correlation ID that is propagated into span logs, so log
  aggregators can group related events without additional hints.

## Quality Gate

- Run `python scripts/dev_start.py` (or `make quality`) before publishing
  changes. The script executes linting, mypy (strict), bandit, pytest with
  coverage, and enforces a minimum coverage of 85%.
- The summary is written to `reports/quality_gate.json` and includes step
  duration, status, and coverage percentage. Upload the file as a CI artifact
  for post-run auditing.
- To skip expensive steps locally, set the following environment variables to
  any truthy value: `ZSKIP_LINT`, `ZSKIP_TYPE`, `ZSKIP_SECURITY`, `ZSKIP_TESTS`.
  Coverage enforcement is automatically disabled when tests are skipped.

## Extension Safety

- New extensions must live under `zscripts/extensions/` and expose a
  `get_extension()` factory that returns a `ToolkitExtension` implementation.
  Follow `zscripts/extensions/AGENTS.md` for naming and logging conventions.
- Use the scaffold script (`scripts/scaffold_extension.py`) to avoid missing
  boilerplate.

## Incident Response

- The health server (`/healthz`) returns JSON describing status, version, and
  active telemetry endpoints. Pair it with `/metrics` to inspect counters for
  CLI operations and sandbox outcomes. Use the correlation ID from log records
  when pivoting between logs and metrics for a specific automation run.
- Consult `docs/operations/INCIDENT_RESPONSE.md` for runbook procedures,
  including suggested queries and log correlation strategies.

Automation agents should treat this document as the canonical reference for
running checks, collecting telemetry, and extending the platform safely.
