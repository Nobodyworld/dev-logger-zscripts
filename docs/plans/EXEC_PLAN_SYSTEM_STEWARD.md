# Observability, Extension Framework, and Automation Stewardship

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan is maintained according to `.agent/PLANS.md` and is self-contained for contributors without prior repository context.

## Purpose / Big Picture

The goal is to evolve the toolkit from a hardened build into an extensible, observable platform. After completing this plan, contributors can:

1. Enable structured logging, request tracing, and Prometheus-compatible metrics while the CLI runs.
2. Check health and metrics over HTTP using a lightweight server and consume a coherent incident guide.
3. Build and register new adapters or automation hooks through a documented extension system and starter scaffolds.
4. Follow upgraded developer tooling (scripts, CI gates, contributor docs) that keep lint/type/test/security/coverage standards enforced automatically.
5. Understand architecture and future-proofing guidance captured in dedicated documentation, including migration notes and automation policies for agents.

## Progress

- [x] (2024-06-01 00:00Z) Draft plan approved and baseline repository reviewed.
- [x] (2024-06-02 00:00Z) Observability layer implemented (metrics registry, tracing spans, structured logger, CLI switches, HTTP health server) with tests.
- [x] (2024-06-02 00:00Z) Modular extension framework delivered (extension contracts, loader, reference plugin, CLI exposure) plus documentation.
- [x] (2024-06-03 00:00Z) Developer enablement assets added (scripts, templates, CONTRIBUTING update, agent guidelines) with automated gates.
- [x] (2024-06-03 00:00Z) Future-proofing documentation (architecture overview, incident response, roadmap, migration notes) finalized with release artifacts.

## Surprises & Discoveries

- Observation: `coverage json` exposes total coverage, allowing the quality gate
  to enforce thresholds without third-party tooling.
  Evidence: `scripts/dev_start.py` parses the generated `artifacts/coverage/coverage.json`.
- Observation: Extensions need to load before CLI parsing; a two-phase argparse
  flow preserves backwards compatibility.
  Evidence: Updated `cli.py` performs `parse_known_args` before building subcommands.

- Decision: Telemetry spans should wrap `ToolkitService` methods instead of
  decorators to avoid breaking tests and to keep instrumentation centralised.
  Rationale: Minimises churn while capturing all CLI operations.
  Date/Author: 2024-06-02 / steward agent.
- Decision: Extensions expose `get_extension()` factories rather than relying on
  implicit class discovery.
  Rationale: Keeps module contracts explicit and easy to document.
  Date/Author: 2024-06-02 / steward agent.
- Decision: Quality gate runs via `scripts/dev_start.py` with optional skip envs.
  Rationale: Encourages one-command checks while allowing local iteration.
  Date/Author: 2024-06-03 / steward agent.

## Outcomes & Retrospective

Observability, extension loading, developer tooling, and forward-looking
documentation landed as planned. Telemetry defaults remain opt-in to avoid
surprising existing workflows, while new CLI flags and docs guide adoption.

## Context and Orientation

The CLI entry point lives at `zscripts/cli.py` and constructs a `ToolkitService` from `zscripts.application.services`. Infrastructure factories live in `zscripts/infrastructure`, wiring adapters, schema validators, examples, and redactors. Configuration defaults are defined in `zscripts/config.py` and loaded through `zscripts/configuration.py`. Tests reside under `tests/`. Documentation is anchored by `README.md` with deeper guides in `docs/`.

Currently, observability is limited to standard output messaging; there is no metrics or tracing subsystem. Extension points are implicit via the adapter registry in `zscripts.infrastructure.adapters.AdapterRegistry` but there is no formal plugin API. Developer ergonomics rely on manual command execution despite a `Makefile`. Stage 3 requires bridging these gaps while keeping mypy strictness and existing tests intact.

## Plan of Work

1. **Observability foundation**
   Introduce a `zscripts/observability` package containing:
   - `logging.py` that configures structured JSON or key-value logging with correlation IDs and log level control.
   - `metrics.py` implementing a registry of counters and histograms that exports in Prometheus text format.
   - `tracing.py` providing a span context manager that records operation durations into the metrics registry and attaches IDs to log records.
   - `health.py` exposing a minimal HTTP server (`HealthTelemetryServer`) that serves `/healthz` (JSON OK payload plus build metadata) and `/metrics` (Prometheus exposition). The server should run in a background thread started via a CLI flag.
   Extend `ToolkitService` to accept an optional telemetry hook that wraps public operations (`collect_logs`, `parse_logs`, `summarize_logs`, `explain_logs`, `guardrails_snapshot`, `redact_text`, `list_examples`). Each wrapper should record spans, counters, and log structured events. Update `build_toolkit_service` to construct a telemetry hook (no-op by default) and propagate CLI options for enabling the HTTP endpoint and verbose logging. Update CLI argument parsing to accept `--enable-telemetry` (boolean) and `--telemetry-port` (int, default 9464) plus `--log-format` and `--log-level`. Provide integration tests covering metrics export, tracing logs, and health checks using pytest’s HTTP client utilities with the server running on an ephemeral port.

2. **Modular extension framework**
   Create a new package `zscripts/extensions` with:
   - `base.py` defining `ToolkitExtensionProtocol` (methods to register adapters, CLI commands, or telemetry handlers) and `ExtensionContext` exposing registries and configuration.
   - `registry.py` to load extensions listed in configuration (e.g., `config.extensions` list). Implement safe dynamic imports with error handling and telemetry logging. The registry should expose `load_extensions` returning instantiated extensions and allow each to register with the `ToolkitService` or CLI.
   - Provide a reference extension `zscripts/extensions/examples/plugin_echo.py` that registers a mock adapter or CLI helper (e.g., adds an `echo` command for demonstration) to show how integration works.
   Update configuration dataclass to include an `extensions` tuple of dotted paths. Modify `load_toolkit_config` parsing to coerce comma-separated overrides into tuples. Extend CLI to expose a new subcommand `extensions` to list loaded extensions and their capabilities. Add tests verifying extension loading (successful, missing module, initialization failure) and the reference plugin behavior.

3. **Developer and agent enablement**
   - Add `scripts/dev_start.py` that orchestrates a full quality gate: run lint, mypy, tests, security, coverage with thresholds. Include environment variable overrides for skipping steps. Use subprocess calls and exit codes. Provide `scripts/scaffold_extension.py` generating a new extension module from a template under `extensions/`. Ensure the script validates names and injects instrumentation hooks.
   - Update `CONTRIBUTING.md` with branching, commit, and quality gate guidelines referencing the new scripts and telemetry flags. Add `docs/automation/AUTOMATION.md` at repo root describing how agents should run commands safely, where to find logs, and how to interact with telemetry.
   - Place `AGENTS.md` in key directories (e.g., `extensions/`) describing conventions for new modules.

4. **Continuous improvement loop**
   - Create `.github/dependabot.yml` configured for pip and GitHub Actions if present. Add GitHub workflow `ci.yml` orchestrating lint → type → test → coverage → security using the new script. Configure coverage fail threshold (e.g., 85%) by parsing `coverage xml` or `coverage report` output.
   - Extend `Makefile` with targets `coverage` (using `coverage run -m pytest`), `quality` (invoking `python scripts/dev_start.py`). Ensure `scripts/dev_start.py` respects thresholds and writes a JSON summary to `artifacts/quality/quality_gate.json`.
   - Tag TODO comments with `TODO(Px, owner, eta):` format and ensure new TODOs follow it. Run `rg` to ensure there are no old-style TODOs in touched files.

5. **Future-proofing & documentation**
   - Author `docs/architecture/ARCHITECTURE_OVERVIEW.md` summarizing package layout, component interactions, observability pipeline, and extension contracts with ASCII diagrams.
   - Add `docs/guides/EXTENSION_GUIDE.md` demonstrating step-by-step creation of a new extension using the scaffold script and explaining lifecycle hooks.
   - Document incident response and recovery in `docs/operations/INCIDENT_RESPONSE.md`, referencing telemetry endpoints and log levels.
   - Expand `docs/releases/RELEASE_NOTES.md` and `CHANGELOG.md` with new features plus upgrade steps (e.g., new config keys, CLI flags). Provide `docs/future_roadmap.md` covering scalability, containerization, multi-tenant considerations, and automation opportunities. Capture migration path suggestions for major versions (e.g., splitting adapters, moving to microservices) and note AI safety policies for agent integrations.

## Concrete Steps

1. Review existing observability mentions and ensure no conflicting modules. Implement new `zscripts/observability` package and integrate CLI options, updating tests accordingly. Validate telemetry exports using pytest and ensure instrumentation is optional by default.
2. Extend configuration dataclasses and loader for extensions. Implement extension registry and reference plugin, integrate with CLI service creation, and add targeted tests for loading and CLI listing.
3. Build developer tooling scripts, update `Makefile`, CONTRIBUTING, and create automation docs. Ensure the new scripts are covered by tests where feasible (unit tests for scaffolding helper, CLI invocation tests using `pytest` subprocess or `capsys`).
4. Establish CI workflow file and dependabot config. Implement coverage enforcement and JSON reporting in `scripts/dev_start.py`. Update documentation to point to the new automation.
5. Write architecture overview, extension guide, incident response doc, automation instructions, future roadmap notes, and update release artifacts. Ensure doc references to telemetry flags and extension config are accurate.
6. Run `ruff`, `mypy`, `pytest`, coverage command, and the new dev script to confirm quality gate success. Capture coverage summary artifact path.

## Validation and Acceptance

- Running `python scripts/dev_start.py` from the repository root should execute lint, mypy, pytest, security, and coverage checks, exiting 0 and generating `artifacts/quality/quality_gate.json` summarizing the run with coverage ≥85%.
- Starting `python cli.py --enable-telemetry --telemetry-port 9100 guardrails` should spin up the background health server. An HTTP GET to `http://localhost:9100/healthz` must return `{"status": "ok", "version": "..."}` and `/metrics` should include counters like `zscripts_requests_total` and histograms for operation latency.
- Invoking `python cli.py extensions` after adding the sample extension in configuration should list the extension name and registered hooks.
- `python scripts/scaffold_extension.py my_custom_plugin` should create `extensions/my_custom_plugin.py` with template code and tests verifying behavior.
- Documentation updates must describe telemetry usage, extension creation, CI scripts, and future-proofing guidance with cross-links from README.

## Idempotence and Recovery

Telemetry configuration defaults to disabled; enabling flags repeatedly should not spawn duplicate servers thanks to guard logic. The quality gate script should cleanly exit even if some commands fail and reruns should overwrite the JSON report. Scaffold script should refuse to overwrite existing files unless `--force` is provided (if implemented) or exit with a clear message. CI workflow uses cached dependencies; reruns are safe.

## Artifacts and Notes

- Capture HTTP responses from the health server as indented transcripts for documentation.
- Include metrics sample output snippet and CLI screenshot if feasible.
- Store coverage JSON and trace output under `artifacts/coverage/` for reference.

## Interfaces and Dependencies

- `zscripts/observability/logging.py`: expose `configure_logging(level: str, fmt: str, correlation_id: str | None = None) -> logging.Logger` and helper `get_logger(name: str) -> logging.Logger`.
- `zscripts/observability/metrics.py`: provide `MetricsRegistry` with `counter(name, description).inc(labels)`, `histogram(name, description).observe(value, labels)`, `collect_prometheus() -> str`, plus a singleton `default_registry`.
- `zscripts/observability/tracing.py`: define `Span` dataclass and context manager `start_span(operation: str, attributes: dict[str, str] | None = None)` that records start/end, updates metrics, and logs with correlation IDs.
- `zscripts/observability/health.py`: implement `HealthTelemetryServer` with `start(port: int) -> None`, `stop() -> None`, `is_running() -> bool`.
- `zscripts/extensions/base.py`: define `ToolkitExtensionProtocol` with `name`, `description`, and hooks like `register_service(service: ToolkitService, context: ExtensionContext) -> None` and `register_cli(parser: argparse.ArgumentParser, context: ExtensionContext) -> None`.
- `zscripts/extensions/registry.py`: implement `load_extensions(paths: Sequence[str], context: ExtensionContext) -> list[ToolkitExtensionProtocol]` and ensure telemetry logs success/failure.
- Extend `ToolkitConfig` with `extensions: tuple[str, ...]` defaulting to empty.
- Provide tests under `tests/test_observability.py`, `tests/test_extensions.py`, `tests/test_dev_scripts.py`.
