# Automation & Agent Playbook

This guide summarises how automated agents should interact with the toolkit.

## Telemetry

- Enable telemetry when running long-lived commands by passing
  `--enable-telemetry` (or setting `telemetry_enabled = true` in the
  configuration). The CLI spins up an HTTP server on
  `http://<host>:<port>/healthz` plus readiness (`/healthz/ready`), liveness
  (`/healthz/live`), and `/metrics` endpoints for Prometheus scrapes. Host and
  port are configurable via `telemetry_host` and `telemetry_port`.
- CLI invocations increment `zscripts_cli_invocations_total` and
  `zscripts_cli_duration_seconds` metrics labelled by command and status.
  Instrumented operations also emit `zscripts_operations_total`,
  `zscripts_operation_duration_seconds`, and the `zscripts_extensions_active`
  gauge. The health server entrypoint (`HealthTelemetryServer.do_GET`, tagged
  with `# agent-entrypoint`) publishes
  `zscripts_health_http_requests_total`,
  `zscripts_health_http_request_duration_seconds`, and
  `zscripts_health_http_requests_inflight` so operators can observe probe
  traffic.
- Logs use structured key/value format. Set `--log-format json` for machine
  parsing or `--log-level DEBUG` to increase verbosity.
- Each CLI run binds a correlation ID that is propagated into span logs, so log
  aggregators can group related events without additional hints.
- Use `python cli.py diagnostics --include-metrics` (or the
  `scripts/diagnostics_probe.py` helper) to snapshot telemetry state, active
  extensions, and hook registrations. The probe exits non-zero when the
  reported status falls below `ok`, making it suitable for CI smoke checks.

## Quality Gate

- Run `python scripts/agent_guard.py` for fast feedback when iterating locally.
  The guard executes linting, mypy (strict), Bandit, and pytest; use
  `--only/--skip` to tailor workloads. For coverage-enforced runs, continue to
  use `python scripts/dev_start.py` or `make quality`, which also produce
  `reports/quality_gate.json`.
- Quality summaries from `dev_start.py` are written to `reports/quality_gate.json`;
  upload the file as a CI artifact for post-run auditing.
- After a full gate, execute `python scripts/collect_quality_metrics.py --output reports/metrics.json`
  to capture coverage, complexity, dependency, build footprint, and CLI latency metrics for the steward report.
- To skip expensive steps locally, set the following environment variables to
  any truthy value: `ZSKIP_LINT`, `ZSKIP_TYPE`, `ZSKIP_SECURITY`, `ZSKIP_TESTS`.
  Coverage enforcement is automatically disabled when tests are skipped.

## Extension Safety

- New extensions must live under `zscripts/extensions/` and expose a
  `get_extension()` factory that returns a `ToolkitExtension` implementation.
  Follow `zscripts/extensions/AGENTS.md` for naming and logging conventions.
- Use `python cli.py extensions scaffold <name>` (or the
  `scripts/scaffold_extension.py` helper) to generate boilerplate with
  instrumentation hooks. Set `capabilities`, `version`, and `config_keys` so the
  manifest contains actionable metadata.
- Query manifests via `python cli.py extensions --output-format json` or from
  within code using `extension.manifest`. Automation agents can cache this to
  decide which plugins to invoke.

## Incident Response

- The health server (`/healthz`) returns JSON describing status, version, and
  active telemetry endpoints. Pair it with `/metrics` to inspect counters for
  CLI operations, sandbox outcomes, and HTTP probe traffic. Use the correlation
  ID from log records when pivoting between logs and metrics for a specific
  automation run.
- `python scripts/ops_status.py --url http://<host>:<port>` provides an
  agent-friendly probe that writes a JSON summary to STDOUT (and optionally a
  file) while setting exit codes based on health status. Integrate this into
  orchestration checks or post-deploy smoke tests.
- `python scripts/diagnostics_probe.py --output reports/diagnostics.json` emits
  the same payload as `cli diagnostics`, including hook summary and optional
  metrics text, and can fail pipelines when telemetry reports a degraded state
  (see `--fail-on-status`).
- Consult `docs/operations.md` and `docs/operations/INCIDENT_RESPONSE.md` for
  runbook procedures, including suggested queries and log correlation
  strategies.

Automation agents should treat this document as the canonical reference for
running checks, collecting telemetry, and extending the platform safely.
