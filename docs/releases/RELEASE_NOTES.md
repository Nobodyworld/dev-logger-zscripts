# Release Notes

## Public Beta Status (2026-07-21)

The repository is public and remains `PUBLIC BETA — ACTIVE DEVELOPMENT`; no
stable tag or GitHub Release has been published. PRs #48 and #53 were
squash-merged, and `399792b687549ea97e9319ad9728c7494a0c7ede` is the exact
final locally validated SHA. The current hardening work restores the hosted
`quality` check, corrects public metadata, and makes JSON Schema validation a
declared runtime contract.

## Highlights
- Introduced a shared health check registry (`zscripts/observability/health_checks.py`)
  feeding the new `zscripts_health_checks_status` gauge, plus a
  `health_monitor` reference extension and tests that surface extension health in
  CLI diagnostics.
- Added `scripts/scaffold_module.py` so contributors and agents can scaffold
  telemetry-ready extensions or standalone health providers with a single
  command, supported by updated README/EXTENSION_GUIDE/AUTOMATION guidance.
- CI now runs `scripts/diagnostics_probe.py --include-metrics` after the quality
  gate and uploads the resulting snapshot alongside other reports to detect
  health regressions early.
- Delivered a diagnostics experience that combines
  `zscripts/observability/diagnostics.py`, the `python cli.py diagnostics`
  command, and the `scripts/diagnostics_probe.py` automation helper to export
  telemetry snapshots (with optional Prometheus metrics) for CI agents.
- Wrapped extension loading with an `ExtensionManager` and hook registry so
  plugins can register lifecycle callbacks while diagnostics report hook
  coverage; refreshed scaffolding and shipped a `metrics_probe` reference
  extension showcasing the pattern.
- Hardened CLI output destination validation to require execute permissions,
  exercised resolution/mkdir/cleanup failure scenarios via new tests, and
  delivered coverage/performance artifacts for the helper module.
- Clarified the Python 3.11+ runtime requirement and expanded the development
  extra so `make check` installs Ruff, mypy, Bandit, and Coverage without
  additional setup.
- Added a full observability stack (structured logging, metrics, tracing, and a
  health server) surfaced through new CLI flags.
- Hardened report severity evaluation so warning-only runs surface as warnings,
  expanded fail-on exit regression tests, and made the developer quality gate
  resilient to missing security scanners.
- CLI invocations now publish dedicated metrics (`zscripts_cli_invocations_total`,
  `zscripts_cli_duration_seconds`) and attach correlation IDs so operators can
  trace automation workflows end-to-end while ensuring the telemetry server
  shuts down cleanly after every command.
- Toolkit services now emit their own metrics via the embedded instrumentation
  manager, and the health server records HTTP traffic with
  `zscripts_health_http_requests_total` and latency histograms for probe
  observability.
- Extension loading captures manifest metadata (module, version, capabilities)
  surfaced by `python cli.py extensions --output-format json`; scaffolding
  templates include these attributes automatically.
- Added `scripts/ops_status.py` for automation-friendly health checks with JSON
  output and exit codes aligned to readiness.
- Published the Stage 4 stewardship report (`STEWARDS_REPORT.md`) and automation
  catalog, documenting code health metrics and safe agent responsibilities.
- Launched the extension framework and reference plugin, enabling third parties
  to register CLI commands safely.
- Introduced developer tooling (`scripts/dev_start.py`, `scripts/scaffold_extension.py`)
  plus CI/Dependabot automation to enforce quality gates.
- Hardened the configuration loader with deterministic cloning of base dataclasses
  and strict override validation for telemetry/logging keys.
- Added comprehensive regression tests for TOML/JSON inputs, invalid paths, and
  CLI override semantics.
- Introduced a trace-based coverage workflow (`scripts/run_pytest_with_trace.py`)
  that emits summaries to `artifacts/quality/coverage_summary.txt`.
- Tightened typing gates to the reporting and observability surfaces so `make
  check` enforces the strict subset without tripping legacy modules, and added
  regression coverage for empty-report edge cases.
- Raised automated test coverage to 90% by adding configuration validation,
  observability logging, and infrastructure adapter test suites. Coverage and
  quality gate artifacts are published under `artifacts/quality/` via `scripts/dev_start.py`.

## Coverage & Performance
- Automated quality gate now reports 88.5% line coverage in
  `artifacts/coverage/coverage.json` while documenting skipped security scans when Bandit
  is unavailable, improving CI diagnostics without blocking local workflows.
- Stage 2 now exports a trace-based coverage snapshot in
  `artifacts/coverage/coverage_stage2.txt` (generated via `python -m trace --count --summary`)
  alongside `artifacts/quality/performance_notes_stage2.md`, confirming the full suite runs
  without the third-party `coverage` package in restricted environments.

## Upgrade Notes
- Register custom health providers through `TelemetryManager.register_health_check`
  or `ExtensionContext.health_checks.register` to appear in diagnostics payloads
  and Prometheus output.
- Use `python scripts/scaffold_module.py` (subcommands `extension` and `health`)
  for new modules so instrumentation, logging, and TODO markers remain
  consistent.
- New configuration keys are available: `telemetry_enabled`, `telemetry_host`,
  `telemetry_port`, `log_level`, `log_format`, and `extensions`. Existing files
  remain compatible; unspecified keys default to safe values.
- Global CLI toggles (`--enable-telemetry`, `--telemetry-host`, `--telemetry-port`,
  `--log-level`, `--log-format`) now apply before command parsing to support
  extension registration and logging configuration.
- Run `python scripts/dev_start.py` (or `make quality`) to execute the full lint
  → type → security → pytest + coverage pipeline. The script enforces ≥85%
  coverage and writes `artifacts/quality/quality_gate.json`.
- Use `python cli.py extensions --output-format json` to inspect manifest data
  for loaded extensions, or call `scripts/ops_status.py --url http://host:port`
  to probe telemetry health in deployment pipelines.
- To reproduce the trace-based coverage summary, run
  `python -m trace --count --summary --coverdir=coverage_reports scripts/run_pytest_with_trace.py`; the curated output is written
  to `artifacts/quality/coverage_summary.txt`.
- When third-party coverage tooling is unavailable, fall back to
  `python -m trace --count --coverdir trace_cov --module pytest` and parse the
  generated `.cover` files (see `STEWARDS_REPORT.md`) before deleting `trace_cov/`.

## Breaking Changes
- None.
