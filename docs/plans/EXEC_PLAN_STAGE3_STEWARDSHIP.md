# Stage 3 Stewardship & Future-Proofing ExecPlan

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Refer to `.agent/PLANS.md` for the required structure and maintenance rules. This document complies with those requirements and must remain self-contained.

## Purpose / Big Picture

Stage 3 transforms the reporting toolkit from a functional product into an extensible platform that other teams and automation agents can evolve safely. After finishing this plan, a maintainer will be able to: (1) observe runtime health through metrics, tracing spans, and readiness endpoints; (2) add new tool integrations via a documented extension boundary and starter template; (3) follow hardened contributor workflows with quality gates and agent guardrails; and (4) understand how to scale or migrate the architecture using the new overview, future-proofing notes, and release automation scripts. The acceptance proof includes running the quality pipeline (`make check`), generating coverage and observability artifacts, exercising the sample extension, and reviewing the produced documentation.

## Progress

- [x] (2025-02-14 17:10Z) Drafted Stage 3 ExecPlan outlining stewardship scope, objectives, and acceptance criteria.
- [x] (2025-02-14 18:05Z) Establish observability enhancements: shared tracing utilities, Prometheus metrics expansion, health endpoint hardening, and incident response documentation.
- [x] (2025-02-14 18:55Z) Build modular expansion scaffolding: refactor extension registry, add template generator, and ship a reference extension with telemetry spans.
- [x] (2025-02-14 19:25Z) Enable developer/agent workflows: CLI helpers, CONTRIBUTING updates, AUTOMATION/AGENTS guidelines, and TODO priority tagging convention.
- [x] (2025-02-14 19:55Z) Implement continuous improvement loop: enforce quality gates, add dependency update automation script, and document release/coverage workflows.
- [x] (2025-02-14 20:40Z) Deliver future-proofing assets: architecture overview refresh, scalability notes, migration outlines, and next-gen opportunities summary.
- [x] (2025-02-14 21:05Z) Final validation, coverage uplift to ≥85%, documentation sweep, and retrospective update.

## Surprises & Discoveries

- Observation: Logging extra keys such as `module` collide with Python's internal `LogRecord` fields when instrumentation attaches attributes.
  Evidence: `pytest` failures in `tests/test_cli.py` after wiring instrumentation (`85693e†L1-L40`).
- Observation: Health endpoints now expose readiness and liveness data, and tests confirm `/healthz/ready` and `/healthz/live` respond with JSON payloads.
  Evidence: New assertions in `tests/test_observability.py::test_health_server_serves_health_and_metrics`.
- Observation: Storing the `ExtensionContext` on `ToolkitExtension` enables CLI handlers to access instrumentation without global imports.
  Evidence: Updated `zscripts/extensions/examples/plugin_echo.py` instrumentation usage and passing tests (`0afffe†L1-L7`).
- Observation: `scripts/bootstrap.py` and `scripts/agent_guard.py` provide deterministic bootstrapping and guardrail execution for agents.
  Evidence: New scripts added with doc updates in `CONTRIBUTING.md` and `docs/automation/AUTOMATION.md`.
- Observation: Dependabot configuration and the release tagging helper establish a repeatable dependency and versioning cadence.
  Evidence: `.github/dependabot.yml` and `scripts/tag_release.py` additions.
- Observation: Coverage driven by subprocess CLI invocations did not improve the
  shared `coverage.py` metrics; new in-process configuration, logging, and
  infrastructure tests were required to exceed the 85% gate.
  Evidence: `tests/test_configuration.py`, `tests/test_observability.py`, and
  `tests/test_infrastructure.py` additions with coverage now at 90%.

## Decision Log

- Decision: Introduce `InstrumentationManager` to unify spans, metrics, and correlation IDs across CLI and extension subsystems.
  Rationale: Centralises observability logic, enabling consistent metrics and structured logging without duplicating telemetry wiring.
  Date/Author: 2025-02-14 / Assistant
- Decision: Sanitize instrumentation attribute names (e.g., `extension`) to avoid clashing with reserved logging fields.
  Rationale: Prevented runtime `KeyError` exceptions raised when `LogRecord` reserved fields were overwritten.
  Date/Author: 2025-02-14 / Assistant
- Decision: Add a CLI-managed scaffolder (`extensions scaffold`) backed by reusable templating utilities.
  Rationale: Lowers the barrier for contributors and agents to generate compliant extensions while sharing code with the standalone script.
  Date/Author: 2025-02-14 / Assistant
- Decision: Introduce dedicated bootstrap and agent guard scripts to codify environment setup and pre-flight quality gates.
  Rationale: Ensures humans and agents can reproduce the validated pipeline with a single command, aligning documentation and automation guidance.
  Date/Author: 2025-02-14 / Assistant
- Decision: Add Dependabot automation and a version bump script to streamline release hygiene.
  Rationale: Keeps dependencies fresh and documents the manual tagging workflow until semantic-release is enabled.
  Date/Author: 2025-02-14 / Assistant

## Outcomes & Retrospective

- Coverage now sits at 90% with infrastructure, logging, and configuration modules
  all exceeding the 85% bar, backed by 89 automated tests. The quality gate
  artifact (`artifacts/quality/quality_gate.json`) confirms lint, type, and coverage
  thresholds pass under `scripts/dev_start.py`.
- Observability safeguards (health server, instrumentation manager, logging
  correlation IDs) are exercised by targeted unit tests and documented in the
  refreshed operations guide, architecture overview, and automation playbooks.
- Extension scaffolding, agent guardrails, and release automation scripts are
  validated end-to-end, with docs and ExecPlan notes capturing onboarding,
  incident response, and next-generation opportunities.

## Context and Orientation

The repository contains a Python-based toolkit (`zscripts/`) with CLI entrypoints (`cli.py` and `zscripts/cli.py`), reporting services under `zscripts/application/`, and observability utilities in `zscripts/observability/`. Extensions live under `zscripts/extensions/`, implementing plugin-style integrations. Documentation resides in `docs/`, while developer onboarding content is in `README.md`, `CONTRIBUTING.md`, and various `EXEC_PLAN_*.md` files. Tests live in `tests/`. Existing observability includes structured logging and Prometheus metrics, but tracing coverage is light. Quality gates rely on `make check`, `ruff`, `pytest`, and scoped mypy runs. Automation scaffolding is minimal and dependency updates are manual. This plan assumes Python 3.11+ with `poetry`/`pip` managed dependencies defined in `pyproject.toml` and `requirements.txt`.

## Plan of Work

We proceed in five milestones.

Milestone 1 (Observability & Maintainability): Introduce an `InstrumentationManager` that wraps logging, metrics, and tracing with consistent context propagation. Expand metrics under `zscripts/observability/metrics.py` with counters/gauges for extension runs, CLI usage, and errors. Harden `zscripts/observability/health.py` with readiness/liveness separation, structured responses, and integration tests. Provide tracing utilities leveraging `contextvars` to propagate correlation IDs. Add a `docs/operations.md` incident response guide detailing how to interpret metrics, logs, and traces. Update configuration to expose telemetry toggles if needed.

Milestone 2 (Modular Expansion Layer): Refine the extension registry so new extensions self-register via entry points defined in `zscripts/extensions/__init__.py`. Add a `zscripts/extensions/template.py` (or similar) demonstrating the contract. Implement a CLI subcommand `python cli.py extensions scaffold <name>` that copies a starter template into `extensions/`. Provide documentation in `docs/guides/EXTENSION_GUIDE.md` describing how to build and register extensions and reference the sample extension.

Milestone 3 (Developer & Agent Enablement): Enhance `scripts/` with helper commands: a bootstrap script for local setup (`scripts/bootstrap.py`) and an agent-safe runner that invokes the quality pipeline (`scripts/agent_guard.py`). Update `CONTRIBUTING.md` with branching, commit, and review guidelines. Create or update `docs/automation/AUTOMATION.md` / `AGENTS.md` to describe how agents should interact, including safe commands, telemetry expectations, and rollback steps. Tag TODOs with `TODO(Px, est:Nh):` format to encode priority and effort. Provide `docs/dev_workflow.md` summarizing CLI and scripts.

Milestone 4 (Continuous Improvement Loop): Update the `Makefile` and CI notes so `make ci` runs lint, type, test, security (e.g., `pip-audit`), and coverage thresholds (≥85% critical modules). Add a script `scripts/update_dependencies.py` leveraging `pip` or `poetry` to refresh dependencies and output diff guidance. Configure Dependabot via `.github/dependabot.yml`. Document changelog automation and create a `scripts/tag_release.py` stub referencing semantic versioning.

Milestone 5 (Future-Proofing Deliverables): Refresh `docs/architecture/ARCHITECTURE_OVERVIEW.md` with diagrams (ASCII or described) and narrative covering observability, extension boundaries, and data flow. Create `docs/future_roadmap.md` capturing scalability, containerization, and migration paths. Add release notes summarizing Stage 3 improvements, compile next-generation opportunities in the summary, and update `Outcomes & Retrospective`.

Throughout each milestone we will update this plan's Progress, Surprises, Decision Log, and Outcomes sections. Each code change will follow repository formatting and include type hints, docstrings, and structured logging. Tests will be added or updated to ensure ≥85% coverage on `zscripts/application/`, `zscripts/observability/`, and `zscripts/extensions/`.

## Concrete Steps

1. For each milestone, work within the repository root (`/workspace/zscripts`). Use `rg` for search, `pytest` and `coverage` for tests, `ruff` for linting, and `mypy` for typing. Document commands and outputs in this plan as progress is made.
2. When adding new modules, ensure they include module-level docstrings explaining purpose, usage, and integration points. For scripts, provide `if __name__ == "__main__":` entrypoints when appropriate.
3. Update documentation files (`docs/*.md`, `README.md`, etc.) and ensure cross-links exist. Add new docs to `docs/INDEX.md`.
4. After implementing features, run `make check`, `pytest --cov=zscripts --cov-report=term-missing`, and `pip-audit` (or `poetry check`). Capture outputs for validation.
5. Update `CHANGELOG.md` and `docs/releases/RELEASE_NOTES.md` with Stage 3 highlights, ensuring release instructions align with new automation.

## Validation and Acceptance

Acceptance requires:
- `make check` passes, invoking lint, type, test, security, and coverage checks.
- `pytest --cov=zscripts --cov-report=term-missing` reports ≥85% coverage for critical modules; document results in `artifacts/coverage/coverage_report.md`.
- Running `python cli.py telemetry health` (or equivalent) confirms health endpoints respond with readiness and liveness states, validated via new tests.
- Invoking `python cli.py extensions scaffold sample_future` creates a template extension consistent with `docs/guides/EXTENSION_GUIDE.md` and passes contract tests.
- Documentation (`docs/architecture/ARCHITECTURE_OVERVIEW.md`, `docs/guides/EXTENSION_GUIDE.md`, `docs/operations.md`, `docs/future_roadmap.md`, `docs/automation/AUTOMATION.md`, `CONTRIBUTING.md`) reflects updated workflows and references new tooling.
- `scripts/update_dependencies.py --check` demonstrates dependency status and surfaces actionable output.
- Release artifacts (`CHANGELOG.md`, `docs/releases/RELEASE_NOTES.md`) summarize Stage 3 improvements and any migration notes.

## Idempotence and Recovery

Scripts introduced must be idempotent: running `extensions scaffold` twice with the same name should warn and exit without overwriting; `update_dependencies.py` should support `--check` and `--apply`. Health endpoints should tolerate repeated hits. Quality gates must not mutate state beyond cache directories. Document rollback steps in `docs/operations.md` (e.g., revert to previous release tag, disable extensions via config).

## Artifacts and Notes

As work progresses, capture:
- Key command outputs (test runs, coverage summaries, lint results) with timestamps.
- Snippets of new configuration or schema definitions for observability toggles.
- Example telemetry payloads (JSON) or log excerpts proving tracing integration.
- CLI help output for new subcommands.

## Interfaces and Dependencies

- `zscripts/observability/instrumentation.py`: new module exposing `InstrumentationManager` with methods `start_span(name: str)` and context managers returning span contexts. Depends on `logging`, `time`, `contextvars`, and Prometheus client.
- `zscripts/extensions/base.py`: ensure protocol definitions reference instrumentation hooks.
- `zscripts/extensions/reference.py`: implement reference extension using the manager.
- `cli.py` and `zscripts/cli.py`: add subcommands `telemetry` (health, metrics) and `extensions scaffold`.
- `scripts/update_dependencies.py`: use `subprocess` to run `pip list --outdated` or `poetry show -o` based on configuration; output Markdown summary.
- `.github/workflows/ci.yml`: add pipeline (if not present) or update instructions for local equivalent.
- Depend on `pip-audit` and `opentelemetry-api`/`opentelemetry-sdk` only if lightweight; otherwise rely on internal tracing abstraction.

Revision History:
- (2025-02-14 17:10Z) Initial draft created by Assistant to steer Stage 3 stewardship work.
