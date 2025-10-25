# Changelog

## [Unreleased]
### Added
- Observability stack (`zscripts/observability`) with structured logging,
  Prometheus-compatible metrics, tracing spans, and a background health server.
- CLI instrumentation emits correlation IDs and dedicated metrics
  (`zscripts_cli_invocations_total`, `zscripts_cli_duration_seconds`) for every
  command, and the telemetry server now shuts down cleanly after execution.
- Telemetry-aware CLI flags (`--enable-telemetry`, `--log-level`, `--log-format`,
  `--telemetry-host`, `--telemetry-port`) plus an `extensions` subcommand to
  enumerate loaded plugins.
- Extension framework under `zscripts/extensions` with `ExtensionContext`,
  loader utilities, and a reference `plugin_echo` implementation.
- Developer tooling scripts: `scripts/dev_start.py` (quality gate with coverage
  threshold enforcement) and `scripts/scaffold_extension.py` (extension template
  generator).
- Documentation suite covering the new architecture overview, extension guide,
  automation playbook, incident response runbook, and roadmap.
- GitHub workflow (`ci.yml`) and Dependabot configuration to keep dependencies
  fresh.
- Stewardship artifacts (`STEWARDS_REPORT.md`, `AUTOMATION_ROLES.md`) describing
  Stage 4 audit metrics, agent responsibilities, and future roadmap.
### Added
- Trace-friendly pytest harness (`scripts/run_pytest_with_trace.py`) and a generated summary stored at `reports/coverage_summary.txt`.
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
- `cli.py` now pre-parses global options, loads extensions before command
  parsing, and passes a `TelemetryManager` into `ToolkitService` for automatic
  span recording.
- CLI telemetry instrumentation records status and duration exactly once via a
  unified `finally` block and tags agent automation hooks around command
  dispatch.
- `ToolkitService` wraps public methods in telemetry spans, emitting counters and
  latency histograms for collect/parse/summarise/guardrail operations.
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

### Fixed
- Prevent empty `--command` sequences from reaching the sandbox, ensuring actionable validation errors reach users.
- Lint violations throughout the sample assets and wrappers detected by Ruff.
- Consolidated dependency list with pinned tooling for reproducible local runs.
- Config loader now warns on duplicate entries and rejects paths that escape the configured log root.
- Consolidate/tree commands validate output destinations up front, yielding actionable errors on permission issues.
- Configuration flags pointing to missing files or directories now raise deterministic `ConfigurationError` messages before CLI dispatch.
