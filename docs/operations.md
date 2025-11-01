# Operations & Incident Response Guide

This guide explains how to observe, troubleshoot, and recover the zscripts toolkit in
production or automated environments.

## Telemetry Endpoints

The toolkit exposes an HTTP server (disabled by default) that publishes health checks and
Prometheus metrics. Enable it by passing `--enable-telemetry` to the CLI or setting
`telemetry_enabled` to `true` in `configs/zscripts.config.json`.

Once enabled, the server listens on `telemetry_host`/`telemetry_port` (defaults to
`127.0.0.1:9464`). The following endpoints are available:

- `GET /healthz` – Aggregated status that includes readiness and liveness sections.
- `GET /healthz/ready` – Readiness for serving CLI/agent requests. Returns HTTP 503 when
  the telemetry server has not fully started.
- `GET /healthz/live` – Liveness heartbeat. Returns HTTP 200 when the telemetry thread is
  alive, or 503 if the process is shutting down.
- `GET /metrics` – Prometheus exposition including CLI, extension, service, and
  HTTP-probe metrics.
- `python cli.py diagnostics` – Structured snapshot combining the health payload,
  extension manifest data, hook registrations, and optional Prometheus text. Use
  `--include-metrics` to embed the raw exposition in JSON output.
- `python scripts/diagnostics_probe.py --output artifacts/diagnostics/diagnostics.json` –
  Automation-friendly wrapper that writes the same snapshot to disk and exits
  non-zero when telemetry reports a degraded status (configurable via
  `--fail-on-status`).

Example response for `/healthz`:

```
{
  "status": "ok",
  "version": "1.2.3",
  "telemetry_enabled": true,
  "health_endpoint": "http://127.0.0.1:9464/healthz",
  "metrics_endpoint": "http://127.0.0.1:9464/metrics",
  "liveness": {"status": "ok", "http_server": "running"},
  "readiness": {"status": "ok", "telemetry": "enabled"},
  "checks": {"http_server": {"status": "ok", "host": "127.0.0.1", "port": 9464}}
}
```

## Metrics to Watch

The Prometheus output includes the following core series:

- `zscripts_operations_total` / `zscripts_operation_duration_seconds` – per-component
  operation counts and latency (e.g., `component="cli"`, `component="extensions"`).
- `zscripts_cli_invocations_total` / `zscripts_cli_duration_seconds` – CLI level metrics
  labelled by command name and status.
- `zscripts_extensions_active` – Gauge representing the number of loaded extensions.
- `zscripts_operations_inflight` – Gauge showing in-flight instrumented operations.
- `zscripts_health_http_requests_total` /
  `zscripts_health_http_request_duration_seconds` – Traffic volume and latency
  for `/healthz` probes, labelled by endpoint. High error rates here indicate
  external monitors are failing.

Alert on sustained increases in `status="error"` labels or large inflight counts. Pair
metrics with structured logs filtered by correlation IDs.

## Correlation IDs & Logging

Every CLI invocation is wrapped in an instrumentation operation that binds a correlation
ID. The ID surfaces in structured logs (`cid=<hex>`) and in metrics labels. To trace a
request across services:

1. Run the CLI with telemetry enabled.
2. Capture the correlation ID from the log output (e.g., `cid=abcd1234`).
3. Query Prometheus for metrics filtered by `correlation_id="abcd1234"` or inspect log
   entries containing the same ID.

## Incident Response Workflow

1. **Verify process health** – Request `/healthz/ready` and `/healthz/live`. If either
   returns HTTP 503, restart the toolkit process or re-enable telemetry. The
   helper `python scripts/ops_status.py --url http://127.0.0.1:9464` performs this
   check and exits non-zero when the status is degraded.
2. **Check metrics for anomalies** – Scrape `/metrics` and inspect `status="error"`
   labels on `zscripts_operations_total` or `zscripts_cli_invocations_total`.
3. **Review structured logs** – Use the correlation ID from the failing command to locate
   the error in `examples/artifacts/zscripts_logs/` or centralised log storage.
4. **Mitigate** – Disable problematic extensions by removing them from the configuration
   or redeploy with known-good settings. The `zscripts_extensions_active` gauge should
   drop after removal.
5. **Recover** – Once metrics return to normal and health endpoints return HTTP 200,
   re-enable blocked automation or agents. Document the incident in the change log.

## Rollback Strategy

If a release introduces regressions:

- Revert to the previous git tag (documented in `CHANGELOG.md`).
- Use `make check` to validate the rollback locally before redeploying.
- Keep telemetry enabled during rollback to ensure readiness probes reflect the new
  state.

## Additional Tools

- Issue an HTTP GET against `http://<host>:<port>/healthz` to surface the active health snapshot
  directly in the terminal (for example, `curl -s http://127.0.0.1:9464/healthz | jq .`).
  Alternatively run `python scripts/ops_status.py --url http://127.0.0.1:9464` to obtain a
  timestamped JSON summary suitable for automated pipelines.
- Run `python cli.py diagnostics --format text` for a quick CLI summary or
  `python scripts/diagnostics_probe.py --include-metrics` to capture a JSON
  artifact for incident retrospectives.
- `scripts/agent_guard.py` runs lint, type, and test gates with the
  same metrics instrumentation for agent-friendly workflows.

Keep this document updated whenever telemetry formats or operational workflows change.
