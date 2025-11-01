# Changelog

## [Unreleased]
### Added
- Health check registry (`zscripts/observability/health_checks.py`) wired into
  the telemetry manager and diagnostics output, including a Prometheus gauge
  (`zscripts_health_checks_status`) and CLI support for extension-provided
  readiness probes.
- Reference `health_monitor` extension plus scaffolding updates that register
  baseline health snapshots and demonstrate registry usage in tests.
- Unified scaffolding tool `scripts/scaffold_module.py` for generating
  extensions or standalone health providers, accompanied by
  `agents/AGENTS.md` guardrails and expanded documentation across README,
  EXTENSION_GUIDE, and AUTOMATION.
- Regression test covering `python cli.py diagnostics --output <directory>` to
  guarantee the command surfaces `OutputPathError` with actionable messaging.
- Trace-based coverage export in `artifacts/coverage/coverage_stage2.txt` that captures the
  full Stage 2 suite when the `coverage` package is unavailable in restricted
  environments.
- Diagnostics pipeline featuring `zscripts/observability/diagnostics.py`, a
  `python cli.py diagnostics` command, and the agent-friendly
  `scripts/diagnostics_probe.py` helper for capturing telemetry snapshots and
  Prometheus metrics on demand.
- Extension hook registry and manager wrapping `load_extensions`, enabling
  plugins to register lifecycle callbacks and exposing hook counts through
  diagnostics payloads and documentation.
- Reference `metrics_probe` extension plus scaffolding updates that demonstrate
  hook registration and structured logging for future plugin authors.
- Unit tests covering diagnostics helpers, CLI output formats, and hook
  emission to preserve observability guarantees.
- Stage 2 hardening artifacts for CLI output helpers, including
  `EXEC_PLAN_STAGE2_OUTPUT_SAFETY_VALIDATION.md`,
  `artifacts/coverage/coverage_stage2.txt`, and
  `artifacts/quality/performance_notes_stage2.md`.
- Regression tests covering configuration validation edge cases, observability
  logging JSON formatting, and infrastructure adapters/sandbox wrappers,
  elevating overall coverage to ~90% with artifacts in `artifacts/quality/`.
- Observability stack (`zscripts/observability`) with structured logging,
  Prometheus-compatible metrics, tracing spans, and a background health server.
- Health server metrics now track HTTP request counts, latency, and inflight
  probes via `zscripts_health_http_requests_total` and related series.
- CLI instrumentation emits correlation IDs and dedicated metrics
  (`zscripts_cli_invocations_total`, `zscripts_cli_duration_seconds`) for every
  command, and the telemetry server now shuts down cleanly after execution.
- Telemetry-aware CLI flags (`--enable-telemetry`, `--log-level`, `--log-format`,
  `--telemetry-host`, `--telemetry-port`) plus an `extensions` subcommand to
  enumerate loaded plugins.
- Extension framework under `zscripts/extensions` with `ExtensionContext`,
  loader utilities, and a reference `plugin_echo` implementation.
- Runtime manifest registry (`zscripts/extensions/manifest.py`) capturing
  extension metadata surfaced via `python cli.py extensions --output-format json`
  and integrated into scaffolding templates.
- Developer tooling scripts: `scripts/dev_start.py` (quality gate with coverage
  threshold enforcement) and `scripts/scaffold_extension.py` (extension template
  generator).
- Operational probe script `scripts/ops_status.py` for agent-friendly health
  checks with JSON output and failure-aware exit codes.
- Documentation suite covering the new architecture overview, extension guide,
  automation playbook, incident response runbook, and roadmap.
- GitHub workflow (`ci.yml`) and Dependabot configuration to keep dependencies
  fresh.
- Stewardship artifacts (`STEWARDS_REPORT.md`, `docs/automation/AUTOMATION_ROLES.md`) describing
  Stage 4 audit metrics, agent responsibilities, and future roadmap.
### Added
- Trace-friendly pytest harness (`scripts/run_pytest_with_trace.py`) and a generated summary stored at `artifacts/quality/coverage_summary.txt`.
- Expanded configuration loader tests covering JSON files, delimiter handling, and defensive error paths.
- Architecture, API, workflow, dependency, and final summary documentation under `docs/` to support the Codex refinement chain.
- README usage walkthroughs and CLI help examples for common collection flows.
- Strict linting, typing, security scanning, and property tests wired into `make check` and pre-commit hooks.
- Structured logging with error identifiers across CLI utilities and the sample database manager.
- Hypothesis-based regression tests covering CLI parsers and ignore pattern expansion.
- `--dry-run` and `--verbose` flags across CLI commands plus utilities for planning log generation and tree previews.
- `--max-bytes` and `--output -` flags enabling tree and consolidate commands to stream artifacts directly to STDOUT.
- Environment variable override (`ZSCRIPTS_CONFIG_PATH`) for pointing the CLI at alternative configuration files.
- Centralised preset registry under `zscripts/presets.py` with serialisable metadata.
- Agent adapter module (`agents/cli_adapter.py`) that exports CLI command schemas and presets for automation.
- Tests covering output-path validation and agent metadata payloads.

### Changed
- Performed a post-refactor validation pass: added README files to every top-level
  directory, refreshed the root README/SPEC/style guide to reflect the new
  layout, modernised agent CLI metadata, and tightened type hints across
  automation helpers and IO utilities.
- Reorganized repository layout: consolidated execution plans and automation guides under `docs/`, moved sample fixtures to `examples/`, and redirected quality artifacts to `artifacts/` to simplify the repository root.
- CI workflow now executes `scripts/diagnostics_probe.py` after the quality gate
  and uploads the telemetry snapshot so registry regressions are caught in PRs.
- Raised the minimum supported Python version to 3.11, documented the
  requirement in the README, and expanded the `dev` extra to install Ruff,
  mypy, Bandit, and Coverage so `make check` runs end-to-end without manual
  setup.
- Refined `scripts/scaffold_extension.py` to use a defensive import fallback
  while satisfying strict import-order linting.
- Replaced the telemetry endpoint canonicalisation `match` statement with
  straightforward conditionals to avoid runtime guardrails depending on Python
  3.10 syntax support.
- Output destination validation now requires execute permission for parent
  directories and exercises resolution/mkdir/cleanup failure branches; helper
  coverage increased to 100% with targeted unit tests.
- `cli.py` now pre-parses global options, loads extensions before command
  parsing, and passes a `TelemetryManager` into `ToolkitService` for automatic
  span recording.
- Developer quality gate (`scripts/dev_start.py`) gracefully skips missing
  security scanners and records the reason instead of failing the pipeline.
- CLI telemetry instrumentation records status and duration exactly once via a
  unified `finally` block and tags agent automation hooks around command
  dispatch.
- `ToolkitService` now wraps public methods in telemetry operations, emitting
  metrics via a dedicated instrumentation manager while still producing spans
  for collect/parse/summarise/guardrail operations.
- The `extensions` CLI command accepts `--output-format json` to expose manifest
  metadata (module, version, capabilities) for automation tooling.
- Configuration loader accepts new telemetry/logging/extension keys while
  preserving strict validation semantics.
- ToolkitService now caches sandbox runners and validates sandbox command sequences before execution.
- CLI collect handler surfaces friendly error messages (exit code 2) when log sources are missing or malformed.
- Sample project models refactored to dataclasses with deterministic timestamps.
- Legacy wrapper scripts simplified to import the shared CLI directly.
- README now documents verification commands, observability practices, and SLO expectations.
- Ignore handling refactored with cached gitignore ingestion, case-aware matching, and support for negated patterns.
- CLI help strings now derive type choices from the preset registry to avoid drift.
- README, ARCHITECTURE, and AI interface documentation updated for agent workflows.
- Configuration loader clones base dataclasses instead of mutating shared defaults and normalizes path overrides.
- Hardened observability helpers and reporting formatters to satisfy strict
  mypy gates and remove pytest collection warnings.

### Fixed
- Prevent empty `--command` sequences from reaching the sandbox, ensuring actionable validation errors reach users.
- Lint violations throughout the sample assets and wrappers detected by Ruff.
- Consolidated dependency list with pinned tooling for reproducible local runs.
- Report severity now honors warning-only statuses and exercises fail-on
  thresholds via focused unit tests, preventing false negatives in CI gating.
- Config loader now warns on duplicate entries and rejects paths that escape the configured log root.
- Consolidate/tree commands validate output destinations up front, yielding actionable errors on permission issues.
- Configuration flags pointing to missing files or directories now raise deterministic `ConfigurationError` messages before CLI dispatch.
- Removed pytest collection warnings for `TestCaseResult`/`TestSummary` and
  ensured guardrail metadata renders deterministically even with empty payloads.
