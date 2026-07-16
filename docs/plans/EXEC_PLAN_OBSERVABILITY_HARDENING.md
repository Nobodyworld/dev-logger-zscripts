# Observability and CLI Resilience Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

We will tighten the zscripts CLI runtime by providing first-class observability hooks and predictable shutdown behavior. After these changes, every CLI command invocation yields structured correlation identifiers, telemetry spans, and Prometheus metrics covering command outcomes. The telemetry server will terminate cleanly, avoiding orphaned background threads. We will document these capabilities and extend tests so newcomers can verify the behavior end-to-end.

## Progress

- [x] (2025-02-14 00:00Z) Draft ExecPlan describing observability hardening scope.
- [x] (2025-02-14 00:30Z) Instrumented CLI commands with correlation IDs, spans, metrics, and deterministic telemetry shutdown.
- [x] (2025-02-14 01:00Z) Added regression tests covering CLI metrics for success and failure plus telemetry stop semantics.
- [x] (2025-02-14 01:20Z) Refreshed README, architecture overview, extension guide, and automation playbook with CLI telemetry guidance.
- [x] (2025-02-14 01:40Z) Updated CHANGELOG and RELEASE_NOTES with CLI observability hardening; coverage JSON pending until the `coverage` tool is available in the environment.
- [x] (2025-02-14 02:00Z) Documented outcomes and residual coverage dependency gaps in the ExecPlan retrospective.

## Surprises & Discoveries

- Observation: Monkeypatching `TelemetryManager` was necessary to assert `stop()` semantics without leaking threads during tests.
  Evidence: Added `RecordingTelemetryManager` fixture in `tests/test_cli.py` capturing `stop_calls` and verifying `health_server.is_running()` becomes `False`.
- Observation: The execution environment lacks the `coverage` package, so automated coverage JSON generation remains pending.
  Evidence: `python -m coverage` exited with "No module named coverage"; manual pytest run captured as fallback.

## Decision Log

- Decision: Use a single ExecPlan for CLI observability, telemetry shutdown, and documentation refresh.
  Rationale: The work touches the same entry point (`zscripts/cli.py`) and related docs, so coordinating changes in one plan keeps validation coherent.
  Date/Author: 2025-02-14 / Codex
- Decision: Store `--command` arguments under `command_args` to preserve the subcommand identifier for telemetry labelling.
  Rationale: The previous destination reused `command`, overwriting the subparser name and preventing accurate metrics labels.
  Date/Author: 2025-02-14 / Codex

## Outcomes & Retrospective

- The CLI now wraps every command execution with correlation IDs, telemetry spans,
  and metrics while guaranteeing the health server stops. Regression tests cover
  both successful and failing flows. Documentation, changelog, and release notes
  were refreshed to guide operators and extension authors. Coverage automation
  remains pending until the `coverage` package is installed in CI environments.

## Context and Orientation

The CLI entry point lives in `zscripts/cli.py`. It constructs a `TelemetryManager`, loads configuration, discovers extensions, and finally executes a handler function. Telemetry spans currently wrap service-level operations inside `zscripts/application/services.py`, yet top-level command execution lacks metrics. The health server started by `TelemetryManager.start()` never shuts down explicitly, which can leave daemon threads running until interpreter exit. Observability utilities such as `bind_correlation_id` (`zscripts/observability/logging.py`) and `start_span` (`zscripts/observability/tracing.py`) already exist. Tests for CLI behavior reside in `tests/test_cli.py`.

Documentation describing architecture and automation workflows is stored at the repository root (`README.md`, `docs/architecture/ARCHITECTURE_OVERVIEW.md`, `docs/automation/AUTOMATION.md`, `docs/guides/EXTENSION_GUIDE.md`). Release metadata is tracked in `CHANGELOG.md` and `docs/releases/RELEASE_NOTES.md`. Coverage artifacts are produced into `artifacts/coverage/` by `make coverage` or `scripts/dev_start.py`.

## Plan of Work

1. Update `zscripts/cli.py`:
   - Import `time`, `uuid`, and `bind_correlation_id`.
   - Configure a module-level logger for CLI operations.
   - Ensure `TelemetryManager.start()` runs exactly once and wrap the command execution in `try`/`except`/`else` to capture outcomes.
   - Generate a correlation identifier per invocation, binding it during configuration, extension registration, and handler execution.
   - Record metrics on `TelemetryManager.metrics` counters/histograms (e.g., `zscripts_cli_invocations_total`, `zscripts_cli_duration_seconds`) labelled by command name and status.
   - Wrap handler execution in `telemetry.span("cli.<command>", ...)`.
   - Guarantee `TelemetryManager.stop()` executes in a `finally` block.
   - Log unexpected exceptions and re-raise them after metrics emission.

2. Tests:
   - Extend `tests/test_cli.py` to simulate a CLI invocation with telemetry enabled using a temporary port. Verify that metrics include CLI counters with expected labels and that the health server stops when the process ends (expose helper on `TelemetryManager`).
   - Add regression test ensuring correlation IDs propagate through spans by calling `bind_correlation_id` indirectly (inspect logs via capturing or check telemetry span trace id?). Instead, check that CLI command increments metrics even on failure by invoking a stub command that raises `SystemExit(2)`.

3. Documentation:
   - Update `README.md` and `docs/architecture/ARCHITECTURE_OVERVIEW.md` sections describing telemetry to mention CLI-level metrics and correlation IDs.
   - Refresh `docs/automation/AUTOMATION.md` with instructions for scraping CLI metrics and verifying telemetry shutdown.
   - Extend `docs/guides/EXTENSION_GUIDE.md` with advice for extension authors about using the shared metrics registry.

4. Release notes & coverage:
   - Append a new entry under the unreleased section (or create one if missing) in `CHANGELOG.md` summarizing observability hardening.
   - Update `docs/releases/RELEASE_NOTES.md` with a concise narrative of these changes.
   - Ensure `artifacts/coverage/coverage.json` is generated by running the coverage command after tests to embed in version control as evidence.

5. Validation:
   - Run `pytest` and `pytest --cov=zscripts` (via `make coverage`) to confirm tests and coverage succeed.
   - Optionally run `make lint` and `make type` if time permits, documenting any skipped steps.

## Concrete Steps

- `cd /workspace/zscripts`
- Edit `zscripts/cli.py` according to the plan.
- Update or add tests under `tests/test_cli.py`.
- Run `pytest` to ensure new tests pass.
- Execute `make coverage` to refresh `artifacts/coverage/coverage.json` and `coverage report` output.
- Modify documentation and release note files as outlined.
- Re-run `pytest` if documentation changes affect tests (unlikely) and capture relevant outputs.

## Validation and Acceptance

- Running `python cli.py --enable-telemetry guardrails` should emit structured logs containing a correlation ID and, after execution, scraping `http://127.0.0.1:<port>/metrics` should show `zscripts_cli_invocations_total` and `zscripts_cli_duration_seconds` entries for `command="guardrails"`.
- Unit tests in `tests/test_cli.py` must assert that CLI metrics capture success and failure outcomes and that `TelemetryManager.stop()` transitions `health_server.is_running()` to `False`.
- `make coverage` must succeed and report >=85% coverage, updating `artifacts/coverage/coverage.json`.
- Documentation and release notes should accurately describe the new telemetry behavior.

## Idempotence and Recovery

The CLI modifications add idempotent instrumentation that executes per invocation without persistent side effects. Running `make coverage` is safe to repeat; it overwrites `artifacts/coverage/coverage.json`. If the telemetry server fails to bind a port during tests, adjust the test fixture to select an ephemeral port or skip the assertion with a clear message. All documentation edits are standard Git-tracked changes and can be reverted with `git checkout -- <file>` if necessary.

## Artifacts and Notes

- Pytest regression run:
      $ pytest
      45 passed, 1 warning in 5.34s
- Coverage attempt (tool missing in environment):
      $ python -m coverage run -m pytest
      /root/.pyenv/versions/3.11.12/bin/python: No module named coverage

## Interfaces and Dependencies

- `TelemetryManager.metrics.counter(name, description)` returns a `CounterMetric` with `.inc(amount=1.0, labels={...})`.
- `TelemetryManager.metrics.histogram(name, description)` returns a `HistogramMetric` with `.observe(value, labels={...})`.
- `TelemetryManager.span(operation, attributes=None)` yields a context manager that records traces and metrics.
- The CLI will access these APIs to produce new metrics `zscripts_cli_invocations_total` and `zscripts_cli_duration_seconds`.
- Tests should import `TelemetryManager` and `TelemetrySettings` from `zscripts.observability.telemetry` and the CLI `main` function from `zscripts.cli`.
