# Stage 3 Stewardship Implementation Plan

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Maintain this plan in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

Deliver the Stage 3 objectives by enriching observability, reinforcing extension boundaries, and equipping future contributors (human or agentic) with automation-first tooling. After these changes, operators should be able to query health/metrics state that includes extension-provided checks, scaffold new modules with instrumentation baked in, and rely on documented patterns for evolving the toolkit. Success is demonstrated by new health-check APIs, an example extension exercising them, updated docs/playbooks, and passing quality gates.

## Progress

- [x] (2025-02-14 10:00Z) Drafted ExecPlan with Stage 3 scope and acceptance criteria.
- [x] (2025-02-14 10:40Z) Implemented health check registry module, telemetry wiring, and unit tests.
- [x] (2025-02-14 11:20Z) Extended extension context/scaffolding and added the health-monitor reference plugin.
- [x] (2025-02-14 12:00Z) Built scaffolding tooling, automation docs, and CI enhancements (diagnostics probe gate, README/guide updates, agents guardrails).
- [x] (2025-02-14 12:40Z) Finalised docs (architecture overview), changelog, release notes, and post-implementation retrospective.

## Surprises & Discoveries

- Observation: Sharing the health registry instance between `TelemetryManager`
  and `ExtensionContext` keeps diagnostics consistent and avoids double
  registration when extensions use the scaffolding helper.
  Evidence: Added `tests/test_observability_health_checks.py` and expanded
  extension runtime tests exercising registry snapshots.

## Decision Log

- Decision: Host the canonical `HealthCheckRegistry` on `TelemetryManager` and
  pass the same instance through `ExtensionContext` so metrics and diagnostics
  stay in sync.
  Rationale: Central ownership simplified gauge updates and let extensions
  reuse the registry even when telemetry is disabled (falling back to an
  in-memory instance).
  Date/Author: 2025-02-14 / agent

## Outcomes & Retrospective

- The shared `HealthCheckRegistry` now underpins telemetry snapshots, CLI
  diagnostics, and the new extension scaffolding path. Tests cover registry
  aggregation, diagnostics payloads, and scaffolded module compilation.
- Documentation, automation guardrails, and CI diagnostics hooks give future
  contributors a consistent workflow for extending observability-aware modules.
- Remaining follow-up: rerun traditional coverage tooling once environment
  restrictions lift; the trace-based fallback is documented in reports.

## Context and Orientation

The runtime toolkit lives under `zscripts/`. Key areas touched by this plan:

- `zscripts/observability/` provides telemetry primitives. `telemetry.py` coordinates logging/health servers, `health.py` hosts HTTP endpoints, and `instrumentation.py` ties metrics to operations.
- `zscripts/extensions/` hosts the plugin system, including `base.py` (context/protocol), `registry.py` (loader), and `examples/` (reference plugins). `ExtensionContext` currently lacks a structured way to publish health data.
- `scripts/` bundles developer tooling (`dev_start.py`, `agent_guard.py`, `scaffold_extension.py`). We will add automation for scaffolding modular components.
- Documentation lives in root markdown files (`docs/architecture/ARCHITECTURE_OVERVIEW.md`, `docs/guides/EXTENSION_GUIDE.md`, `docs/automation/AUTOMATION.md`, `CONTRIBUTING.md`) plus `docs/operations/` for incident response. Stage 3 output requires refreshed guidance and new AGENTS instructions for automation-aware paths.
- Tests under `tests/` cover observability (`tests/test_observability_diagnostics.py`) and extensions (`tests/test_extensions_runtime.py`). We will expand coverage for health contributions and scaffolding utilities.

The CLI entry point (`zscripts/cli.py`) constructs `ExtensionContext`, builds services via `zscripts/infrastructure`, and coordinates telemetry. Updates must respect existing interfaces and tests.

## Plan of Work

1. **Observability Health Registry**
   - Introduce `HealthCheck` and `HealthCheckRegistry` in a new module `zscripts/observability/health_checks.py`. Provide registration, removal, and snapshot aggregation APIs emitting structured status plus timing metadata.
   - Update `TelemetryManager` to own a registry instance, expose `register_health_check()` / `unregister_health_check()` helpers, and include registry results in `snapshot()` and `_status_payload()`.
   - Extend `HealthTelemetryServer` to accept a registry-driven status provider (ensuring backwards compatibility by defaulting to current behaviour). Emit new metrics (`zscripts_health_checks_status`) recording ok/degraded counts by component.
   - Adjust diagnostics collection (`zscripts/observability/diagnostics.py`) to surface health check summaries.
   - Add targeted unit tests verifying registration, aggregation, and HTTP handler behaviour.

2. **Extension Context & Example Plugin**
   - Extend `ExtensionContext` to surface the health registry, updating all instantiations (CLI, diagnostics probe, tests).
   - Update scaffolding template (`zscripts/extensions/scaffolding.py`) to demonstrate registering a custom health check with instrumentation.
   - Add a new reference extension (`zscripts/extensions/examples/plugin_health.py`) that registers a readiness check and emits metrics through the new registry.
   - Expand extension runtime tests to ensure contexts expose the registry and example plugin reports health status.

3. **Developer & Agent Tooling**
   - Create a new script `scripts/scaffold_module.py` that can scaffold either extensions or observability-aware service modules, producing stub code, tests, and agent instructions. Wire it into the CLI under `python -m zscripts.create` if applicable and document usage in README/EXTENSION_GUIDE.
   - Introduce `agents/AGENTS.md` (or extend existing automation docs) with guardrails for scaffolded modules, detailing how agents should use the new script and health registry APIs safely.
   - Update `CONTRIBUTING.md`, `docs/automation/AUTOMATION.md`, `docs/guides/EXTENSION_GUIDE.md`, and `docs/architecture/ARCHITECTURE_OVERVIEW.md` to reflect the new observability registry, scaffolding workflow, and incident response playbook. Ensure docs mention required commands and expected outputs.

4. **Continuous Improvement & Future Notes**
   - Enhance CI by updating `.github/workflows/ci.yml` to expose health-check registry results as artifacts or logs. Ensure the workflow fails on quality regressions already covered by `dev_start.py`.
   - Add TODO annotations with priority tags where long-term follow-ups remain (e.g., remote telemetry exporters), capturing effort estimates.
   - Refresh `CHANGELOG.md` and `docs/releases/RELEASE_NOTES.md` with Stage 3 highlights and upgrade guidance.
   - Produce `docs/architecture/ARCHITECTURE_OVERVIEW.md` diagrams/text updates plus a new `Future Opportunities` section summarising intelligent automation hooks. Include Evolvability Score and next-gen opportunities in the final summary per user request.

## Concrete Steps

- Edit `zscripts/observability/` modules to add the registry and telemetry changes.
- Modify CLI setup (`zscripts/cli.py`) and diagnostics utilities to wire the registry.
- Create/update extension scaffolding and example plugins.
- Author new developer tooling script under `scripts/` with executable entry point.
- Update documentation files and add new automation guidance where necessary.
- Adjust `.github/workflows/ci.yml` if additional publishing is required.
- Extend tests in `tests/` to cover new functionality and ensure coverage expectations hold.
- Run `ruff check .`, `make type`, `pytest`, and regenerate trace-based coverage artifacts if `coverage` is unavailable.

## Validation and Acceptance

- `pytest` passes with new tests covering health registry and scaffolding utilities.
- `python scripts/dev_start.py` (or `make quality`) succeeds locally.
- Invoking `python -m zscripts.cli diagnostics --include-metrics` after loading the sample health plugin shows registry contributions in the JSON payload.
- `scripts/scaffold_module.py --help` documents the new scaffolding workflows, and generating a sample module produces files with instrumentation hints.
- Updated docs clearly explain observability and scaffolding workflows.

## Idempotence and Recovery

- Health registry registration/unregistration helpers should be safe to call multiple times; tests must confirm idempotence.
- Scaffold script should refuse to overwrite existing targets unless `--force` is provided.
- CI workflow modifications must be reversible by rerunning `git checkout .github/workflows/ci.yml`.
- Documentation updates should be additive and maintainable.

## Artifacts and Notes

- Capture diagnostic command output showcasing registry contributions for inclusion in reports.
- Record CI workflow logs or artifact references verifying health summary emission.

## Interfaces and Dependencies

- New module: `zscripts/observability/health_checks.py` exporting `HealthCheck`, `HealthCheckRegistry`.
- `TelemetryManager` gains `health_checks` property plus register/unregister methods with signatures `def register_health_check(self, name: str, provider: Callable[[], Mapping[str, object]], *, kind: str = "generic") -> None`.
- Extension scaffolding template updated to call `context.telemetry.register_health_check(...)` when telemetry is available.
- `scripts/scaffold_module.py` exposes CLI via `python scripts/scaffold_module.py <type> <name>` with options for target directory and `--force`.

_Last updated: 2025-02-14 12:45Z_
