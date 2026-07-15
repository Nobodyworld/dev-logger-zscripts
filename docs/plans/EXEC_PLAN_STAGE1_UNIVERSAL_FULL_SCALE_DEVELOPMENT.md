# Stage 1 – Universal Full-Scale Development ExecPlan

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Refer to `.agent/PLANS.md` for formatting and maintenance requirements. This plan abides by those rules and remains self-contained so a newcomer can execute it from scratch.

## Purpose / Big Picture

Modernise the toolkit into a production-ready platform that unifies configuration, telemetry, reporting, and extension workflows under a consistent CLI. After completing this stage, a user can run `python cli.py report --input <log>` to obtain JSON or Markdown bundles, introspect guardrails and diagnostics, load extensions, and benefit from typed infrastructure wiring. All commands must honour configuration files, emit metrics when telemetry is enabled, and provide actionable errors.

## Progress

- [x] (2025-10-27 22:25Z) Drafted Stage 1 ExecPlan outlining scope, architecture, and acceptance.
- [x] (2025-10-27 22:23Z) Foundation: implemented metadata helpers, configuration dataclass, legacy constants, and refreshed `zscripts.__init__` exports.
- [x] (2025-10-27 22:27Z) Application & observability hardening: corrected imports/docstrings across schemas, services, observability, and extensions; validated with reporting/service tests.
- [x] (2025-10-27 22:29Z) Infrastructure wiring: refreshed adapters/sandbox/schema/redaction modules, ensured compatibility with new config, and validated via infrastructure/observability/extension tests.
- [x] (2025-10-27 22:41Z) CLI renaissance: rebuilt `cli.py` with telemetry metrics, output validation, extension routing, and comprehensive error handling; validated via full CLI suite.
- [x] (2025-10-27 22:43Z) Documentation & validation: refreshed README quickstart/config guidance, executed `pytest` across the repository (chunk `a882a6†`), and captured learnings.

## Surprises & Discoveries

- Early test runs surfaced an import cycle between `zscripts.__init__` and `zscripts.infrastructure.adapters`; resolved with lazy module exports to preserve adapter loading.
- Legacy scaffold script could not import the package when executed directly; adding a repository-root bootstrap to `scripts/scaffold_extension.py` restored compatibility.

## Decision Log

- Decision: Treat Stage 1 as an end-to-end platform revamp covering metadata, configuration, CLI orchestration, and observability rather than piecemeal fixes.
  Rationale: Tests exercise all layers (config parsing, service orchestration, telemetry, extensions, CLI). Implementing them cohesively avoids regressing cross-cutting guarantees.
  Date/Author: 2025-10-27 / Assistant

## Outcomes & Retrospective

- Stage 1 delivered a cohesive CLI and configuration experience: telemetry instrumentation, diagnostics, extension commands, and reporting now share consistent plumbing.
- Repository documentation aligns with the refreshed workflows, smoothing onboarding for contributors and operators.
- Full test suite passes (`pytest`), demonstrating stability across adapters, CLI flows, observability, and infrastructure layers.

## Context and Orientation

The repository packages a CLI-focused toolkit with layered architecture:

- `cli.py` is the user entry point executed via `python cli.py` (tests spawn subprocesses). It must parse global options (`--config`, `--set`, telemetry toggles) and subcommands (`collect`, `parse`, `guardrails`, `report`, `extensions`, `diagnostics`).
- `zscripts/__init__.py` should expose helpers (configuration loader, version metadata) for both CLI and library consumers. `zscripts/config.py` is expected to define a typed configuration dataclass and cloning helpers; `zscripts/configuration.py` loads TOML/JSON files and merges CLI overrides.
- Domain/application layers live under `zscripts/domain` and `zscripts/application`. `ToolkitService` orchestrates adapter registry, sandbox runners, redaction, reporting, and telemetry instrumentation.
- Infrastructure adapters inside `zscripts/infrastructure/` wrap legacy modules (`adapters`, `scripts.sandbox`, `scripts.redaction`) to satisfy domain protocols.
- Observability utilities (`zscripts/observability/*`) provide telemetry managers, metrics registries, diagnostics snapshots, instrumentation helpers, and structured logging.
- Extension system resides in `zscripts/extensions/`, supporting discovery, manifests, hook registries, and scaffolding. Tests expect example extension `zscripts.extensions.examples.plugin_echo` to be loadable.
- Schemas under `zscripts/schemas` offer dataclasses for normalized logs and JSON schema loading. Tests validate `ReportBundle` markdown/JSON formatting.

Current issues include incomplete imports, missing metadata/config helpers, outdated CLI implementation, and inconsistent doc coverage. Bringing modules in sync with tests requires implementing these contracts end-to-end.

## Plan of Work

1. **Foundation layer**
   - Design `zscripts/metadata.py` wrapping `importlib.metadata` (exposing `version`, `PackageNotFoundError`). Update `zscripts/__init__.py` to export `get_version()`, `get_default_config()`, and surface `ToolkitConfig`, `load_toolkit_config`, `ConfigurationError`.
   - Rebuild `zscripts/config.py` around a `@dataclass(slots=True)` `ToolkitConfig` with sensible defaults (allowed paths, timeout, adapters, telemetry defaults, reporting preferences). Provide `DEFAULT_CONFIG` mapping and `clone_config()` returning deep copies. Document fields inline.
   - Ensure `get_default_config()` returns a fresh `ToolkitConfig` each call while caching the base template to avoid repeated disk access.

2. **Configuration parsing & schema alignment**
   - Complete `zscripts/configuration.py` imports (`os`, `ToolkitConfig`, etc.) and docstrings. Verify coercion helpers cover all keys (including `report_fail_on`). Add tests if necessary to capture edge cases not already in suite.
   - Update `schemas/normalized.py` to import dataclasses/time utilities correctly and ensure `NormalizedLog.to_dict()` uses `asdict` from `dataclasses`.

3. **Application & observability hardening**
   - Audit `zscripts/application` modules: add missing imports (e.g., `json`, `typing` protocols) in `report_formatters.py`, `io_utils.py`, `services.py`. Ensure instrumentation wrappers use `typing` types.
   - Confirm `zscripts/observability` modules import needed typing utilities (`Mapping`, `Sequence`, `Iterable`, etc.) and expose comprehensive docstrings. Guarantee metrics registry renders Prometheus text correctly.
   - Ensure `zscripts/observability/telemetry.py` uses new metadata helper and gracefully handles missing telemetry dependencies.

4. **Infrastructure wiring**
   - Fix `zscripts/infrastructure` modules to rely on new config dataclass: adjust imports for `Path`, `Callable`, etc. Validate adapter registry caches wrappers, sandbox builder returns protocol, schema validator handles missing `jsonschema`, and redactor wraps `scripts.redaction.Redactor` with typed sequences.
   - Provide top-level factory `build_toolkit_service()` returning `ToolkitService` configured from `ToolkitConfig`. Ensure docstring clarifies dependencies and telemetry usage.

5. **CLI renaissance**
   - Rewrite `cli.py` with argparse-based architecture supporting:
     * Global options: `--config PATH`, `--set KEY=VALUE` (multiple), `--adapter`, `--enable-telemetry/--no-enable-telemetry`, `--log-format`, `--log-level`, `--examples`, etc., aligning with tests.
     * Subcommands: `collect`, `parse`, `report`, `guardrails`, `extensions` (list + `--output-format json`, `scaffold` subcommand, dynamic extension commands), `diagnostics` (optional `--output`, `--format text|json`, `--include-metrics`).
     * `report` command using `ToolkitService.generate_report()`, selecting formatter via `get_report_formatter`, applying `--format`, `--output`, `--redact/--no-redact`, and `--fail-on` (with `_should_fail` helper evaluating severity thresholds). Validate output paths using `prepare_output_path`/`atomic_write_text` and exit codes per tests.
     * `parse` command printing normalized log JSON; `guardrails` command printing sandbox snapshot; `collect` command retrieving logs (with STDIN fallback) and writing to stdout; `extensions` command listing loaded extensions (text + JSON), executing extension CLI handlers, and scaffolding new extensions to disk.
     * Telemetry integration: instantiate `TelemetryManager` when enabled/configured, emit CLI invocation metrics (`zscripts_cli_invocations_total`, `zscripts_cli_duration_seconds` histogram), ensure manager stopped at exit, handle failure metrics and propagate errors.
   - Ensure CLI uses `load_toolkit_config()` to merge defaults, config files, and `--set` overrides; apply `--adapter` CLI override for operations requiring adapter selection.
   - Provide helpful error messaging and exit codes (0 success, 1 fail threshold, 2 usage/path errors). Tests expect directory output error to produce code 2 with descriptive stderr.

6. **Diagnostics & extensions**
   - Guarantee extension modules (base, hooks, registry, manifest, scaffolding, examples) compile with required imports. `scaffold_extension()` should validate module names, avoid overwriting existing files, and embed instrumentation usage in template.
   - `collect_runtime_diagnostics()` should produce `DiagnosticsSnapshot` with metrics optional; ensure text format renderer (likely in CLI) summarises payload.

7. **Documentation & validation**
   - Update `README.md` and add/refresh docs (e.g., `docs/reporting.md`, `docs/configuration.md`) to reflect new CLI commands, telemetry, and extension workflows. Document configuration keys, report formats, telemetry toggles, and diagnostics usage. Include TODO markers for future enhancements if discovered.
   - Run `python -m pytest` and linting (`ruff check` if configured). Capture command output chunk IDs for reporting. Ensure tests pass; address failures iteratively.
   - Summarise outcomes in ExecPlan, including surprises/decisions discovered during implementation.

## Concrete Steps

1. Implement foundation modules and exports:
   - Edit `zscripts/metadata.py`, `zscripts/__init__.py`, `zscripts/config.py`.
   - Run targeted unit tests (e.g., `pytest tests/test_package.py tests/test_configuration.py`).

2. Fix schemas and application imports:
   - Update `zscripts/schemas/normalized.py`, `zscripts/application/*.py`, `zscripts/observability/*.py` modules.
   - Execute `pytest tests/test_reporting.py tests/test_services.py` to verify coverage.

3. Harden infrastructure wiring:
   - Update `zscripts/infrastructure/*.py` and ensure service factory integrates new config.
   - Run `pytest tests/test_infrastructure.py tests/test_observability.py`.

4. Rebuild CLI and diagnostics workflows:
   - Overhaul `cli.py`, adjust `zscripts/extensions` utilities as needed, ensure telemetry metrics recorded.
   - Execute full CLI suite via `pytest tests/test_cli.py tests/test_extensions_runtime.py tests/test_observability_diagnostics.py`.

5. Final validation and docs:
   - Refresh README/docs, confirm formatting.
   - Run `pytest` across repository, optionally linting.
   - Update ExecPlan sections (`Progress`, `Surprises`, `Decision Log`, `Outcomes`).

## Validation and Acceptance

- `python -m pytest` must pass without errors.
- CLI manual smoke tests: `python cli.py report --input examples/python/sample.log --format markdown`, `python cli.py guardrails`, `python cli.py diagnostics --format text` should succeed.
- Telemetry-enabled run (`python cli.py --enable-telemetry guardrails`) should start/stop server cleanly and expose metrics counters.
- Documentation updates should describe new commands and configuration keys.

## Idempotence and Recovery

- Configuration helpers avoid mutating shared state; rerunning CLI commands with the same config should be safe.
- `scaffold_extension()` refuses to overwrite existing files, preventing destructive reruns.
- Telemetry manager `.stop()` is invoked in `finally` blocks to avoid lingering threads even after failures.
- Output writers use atomic replace semantics; partial writes clean up temp files.

## Artifacts and Notes

- Capture key pytest/ruff transcripts in ExecPlan once available.
- Record any notable diffs or command outputs that clarify tricky behaviors (e.g., telemetry metrics snippet, Markdown report excerpt).

## Interfaces and Dependencies

- `zscripts.metadata.get_version()` -> `str`
- `zscripts.config.ToolkitConfig`: dataclass fields include `allowed_paths: tuple[Path, ...]`, `timeout_seconds: int`, `dangerous_mode: bool`, `default_adapter: str`, `redact_patterns: tuple[str, ...]`, `examples_path: Path`, `telemetry_enabled: bool`, `telemetry_host: str`, `telemetry_port: int`, `log_level: str`, `log_format: str`, `extensions: tuple[str, ...]`, `report_format: str`, `report_redact: bool`, `report_fail_on: str`.
- `zscripts.config.clone_config(config: ToolkitConfig) -> ToolkitConfig`
- `zscripts.application.services.ToolkitService` exposes `collect_logs`, `parse_logs`, `summarize_logs`, `explain_logs`, `generate_report`, `guardrails_snapshot`, `list_examples`, `redact_text`.
- `zscripts.application.report_formatters.get_report_formatter(name: str) -> Callable[[ReportBundle], str]`.
- CLI metrics: `MetricsRegistry.counter("zscripts_cli_invocations_total", ...)`, histogram `MetricsRegistry.histogram("zscripts_cli_duration_seconds", ...)`.
- Extension scaffolding template should define a subclass of `ToolkitExtension` with `get_extension()` factory.
