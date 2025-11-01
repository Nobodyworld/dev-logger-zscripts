# Stage 3 Stewardship Refresh ExecPlan

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Refer to `.agent/PLANS.md` for mandatory structure and maintenance expectations. This document follows those rules and remains self-contained.

## Purpose / Big Picture

We will elevate Stage 3 deliverables by deepening observability, codifying extension metadata, and equipping maintainers with operational tooling. After this work, maintainers can track HTTP health traffic via metrics, introspect loaded extensions (and scaffold new ones) with manifest data, and run a scripted health probe for automation. Documentation updates will guide contributors and agents through the new workflows, while changelog and release notes capture the release story.

## Progress

- [x] (2025-02-15 10:05Z) Authored refresh ExecPlan defining observability, extension, and tooling scope.
- [x] (2025-02-15 11:00Z) Implement observability updates (service instrumentation + health request metrics) with tests.
- [x] (2025-02-15 11:15Z) Add extension manifest registry, CLI list enhancements, and scaffolding template updates with coverage.
- [x] (2025-02-15 11:40Z) Ship ops status script, documentation refresh (architecture, automation, operations, incident response, extension guide), and update changelog/release notes.
- [x] (2025-10-26 09:55Z) Run full quality gate (lint/type/tests/coverage), update reports artifacts, and document outcomes.

## Surprises & Discoveries

- Observation: Health endpoint degradation returns HTTP 503, causing
  `urllib.request.urlopen` to raise `HTTPError` even though a JSON payload is
  available.
  Evidence: Pytest initially surfaced exit code 2 for the degraded probe in
  `tests/test_dev_scripts.py::test_ops_status_flags_degraded_status` before
  adding explicit `HTTPError` handling.
- Observation: CLI text output now includes extension versions, so table-based
  assertions must match the enriched format.
  Evidence: Initial regression failure in
  `tests/test_cli.py::test_cli_extensions_command_lists_loaded` after the
  manifest metadata landed.

## Decision Log

- Decision: Store manifests keyed by extension name and expose JSON-formatted
  listings through `python cli.py extensions --output-format json`.
  Rationale: Automation agents need a stable lookup to query capabilities and
  versions without re-importing modules.
  Date/Author: 2025-02-15 / Assistant
- Decision: Treat HTTP 5xx responses from the health endpoint as degraded
  statuses rather than fatal errors inside `scripts/ops_status.py`.
  Rationale: The health server returns structured JSON with `status` fields even
  when returning 503, so agents benefit from a non-zero exit that still emits
  telemetry rather than a hard failure.
  Date/Author: 2025-02-15 / Assistant

## Outcomes & Retrospective

- Service calls now emit `component="service"` operation metrics, health probes
  report per-endpoint traffic, and automation can query manifests or run
  `scripts/ops_status.py` for readiness. Documentation mirrors the new
  capabilities and the quality gate reports 88.5% coverage with lint/type/tests
  passing.
- Executed `python scripts/dev_start.py` (coverage 88.5%) and
  `python cli.py extensions --output-format json` (currently `[]` with default
  configuration) and captured transcripts for traceability.

## Context and Orientation

The toolkit exposes telemetry facilities under `zscripts/observability/`, CLI orchestration in `zscripts/cli.py`, and application services in `zscripts/application/services.py`. Extension loading and scaffolding live in `zscripts/extensions/` alongside examples. Tests covering telemetry reside in `tests/test_observability.py`, with CLI regression tests in `tests/test_cli.py`. Quality gates are orchestrated via `scripts/dev_start.py`, producing artifacts under `artifacts/quality/`. Documentation spanning architecture, automation, and operations lives in `docs/architecture/ARCHITECTURE_OVERVIEW.md`, `docs/automation/AUTOMATION.md`, `docs/operations.md`, and `docs/guides/EXTENSION_GUIDE.md`.

Currently, service methods instrument spans but do not emit metrics, and the health server lacks per-endpoint telemetry. Extensions expose limited metadata, constraining automation. There is no dedicated script to query health endpoints for agents. Documentation predates these additions, so it must be refreshed to match the new capabilities.

## Plan of Work

1. **Observability Enhancements**: Update `ToolkitService` to use `InstrumentationManager` operations (creating one when telemetry is provided) so service calls emit metrics and traces. Extend `HealthTelemetryServer` to track HTTP request counts, durations, and inflight gauges labelled by endpoint and status. Add targeted tests in `tests/test_services.py` and `tests/test_observability.py` verifying new metrics.
2. **Extension Manifest Layer**: Introduce `ExtensionManifest` (new module) and add a manifest registry to `ExtensionContext`. Update `load_extensions` to populate manifests, enhance `extensions` CLI output with JSON formatting based on manifest data, and refresh scaffolding/template plus example extension to declare capabilities. Expand CLI and extension tests accordingly.
3. **Developer Tooling & Docs**: Implement `scripts/ops_status.py` to fetch health endpoints, persist optional JSON summaries, and exit non-zero on degraded status. Document usage across `docs/automation/AUTOMATION.md`, `docs/operations.md`, `docs/operations/INCIDENT_RESPONSE.md`, `docs/guides/EXTENSION_GUIDE.md`, `docs/architecture/ARCHITECTURE_OVERVIEW.md`, and `README.md` as needed. Capture future-proofing notes in `docs/future_roadmap.md` and update `CONTRIBUTING.md` with the telemetry/tooling workflow. Refresh `CHANGELOG.md` and `docs/releases/RELEASE_NOTES.md`.
4. **Validation & Artifacts**: Run `python scripts/dev_start.py` to regenerate quality gate/coverage artifacts, followed by `pytest` (if needed for isolated debugging). Update the ExecPlan sections (`Progress`, `Surprises`, `Decision Log`, `Outcomes`) with findings and final status.

## Concrete Steps

- Modify `zscripts/application/services.py` and `zscripts/infrastructure/__init__.py` to wire instrumentation.
- Update `zscripts/observability/health.py` to emit request metrics and logging for each endpoint.
- Add assertions in `tests/test_services.py` and `tests/test_observability.py` for the new instrumentation outputs.
- Create `zscripts/extensions/manifest.py`, update `zscripts/extensions/base.py`, `zscripts/extensions/__init__.py`, and `zscripts/extensions/registry.py` to manage manifests.
- Enhance CLI handling in `zscripts/cli.py` to surface manifest data with a new `--format` option for `extensions` list output. Add coverage in `tests/test_cli.py`.
- Refresh scaffolding (`zscripts/extensions/scaffolding.py`, `scripts/scaffold_extension.py` template strings) and the example extension to include capabilities metadata.
- Implement `scripts/ops_status.py` with tests in `tests/test_dev_scripts.py`.
- Revise documentation files and release artifacts noted above.
- Execute `python scripts/dev_start.py` to regenerate artifacts, and commit the updated plan reflecting completed milestones.

## Validation and Acceptance

- `python scripts/dev_start.py` succeeds, generating updated `artifacts/quality/quality_gate.json` and `artifacts/coverage/coverage.json` showing ≥85% coverage.
- `pytest` (implicit in the quality gate) covers new tests verifying service metrics, health request telemetry, CLI manifest output, scaffolding template, and ops status script behavior.
- Running `python cli.py extensions --format json` prints manifest metadata for the echo example.
- Executing `python scripts/ops_status.py --url http://127.0.0.1:<port>` against a running telemetry server returns status information and exits with code 0 for healthy, non-zero for degraded (documented via tests).
- Documentation and release notes mention the new manifest registry, health metrics, and ops tooling.

## Idempotence and Recovery

- Service instrumentation changes remain opt-in when telemetry is disabled; the helper falls back to a no-op context manager.
- `HealthTelemetryServer` metrics do not mutate global state beyond the registry and handle repeated start/stop cycles.
- `scripts/ops_status.py` supports repeated invocation, overwriting its JSON output deterministically when requested.
- CLI manifest output gracefully handles missing metadata, defaulting to text mode if JSON serialization fails.

## Artifacts and Notes

- Capture command transcripts for `python scripts/dev_start.py` and `python cli.py extensions --format json` in the Surprises/Outcomes section once executed.
- Include snippets of Prometheus output showing new `zscripts_health_http_requests_total` series and service metrics in the notes.

## Interfaces and Dependencies

- `ToolkitService._instrument` will return a context manager that leverages `InstrumentationManager` when available; import `contextmanager` from `contextlib`.
- `HealthTelemetryServer` will initialise counters (`zscripts_health_http_requests_total`), histograms (`zscripts_health_http_request_duration_seconds`), and gauges (`zscripts_health_http_requests_inflight`).
- `ExtensionManifest` dataclass exposes fields (`name`, `module`, `description`, `entrypoint`, `version`, `capabilities`, `config_keys`).
- `scripts/ops_status.py` uses `urllib.request` for HTTP calls with configurable timeout; JSON summary uses `json` module.
- Tests rely on `TelemetryManager`, `InstrumentationManager`, and built-in HTTP server interactions; ensure deterministic waits via `time.sleep` where necessary.

Revision history:
- (2025-02-15 10:05Z) Initial draft authored to guide Stage 3 refresh implementation.
