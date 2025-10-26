# Stage 3 Evolution & Automation ExecPlan

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Refer to `.agent/PLANS.md` for required structure and maintenance rules; this plan follows them and must remain compliant.

## Purpose / Big Picture

Stage 3 evolves the hardened toolkit into a self-sustaining platform. After finishing this plan, maintainers can: (1) interrogate runtime diagnostics through a dedicated CLI command and library helpers, (2) orchestrate extensions through a managed hook registry that encourages modular growth, and (3) rely on refreshed contributor docs and automation playbooks describing agent-friendly workflows. Acceptance is demonstrated by running `python cli.py diagnostics --include-metrics` to obtain a structured snapshot, exercising the reference hook-enabled extension, and executing `python scripts/diagnostics_probe.py --output reports/diagnostics.json` to capture telemetry artifacts alongside the existing quality gate.

## Progress

- [x] (2025-02-15 16:05Z) Baseline repository analysis; confirmed existing telemetry manager, extension loader, and automation scripts.
- [x] (2025-02-15 16:45Z) Defined observability scope: new diagnostics module, CLI command, telemetry snapshot API, and automated probe script scaffolding.
- [x] (2025-02-15 17:30Z) Implemented extension hook registry, manager wrapper, and updated loader plus sample extension to exercise hooks.
- [x] (2025-02-15 18:20Z) Added diagnostics collection helpers, CLI command, probe script, and integration tests covering metrics snapshots and hook emissions.
- [x] (2025-02-15 19:15Z) Documented extension hooks, diagnostics workflows, automation guidance, and architecture updates; refreshed changelog and release notes.
- [x] (2025-02-15 19:40Z) Completed final validation (`ruff`, `mypy`, `pytest`, diagnostics probe smoke run) and captured retrospective notes.

## Surprises & Discoveries

- Observation: Extension lifecycle lacked a central hook emitter, forcing ad-hoc integration; introducing a registry requires adapting CLI expectations around loaded extensions.
  Evidence: CLI `_prepare_and_execute` assumed a list return from `load_extensions`, so adding an `ExtensionManager` wrapper must preserve sequence semantics while surfacing hook metadata (`tests/test_extensions_runtime.py`).
- Observation: Diagnostics snapshots needed a public telemetry API to avoid duplicating private health logic.
  Evidence: `tests/test_observability_diagnostics.py` exercises `TelemetryManager.snapshot()` to verify metrics inclusion without touching internal server fields.

## Decision Log

- Decision: Return an `ExtensionManager` that implements sequence protocols and surfaces a hook registry rather than augmenting raw lists in-place.
  Rationale: Maintains backward compatibility for existing loops while providing structured extension orchestration for new automation features.
  Date/Author: 2025-02-15 / Assistant
- Decision: Expose `TelemetryManager.snapshot()` and `observability.diagnostics.collect_runtime_diagnostics()` to ensure both CLI and automation scripts rely on a single source of truth for health payloads.
  Rationale: Avoids duplicating private health server wiring while standardising incident-response tooling for humans and agents.
  Date/Author: 2025-02-15 / Assistant
- Decision: Default diagnostics probe failures to `--fail-on-status degraded` so automation matches existing incident thresholds while permitting stricter policies.
  Rationale: Keeps backwards compatibility for environments that only alert on degraded states yet allows opting into earlier failure signals via CLI/automation flags.
  Date/Author: 2025-02-15 / Assistant

## Outcomes & Retrospective

Diagnostics snapshots now combine telemetry payloads, extension manifests, and hook summaries via a shared helper consumed by the CLI and automation probe script. The hook registry keeps extension lifecycles observable without breaking compatibility, and documentation across README, architecture, automation, operations, changelog, and release notes reflects the new workflows. Targeted unit tests cover diagnostics payloads, CLI formatting, hook summaries, and the reference extension. Quality gates (`ruff`, `mypy`, `pytest`) and the diagnostics probe smoke test now pass cleanly, confirming readiness for stewardship hand-off.

## Context and Orientation

The repository hosts a Python CLI toolkit under `zscripts/` that processes build logs. Observability utilities live in `zscripts/observability/`, with `TelemetryManager` controlling logging, metrics, and the HTTP health server. Extensions load from modules listed in configuration via `zscripts/extensions/registry.py`, while CLI command wiring resides in `zscripts/cli.py`. Tests live in `tests/`, and automation helpers (bootstrap, guard, quality gate) reside under `scripts/`. Documentation and contributor guides sit in the project root (`README.md`, `CONTRIBUTING.md`) and `docs/`. Stage 3 work introduces a diagnostics surface and structured extension hooks without breaking the CLI contract.

## Plan of Work

Milestone 1 (Hook Registry Infrastructure): Update `zscripts/extensions/base.py` to carry a new `hook_registry` attribute on `ExtensionContext`. Implement `ExtensionHookRegistry` in a new module (`zscripts/extensions/hooks.py`) that records callbacks with instrumentation wrappers and exposes `emit()` for runtime triggers. Refactor `zscripts/extensions/registry.py` so `load_extensions()` instantiates an `ExtensionManager` that wraps the loaded list, exposes manifests, hook registry access, and emits a gauge metric. Ensure the manager implements sequence semantics (`__iter__`, `__len__`, `__getitem__`) to preserve CLI compatibility. Expand tests in `tests/test_extensions_runtime.py` to cover registry summary, hook registration/emit, and manifest lookups. Create a new reference extension (`zscripts/extensions/examples/plugin_metrics.py`) demonstrating hook usage (e.g., registering a `service_ready` hook to log manifest summaries) and extend sample tests accordingly.

Milestone 2 (Diagnostics Collection & CLI Command): Introduce `zscripts/observability/diagnostics.py` providing a `collect_runtime_diagnostics()` helper that consumes `TelemetryManager`, optional instrumentation, and an `ExtensionManager` (or sequence) to produce a JSON-serialisable snapshot with timestamps, health URLs, extension counts, and optional Prometheus text when requested. Extend `TelemetryManager` with a public `snapshot()` method returning the health payload (ensuring existing functionality remains). Wire a new `diagnostics` subcommand into `zscripts/cli.py` (with `--include-metrics`, `--format`, and `--output` options). The handler should attach runtime context, call the diagnostics helper, emit instrumentation, and write JSON/text payloads using `_write_output`. Add tests in `tests/test_cli.py` verifying CLI diagnostics output, metrics inclusion, and error handling when output path fails. Include targeted unit tests for the diagnostics module.

Milestone 3 (Automation & Documentation): Add a script `scripts/diagnostics_probe.py` invoking the diagnostics helper to write snapshots for agents (supporting JSON output, optional metrics capture, and exit codes on degraded status). Document usage in `AUTOMATION.md`, `README.md`, `EXTENSION_GUIDE.md`, and `docs/operations.md` plus update `ARCHITECTURE_OVERVIEW.md` to include the new diagnostics flow and hook registry. Refresh `CHANGELOG.md` and `RELEASE_NOTES.md` to summarise the enhancements. Ensure TODOs include priority tags where new follow-up work is identified.

## Concrete Steps

1. Implement hook registry infrastructure (Milestone 1) with tests.
2. Implement diagnostics helper and CLI command (Milestone 2) with tests.
3. Add automation script and documentation updates (Milestone 3); update changelog and release notes.
4. Run `ruff check .`, `mypy`, `pytest`, and `python scripts/diagnostics_probe.py --output reports/diagnostics.json` to validate end-to-end.

## Validation and Acceptance

- `pytest` passes with new diagnostics and extension tests.
- `python cli.py diagnostics --include-metrics` returns a JSON payload containing `status`, `extensions`, and `metrics` keys.
- `python scripts/diagnostics_probe.py --output reports/diagnostics.json` exits 0 and writes the snapshot.
- Documentation reflects the new workflows.

## Idempotence and Recovery

The hook registry and diagnostics helpers are additive. Re-running the CLI scaffold or diagnostics script overwrites idempotent artifacts (`reports/diagnostics.json`). Hook registrations guard against duplicate callbacks via instrumentation logging. No destructive operations occur.

## Artifacts and Notes

- Hook registry interface definition (`zscripts/extensions/hooks.py`).
- Diagnostics snapshot structure (`zscripts/observability/diagnostics.py`).
- CLI diagnostics command usage examples (added to README and docs).

## Interfaces and Dependencies

- `zscripts/extensions/hooks.ExtensionHookRegistry.register(hook: str, callback: Callable[..., None], *, extension: str) -> None`
- `zscripts/extensions/hooks.ExtensionHookRegistry.emit(hook: str, **kwargs) -> list[object]`
- `zscripts/extensions/registry.ExtensionManager` implements `Sequence[ToolkitExtensionProtocol]`, `manifest_for(name: str)`, `hook_summary()`, and `emit(hook: str, **kwargs)`.
- `zscripts/observability/diagnostics.collect_runtime_diagnostics(*, telemetry: TelemetryManager, instrumentation: InstrumentationManager | None = None, extensions: Sequence[ToolkitExtensionProtocol] | ExtensionManager | None = None, include_metrics: bool = False) -> dict[str, object]`
- `TelemetryManager.snapshot(include_metrics: bool = False) -> dict[str, object]`
