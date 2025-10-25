# Stewardship Audit and Evolution

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Maintain this document in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

We will complete the Stage 4 stewardship audit to ensure the zscripts toolkit operates as a coherent, observable system. A contributor following this plan will verify correctness, collect quality metrics, simplify lingering complexity, and publish a permanent steward report that captures findings, automation entry points, and the forward roadmap. After executing the plan, maintainers can read `STEWARDS_REPORT.md` to understand the system's state, run commands to reproduce metrics, and adopt new automation hooks tagged in the codebase.

## Progress

- [x] (2025-10-25T17:34Z) Drafted the stewardship ExecPlan and recorded repository orientation notes.
- [x] (2025-10-25T17:36Z) Ran baseline `pytest` suite to confirm green state and captured warning noise.
- [x] (2025-10-25T17:37Z) Gathered quality metrics (coverage via `trace`, cyclomatic complexity script, dependency depth, package size/time).
- [x] (2025-10-25T17:39Z) Simplified CLI telemetry orchestration with a unified `finally` block and automation tags.
- [x] (2025-10-25T17:39Z) Updated documentation and authored `STEWARDS_REPORT.md` plus `AUTOMATION_ROLES.md` to reflect the audit.
- [x] (2025-10-25T17:39Z) Tagged agent-safe automation entry points in `zscripts/cli.py` and documented usage in the new roles guide.
- [x] (2025-10-25T17:41Z) Finalized the steward report, updated ExecPlan outcomes, and prepared release documentation.

## Surprises & Discoveries

- Observation: Network egress is blocked, preventing `pip` from installing tooling such as `coverage`, `radon`, and `pipdeptree`.
  Evidence: `pip` install attempts returned `ProxyError` 403 Forbidden responses.

- Observation: Python's built-in `trace` module successfully generated per-line execution counts as an alternative coverage source.
  Evidence: `python -m trace --count --coverdir trace_cov --module pytest` produced `.cover` files for every `zscripts` module.

- Observation: Strict mypy checking reports longstanding `Any` usage across infrastructure and adapter modules.
  Evidence: `mypy zscripts` surfaced 153 baseline errors spanning schema, metrics, and adapter packages.

## Decision Log

- Decision: Use `python -m trace` to approximate coverage metrics since third-party packages cannot be fetched behind the proxy.
  Rationale: Maintains offline reproducibility and provides deterministic `.cover` artifacts for audit.
  Date/Author: 2025-10-25T17:37Z / Steward Agent
- Decision: Extracted `_prepare_and_execute` and `_execute_command` helpers from `main()` to reduce complexity and satisfy lint checks.
  Rationale: Keeps `main()` focused on configuration + context wiring while consolidating automation hooks in a reusable helper.
  Date/Author: 2025-10-25T17:41Z / Steward Agent

## Outcomes & Retrospective

CLI telemetry orchestration is now centralized within `_execute_command`, reducing redundant state handling while preserving logging and spans. The stewardship report and automation roles catalog document reproducible health metrics, proxy limitations, and agent responsibilities. Ruff passes cleanly, pytest remains green, and mypy highlights pre-existing debt for future remediation.

## Context and Orientation

The repository root contains the CLI entry point at `zscripts/cli.py`, configuration helpers under `zscripts/configuration.py`, telemetry coordination inside `zscripts/observability/`, and tests in `tests/`. Documentation is spread across the root Markdown files (README, CHANGELOG, RELEASE_NOTES) and supporting reports within `REPORTS/` and `docs/`. Stage 3 previously introduced detailed telemetry instrumentation in `zscripts/cli.py`; our audit must ensure that instrumentation is correct yet simple, that metrics align with documentation, and that new stewardship artifacts live beside existing reports (e.g., `REPORT.md`).

The telemetry stack relies on `TelemetryManager` (`zscripts/observability/telemetry.py`) with metrics exported through `TelemetryManager.metrics`. Tests exercise CLI behavior in `tests/test_cli.py`. We will reuse `pytest` for validation and rely on the optional development dependencies defined in `pyproject.toml` (pytest, ruff, mypy, coverage).

## Plan of Work

1. Run `pytest` from the repository root to confirm the current baseline passes before refactoring.
2. Attempt to capture coverage metrics via `pytest --cov=zscripts`; if coverage tooling is unavailable, note the limitation for later documentation.
3. Estimate cyclomatic complexity using `radon cc` if available; otherwise compute manually for the primary CLI module and describe reasoning in the steward report.
4. Analyze dependency structure by parsing `pyproject.toml` and enumerating package imports to derive a qualitative depth/cohesion ratio for the steward report.
5. Measure package footprint using `python -m build` if available or, failing that, `du -sh zscripts zscripts/config.py` to approximate install size.
6. Review `zscripts/cli.py` to simplify telemetry handling by consolidating the status tracking and ensuring metrics emission occurs in a single finally block; preserve logging.
7. Annotate relevant orchestration points with `# agent-entrypoint` or `# agent-safe-task` where future automation could hook in, particularly around CLI command dispatch and telemetry metrics.
8. Update documentation to align with simplified code and new automation guidance: revise README sections if they mention old telemetry behavior, append entries to CHANGELOG and RELEASE_NOTES summarizing audit outcomes, and add `STEWARDS_REPORT.md` with the requested metrics table and roadmap.
9. Create `AUTOMATION_ROLES.md` describing candidate agent jobs and triggers if clarity benefits stewardship.
10. Re-run tests (`pytest`) and, when tools are available, lint (`ruff check`) and type-check (`mypy`) to ensure no regressions.
11. Update this ExecPlan's progress, decisions, surprises, and outcomes sections to reflect discoveries, then prepare commit and PR messaging summarizing the audit.

## Concrete Steps

1. From `/workspace/zscripts`, run `pytest` and capture results.
2. Run `pytest --cov=zscripts` to gather coverage or record the failure reason.
3. Try `python -m pip show radon`; if missing, install locally with `python -m pip install radon` (acceptable for tooling) and execute `radon cc -s -a zscripts` to compute complexity. Record values.
4. Inspect dependencies by reading `pyproject.toml` and generating an import graph with `python -m pip install pipdeptree` followed by `pipdeptree --json-tree`. If installation is impossible, document the limitation and approximate manually.
5. Measure build footprint using `python -m pip install build` and `python -m build`, capturing the elapsed time with `/usr/bin/time -f '%E' python -m build`. If tooling installation fails, fall back to `du -sh zscripts` size measurement and note the gap.
6. Modify `zscripts/cli.py` to streamline telemetry instrumentation and insert automation tags. Ensure `_record_cli_metrics` handles caching gracefully.
7. Draft `STEWARDS_REPORT.md` containing the metrics table, recommendations, simplification log, and roadmap. Include coverage of automation entry points and risks.
8. Draft `AUTOMATION_ROLES.md` outlining agent responsibilities and triggers.
9. Update README/CHANGELOG/RELEASE_NOTES if behavior or instructions change.
10. Run quality checks: `pytest`, `ruff check`, and `mypy`. Capture outputs for the report.
11. Update ExecPlan narrative sections with findings, set remaining progress items to complete, and summarize outcomes.

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

- `pytest` (45 passed, 1 warning): see chunk `2e15c4`.
- `python -m trace --count --coverdir trace_cov --module pytest`: generated `.cover` files prior to cleanup.
- `ruff check`: clean run after CLI refactor (chunk `2de275`).
- `mypy zscripts`: surfaced baseline typing issues outside this audit's scope (chunk `93c55a`).

## Interfaces and Dependencies

- `zscripts/cli.py`: ensure `main()` remains the CLI entry point, with handler signatures `Callable[[argparse.Namespace, ToolkitService], None]`.
- `zscripts.observability.telemetry.TelemetryManager`: used for spans and metrics; do not modify its public API.
- `tests/test_cli.py`: integration tests for CLI behaviors; must remain green after simplification.
- Markdown documentation files (`STEWARDS_REPORT.md`, `AUTOMATION_ROLES.md`, README, CHANGELOG, RELEASE_NOTES`).

