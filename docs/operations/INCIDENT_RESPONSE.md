# Incident Response Runbook

Use this playbook to diagnose issues when zscripts is embedded in automation.

## 1. Confirm Telemetry

1. Query the health endpoint: `curl http://<host>:<port>/healthz`
   - Expected response: `{"status": "ok", "version": "...", ...}`
   - If unavailable, restart the CLI with `--enable-telemetry` and verify the
     port is not blocked by host firewalls.
2. Scrape metrics: `curl http://<host>:<port>/metrics`
   - Check `zscripts_requests_total` (operation + status labels) and
     `zscripts_request_duration_seconds` for latency spikes.

## 2. Inspect Logs

- Structured logs default to text; use `--log-format json` for ingestion into
  log aggregators. Correlate events via the `correlation_id` field, which maps to
  the active trace.
- Increase verbosity with `--log-level DEBUG` to surface adapter decisions and
  sandbox commands.

## 3. Validate Extensions

- List loaded extensions: `python cli.py extensions`
  - Missing extensions typically indicate configuration drift. Verify the
    `extensions` array in the active config and ensure modules import correctly.
- For extension-specific commands, wrap execution in telemetry spans:
  `context.telemetry.span("ext.<name>")` to monitor failures.

## 4. Sandbox Failures

- Check the guardrails snapshot: `python cli.py guardrails` and confirm
  `dangerous_mode` and `allowed_paths` are expected.
- Review `zscripts_requests_total{operation="collect_logs",status="error"}`
  for spikes. Use the correlation ID from logs to reproduce the failing command.

## 5. Recovery Steps

- Restart automation workers with `--enable-telemetry` to keep health endpoints
  accessible during post-incident analysis.
- Run `python scripts/dev_start.py` to validate the codebase (lint/type/tests)
  before rolling out fixes. Ensure the coverage report meets the 85% threshold.

## Residual Risks

- Telemetry server is single-threaded; avoid overloading with aggressive scrape
  intervals. Recommended scrape interval ≥ 10 seconds.
- Extensions run in-process and share the same telemetry. Poorly written
  extensions can degrade metrics fidelity—review new modules using
  `scripts/scaffold_extension.py` as a baseline.
