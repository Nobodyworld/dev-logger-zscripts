# Stage 4 Stewardship Refresh ExecPlan

## Context
Stage 4 requires a holistic audit plus simplification and automation guidance. The prior
pass introduced metrics plumbing and documentation, but feedback indicated the results
did not fully meet expectations. This plan targets the remaining gaps.

## Objectives
- Validate and update repository-wide metrics with reproducible tooling.
- Reconcile documentation with the implemented telemetry and automation workflows.
- Simplify code paths that remain overly complex after Stage 3.
- Produce an updated Steward Report capturing metrics, recommendations, and roadmap.

## Tasks
1. **Metrics Refresh**
   - [x] Execute or enhance `scripts/collect_quality_metrics.py` to ensure it captures
     coverage, complexity, dependency cohesion, build timing, and CLI latency.
   - [x] Regenerate `artifacts/quality/metrics.json` (new artifact) for reproducible audits.

2. **Code Simplification & Tagging**
   - [x] Identify and refactor at least one high-complexity helper (target:
     `zscripts/observability/health.py` request flow) to reduce branching and improve
     readability.
   - [x] Review automation tags and ensure key helpers include `# agent-entrypoint` or
     `# agent-safe-task` comments where applicable.

3. **Documentation Alignment**
   - [x] Update `README.md`, `docs/automation/AUTOMATION.md`, and `docs/automation/AUTOMATION_ROLES.md` to reference the
     refreshed metrics workflow and any new automation hooks.
   - [x] Rewrite `STEWARDS_REPORT.md` with new metrics table, simplification log, roadmap,
     and emerging risks consistent with the audit results.

4. **Automation Artifacts**
   - [x] Ensure `artifacts/quality/` captures the latest metrics including coverage snapshot.
   - [x] Provide `docs/automation/AUTOMATION_ROLES.md` updates and, if necessary, additional
     documentation describing agent responsibilities.

## Validation
- Run `ruff`, `mypy`, and `pytest` to confirm code health after modifications.
- Execute `python scripts/collect_quality_metrics.py --output artifacts/quality/metrics.json` to
  verify metrics script functionality.

## Deliverables
- Updated code, scripts, and documentation reflecting the audit.
- New or refreshed metrics artifacts.
- Final Steward Report summarizing findings and roadmap.
