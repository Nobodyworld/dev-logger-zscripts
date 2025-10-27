# Stewardship Audit and Evolution

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Maintain this document in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

We will complete the Stage 4 stewardship audit to ensure the zscripts toolkit operates as a coherent, observable system. A contributor following this plan will verify correctness, collect quality metrics, simplify lingering complexity, and publish a permanent steward report that captures findings, automation entry points, and the forward roadmap. After executing the plan, maintainers can read `STEWARDS_REPORT.md` to understand the system's state, run commands to reproduce metrics, and adopt new automation hooks tagged in the codebase.

## Progress

- [x] (2025-10-26T02:32Z) Verified the baseline with `coverage run -m pytest` so coverage data could feed Stage 4 metrics.
- [x] (2025-10-26T02:35Z) Authored `scripts/collect_quality_metrics.py` and captured coverage, complexity, dependency, and build outputs into `reports/metrics.json`.
- [x] (2025-10-26T02:37Z) Refactored CLI telemetry dispatch by introducing `_resolve_command_labels` for consistent logging and metrics labels.
- [x] (2025-10-26T02:39Z) Updated README, AUTOMATION guides, and the stewardship report to document the new metrics workflow and remove stale trace instructions.
- [x] (2025-10-26T02:41Z) Finalised STEWARDS_REPORT updates, refreshed ExecPlan sections, and captured latency measurements for `cli guardrails`.

## Surprises & Discoveries

- Observation: Network egress remains restricted; attempts to install `radon` still fail with proxy 403 errors, so complexity metrics now rely on the in-repo AST walker.
  Evidence: `python -m pip install radon` emitted repeated `ProxyError` messages. (`9cc13f`)

- Observation: Native coverage tooling is available, yielding 89.67% total statement coverage with the CLI at 65%, highlighting remaining hot spots.
  Evidence: `coverage report` summarised module coverage after the audit run. (`9a6f04`)

- Observation: The guardrails command completes in ~0.34s even with telemetry spans enabled, confirming the simplified metrics path has minimal overhead.
  Evidence: Timed invocation of `python cli.py guardrails` recorded 0.344 seconds. (`a03684`)

## Decision Log

- Decision: Build the `scripts/collect_quality_metrics.py` AST walker instead of relying on `radon`, which cannot be fetched behind the proxy.
  Rationale: Ensures repeatable complexity and dependency metrics using only stdlib dependencies.
  Date/Author: 2025-10-26T02:35Z / Steward Agent
- Decision: Introduce `_resolve_command_labels` to compute telemetry labels before entering the instrumentation span.
  Rationale: Eliminates duplicated string handling and guarantees metrics and logs share the same command label.
  Date/Author: 2025-10-26T02:37Z / Steward Agent

## Outcomes & Retrospective

CLI telemetry orchestration now relies on `_resolve_command_labels`, so metrics and logs derive from a single source of truth and the finally block stays minimal. The new metrics script produces repeatable coverage, complexity, and dependency data for `STEWARDS_REPORT.md`, while documentation updates direct agents to the unified workflow. Ruff and mypy baselines are unchanged, and pytest with coverage continues to pass.

## Context and Orientation

The repository root contains the CLI entry point at `zscripts/cli.py`, configuration helpers under `zscripts/configuration.py`, telemetry coordination inside `zscripts/observability/`, and tests in `tests/`. Documentation is spread across the root Markdown files (README, CHANGELOG, RELEASE_NOTES) and supporting reports within `REPORTS/` and `docs/`. Stage 3 previously introduced detailed telemetry instrumentation in `zscripts/cli.py`; our audit must ensure that instrumentation is correct yet simple, that metrics align with documentation, and that new stewardship artifacts live beside existing reports (e.g., `REPORT.md`).

The telemetry stack relies on `TelemetryManager` (`zscripts/observability/telemetry.py`) with metrics exported through `TelemetryManager.metrics`. Tests exercise CLI behavior in `tests/test_cli.py`. We will reuse `pytest` for validation and rely on the optional development dependencies defined in `pyproject.toml` (pytest, ruff, mypy, coverage).

## Plan of Work

1. Run `coverage run -m pytest` from the repository root to confirm the baseline and produce machine-readable coverage metrics.
2. Generate holistic metrics by executing `scripts/collect_quality_metrics.py --output reports/metrics.json`; if the script does not exist, implement the AST-based complexity/dependency walker using stdlib modules.
3. Measure CLI latency for a representative command (e.g., `python cli.py guardrails`) to confirm telemetry overhead stays within acceptable bounds.
4. Review `zscripts/cli.py` and simplify command/label handling while preserving instrumentation semantics.
5. Update documentation (README, AUTOMATION guides, operations, steward report) to reference the deterministic metrics workflow and remove stale trace-only guidance.
6. Refresh `STEWARDS_REPORT.md` with the new metrics table, simplification log, and roadmap updates.
7. Re-run quality checks (`coverage report`, `pytest`, `ruff check`, optional `mypy`) and capture relevant artefacts for the report.
8. Update this ExecPlan's progress, discoveries, decisions, and outcomes sections before preparing commit and PR messaging.

## Concrete Steps

1. From `/workspace/zscripts`, run `coverage run -m pytest` and capture results (coverage + test output).
2. Execute `python scripts/collect_quality_metrics.py --output reports/metrics.json` to generate coverage, complexity, dependency, and build statistics.
3. Time `python cli.py guardrails` with telemetry enabled to gather latency data for the steward report.
4. Update `zscripts/cli.py` by adding `_resolve_command_labels` and refactoring `_execute_command` to use it.
5. Revise README, AUTOMATION guides, and `docs/operations.md` to describe the metrics workflow and correct outdated telemetry references.
6. Refresh `STEWARDS_REPORT.md` with the new metrics table, simplification log, and roadmap bullets.
7. Run `coverage report` (plus optional `ruff check`/`mypy`) and archive artefacts (`reports/coverage.json`, `reports/metrics.json`).
8. Update ExecPlan narrative sections (progress, discoveries, decisions, outcomes) before preparing commit messaging.

## Validation and Acceptance

The change is accepted when:

- `pytest` passes from a clean working tree.
- The steward report documents the requested metrics (coverage %, cyclomatic complexity average, dependency depth, build time, performance observations) with clear reproduction notes or limitations.
- CLI telemetry code is simpler (single exit path for metrics, no redundant status tracking) while all existing tests continue to pass.
- Automation entry points are tagged in code where relevant.
- Documentation aligns with new behavior, and future roadmap plus agent roles are recorded.

## Idempotence and Recovery

All commands are safe to rerun. Installing tooling with `pip` affects only the ephemeral environment. If tests fail, revert changes with `git checkout -- <path>` and reapply edits according to the plan. `python -m build` writes to the `dist/` directory, which can be removed using `rm -rf dist/ build/`.

## Artifacts and Notes

- `coverage run -m pytest` (89 tests, 7.67s): see chunk `c56283`.
- `coverage report`: detailed module coverage including CLI hot spots (chunk `9a6f04`).
- `python scripts/collect_quality_metrics.py --output reports/metrics.json`: outputs captured in `reports/metrics.json`.
- `python -m pip install radon`: proxy failures recorded for complexity tooling (chunk `9cc13f`).
- Timed `python cli.py guardrails` invocation for latency measurement (chunk `a03684`).

## Interfaces and Dependencies

- `zscripts/cli.py`: ensure `main()` remains the CLI entry point, with handler signatures `Callable[[argparse.Namespace, ToolkitService], None]`.
- `zscripts.observability.telemetry.TelemetryManager`: used for spans and metrics; do not modify its public API.
- `tests/test_cli.py`: integration tests for CLI behaviors; must remain green after simplification.
- Markdown documentation files (`STEWARDS_REPORT.md`, `AUTOMATION_ROLES.md`, README, CHANGELOG, RELEASE_NOTES`).

