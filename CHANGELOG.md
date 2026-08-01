# Changelog

## [Unreleased]

### Fixed

- Make snapshot evidence-status schema support surface-aware so readable schema
  versions are not labeled globally unsupported, and announce asynchronous
  status-load failures through one stable polite live region.
- Enforce the Handoff format-2 JSON limit against the exact final normalized
  UTF-8 bytes after warnings, omitted counts, and truncation metadata. Optional
  evidence is removed deterministically; an oversized required envelope fails
  with a bounded error, and saved-output integrity retains the same format-2
  digest contract.

### Added

- Snapshot-label presentation contract version `1`, shared across the current,
  Compare, and Handoff selectors and saved-handoff context. Labels use UTC
  second precision, observed branch/Git/worktree facts or an explicit unknown
  state, a short snapshot suffix, and partial-evidence markers without changing
  snapshot ordering, defaults, identity, comparison, or Handoff persistence.
- Evidence-status presentation contract version `1`, a strict lightweight
  snapshot endpoint, and shared accessible persistent banners across Overview,
  Symbols, Relationships, Findings, Compare, and Handoff. The presentation
  distinguishes snapshot partial evidence from bounded-query truncation,
  preserves exact selected-snapshot lifecycle authority, and leaves analyzer,
  evidence, rule-set, SQLite, comparison, Handoff, and queue-preset versions
  unchanged.
- A versioned server-side `high-signal-v1` Findings queue preset, used by the
  clearly labeled default workspace while complete family/lifecycle counts and
  one-action access to all findings remain available. Finding evidence,
  identities, rules, lifecycle, and stored schema versions are unchanged.
- A sanitized, reproducible Repository Review dogfood harness and evidence-backed
  product report covering the complete Scan, Explore, Review, Compare, and
  Handoff workflow with explicit recommendations for focused polish.
- Deterministic same-repository snapshot comparison across files, symbols,
  relationships, cycles, metrics, and finding occurrences, with explicit
  compatibility/partial evidence and a bounded Compare workspace.
- Versioned local handoff rendering with explicit evidence/note selection,
  deterministic Markdown/JSON, budgets and omitted counts, clipboard/download
  actions, and immutable saved handoffs. SQLite schema advances to 5;
  analyzer/evidence/rule-set versions remain 3/3/4.
- Deterministic repository metrics and conservative finding candidates with
  stable repository-scoped identities, schema-v3 lifecycle reconciliation,
  optimistic review decisions/history, bounded API/CLI queries, and the
  accessible Findings workspace. Rule-set version advances to 4; analyzer
  version remains 3.
- Correct bounded relationship discovery and resolution with server-side node
  search, complete neighborhood request identities, proven qualified-name
  bindings, and conservative `Literal`/`Annotated` handling. Analyzer and
  rule-set versions advance to 3 while evidence and database schemas remain 2.
- Deterministic import, containment, inheritance, and bounded type-reference
  evidence for Repository Review, including explicit ambiguous/unresolved
  records, SCC/cycle analysis, fan-in/fan-out, bounded graph APIs, and the
  accessible Relationships workspace.
- SQLite repository-review schema v2 migration with atomic graph persistence,
  stable relationship/cycle identities, and explicit empty relationship
  responses for v1 snapshots.
- Experimental Repository Review MVP: bounded read-only generic-Python
  discovery and AST extraction, versioned deterministic evidence, atomic local
  SQLite snapshots, experimental CLI and loopback API, and responsive React
  Overview/Symbols views with progress, cancellation, prior snapshots, filters,
  sorting, pagination, and bounded source evidence.
- Repository-review hostile-input, determinism, rollback, cancellation, API,
  frontend, and packaged-workspace tests plus named CI/quality operations.
- Public repository-review architecture, configuration, privacy, dependency,
  workflow, data-deletion, and static-analysis limitation documentation.

### Fixed

- Repository Review now deduplicates identical content-derived diagnostics
  before snapshot persistence, allowing repeated file-count-limited scans to
  reuse deterministic evidence without a SQLite key collision.
- Repository comparison now preserves immutable branch/worktree observations
  in evidence-schema-v4 snapshot identity, migrates older observations as
  unknown, models partial absence on both comparison sides, rejects stale
  handoff selections, digests exact format-v2 rendered bytes, verifies saved
  output integrity, and preserves validated saved previews across pair
  rehydration. SQLite schema advances to 6; analyzer/rule-set remain 3/4.

- Finding lifecycle reconciliation now skips absence-based resolution for
  truncated scans and parse gaps, orders overlapping analyses by
  repository-local generation, applies current-repository lifecycle semantics
  consistently across summary/list/detail queries, and refreshes bounded
  frontend queues after review saves or conflicts. SQLite schema advances to 4;
  analyzer/evidence/rule-set versions remain 3/3/4.

- Evidence-backed consumer and ownership review for the seven temporary legacy
  helper compatibility points, plus the public-beta deprecation notice. The
  notice starts the required cycle without authorizing Phase 2B; all owner
  fields remain unassigned and all 154 helpers remain wheel-included.

- Phase 2A legacy-helper compatibility contracts: a deterministic 154-module
  surface freeze, seven temporary registry compatibility points, maintained-core
  import-boundary enforcement, and canonical quality-gate checks. Helpers remain
  wheel-included and unchanged; Phase 2B is not authorized.

- Public release documentation updates including
  `docs/operations/PUBLIC_RELEASE_AUDIT.md` and
  `docs/operations/CLEAN_CLONE_RELEASE_VALIDATION.md`.
- ETL documentation additions with `docs/guides/LOG_ETL_CASE_STUDY.md` and
  expanded schema mapping guidance in `docs/schema.md`.
- Package-level console script entry point `zscripts` via
  `project.scripts` in `pyproject.toml`.
- Regression tests for adapter inventory coverage, service redaction ordering,
  and zipapp runtime validation.
- Operational baseline and quality audit documentation, zipapp build/deploy
  workflow targets, and agent metadata tests covering the expanded CLI surface.
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

### Added (Historical)

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

- Public-beta package metadata now uses the Beta classifier, SPDX `MIT` license
  metadata with the license file included in wheels, and a required
  `jsonschema>=4.21,<5` runtime dependency so normalized-payload validation
  cannot silently disable itself.
- Public status and support documentation now reflects the merged, public
  repository state without machine-specific validation paths or unsupported
  enterprise support language.
- The `quality` workflow now supports manual dispatch, cancels superseded runs,
  has a 30-minute timeout, and reports Bandit, dependency-audit, and binary-scan
  failures as separate steps while preserving the `quality` check context.

- CI now enforces strict quality/security commands directly in workflow steps:
  Ruff format check, Ruff lint, mypy, Bandit, pip-audit, binary-file scan,
  and pytest.
- Package metadata now reflects product identity as a structured log ETL and
  reporting toolkit, with project URLs and classifiers.
- Core service collection now only accepts log-like input artifacts (`.log`,
  `.txt`, `.out`, `.json`, `.jsonl`) when reading from `--input`.
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
