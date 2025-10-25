# Release Notes

## Highlights
- Added a full observability stack (structured logging, metrics, tracing, and a
  health server) surfaced through new CLI flags.
- Launched the extension framework and reference plugin, enabling third parties
  to register CLI commands safely.
- Introduced developer tooling (`scripts/dev_start.py`, `scripts/scaffold_extension.py`)
  plus CI/Dependabot automation to enforce quality gates.
- Hardened the configuration loader with deterministic cloning of base dataclasses
  and strict override validation for telemetry/logging keys.
- Added comprehensive regression tests for TOML/JSON inputs, invalid paths, and
  CLI override semantics.
- Introduced a trace-based coverage workflow (`scripts/run_pytest_with_trace.py`)
  that emits summaries to `reports/coverage_summary.txt`.

## Upgrade Notes
- New configuration keys are available: `telemetry_enabled`, `telemetry_host`,
  `telemetry_port`, `log_level`, `log_format`, and `extensions`. Existing files
  remain compatible; unspecified keys default to safe values.
- Global CLI toggles (`--enable-telemetry`, `--telemetry-host`, `--telemetry-port`,
  `--log-level`, `--log-format`) now apply before command parsing to support
  extension registration and logging configuration.
- Run `python scripts/dev_start.py` (or `make quality`) to execute the full lint
  → type → security → pytest + coverage pipeline. The script enforces ≥85%
  coverage and writes `reports/quality_gate.json`.
- To reproduce the trace-based coverage summary, run
  `python -m trace --count --summary --coverdir=coverage_reports scripts/run_pytest_with_trace.py`; the curated output is written
  to `reports/coverage_summary.txt`.

## Breaking Changes
- None.
