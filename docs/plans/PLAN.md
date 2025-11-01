# Execution Plan

_Last updated: 2025-10-19_

This plan sequences modernization into guardrailed milestones that deliver incremental value without regressing the CLI’s
behaviour. Each task is sized for a reviewable PR and carries explicit rollback instructions, tags, and prerequisites.
docs/plans/STATUS.md will track execution progress after every PR.

## Milestone Readiness Matrix
| Milestone | Goal | Exit Criteria |
|-----------|------|---------------|
| M0 – Discovery | Establish shared understanding and roadmap. | docs/plans/REPORT.md + docs/plans/PLAN.md merged, referenced from README and docs/plans/STATUS.md, stakeholders sign-off. |
| M1 – Governance & CI | Harden policies, docs, and automation to catch regressions early. | Governance docs aligned, CI matrix & caching live, pre-commit parity achieved. |
| M2 – Type Safety & Modularity | Remove typing debt and prepare for refactors. | mypy strict clean, config schema validated, utilities modularised behind flags. |
| M3 – Quality Gates | Expand regression safety nets. | Snapshot/integration/coverage suites stable, coverage ≥85% core modules. |
| M4 – Security & Observability | Provide supply-chain visibility and runtime insight. | SBOM automation, secret scanning, structured logging flag, telemetry hooks. |
| M5 – Performance & Resilience | Quantify and improve throughput & UX. | Benchmarks in place, traversal optimised behind flag, graceful cancellation documented. |
| M6 – Release & Adoption | Automate releases and onboard contributors fast. | Semantic release pipeline, adoption docs, docs/plans/STATUS.md summarises residual risk. |

## Milestone 0 – Discovery & Alignment
### Workstream M0.W1 – Intelligence Baseline
- **Task M0.W1.T1 – Ratify Repo Intelligence & Execution Plan**
  - Goal: Publish docs/plans/REPORT.md and docs/plans/PLAN.md (this document) in main with cross-links to README and docs/plans/STATUS.md.
  - Acceptance Criteria: Docs merged; README/STATUS reference them; kickoff notes shared with stakeholders.
  - Blast Radius: Documentation only.
  - Rollback Plan: Revert documentation commit.
  - Tags: {docs, DX}.
  - Prerequisites: None.
  - Blockers: Stakeholder roster confirmation.

## Milestone 1 – Governance, DX, and CI Foundations
### Definition of Done
- Governance docs (LICENSE, README, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, SUPPORT, CODEOWNERS) aligned and lint-clean.
- `.github/` contains PR/Issue templates, CI status checks enforced, commitlint active.
- Developers can run `make check` with identical tooling to CI.

### Workstream M1.W1 – Governance & Policy
- **Task M1.W1.T1 – Normalize governance documents**
  - Goal: Ensure policy docs are consistent, linked, and reference escalation paths.
  - Acceptance Criteria: README links governance bundle; CODEOWNERS current; templates auto-apply.
  - Blast Radius: Docs/templates.
  - Rollback Plan: Revert doc/template updates.
  - Tags: {docs, DX}.
  - Prerequisites: M0 complete.
  - Blockers: Confirm maintainer list and contact info.
- **Task M1.W1.T2 – Adopt Conventional Commits & commitlint enforcement**
  - Goal: Enforce conventional commits via commitlint in CI and optional pre-commit hook.
  - Acceptance Criteria: CI rejects malformed commits; CONTRIBUTING documents style; sample commit messages provided.
  - Blast Radius: Tooling/CI.
  - Rollback Plan: Remove commitlint config + workflow step.
  - Tags: {DX}.
  - Prerequisites: Task M1.W1.T1.
  - Blockers: Node runtime availability (resolve via `commitlint --help` container or python equivalent).

### Workstream M1.W2 – CI/CD + Tooling Baseline
- **Task M1.W2.T1 – Harden CI workflow**
  - Goal: Update `.github/workflows/ci.yml` for Python 3.10–3.12 matrix, pip caching, artifact uploads (coverage, SBOM, security).
  - Acceptance Criteria: Workflow passes, badge updated, required checks documented in README/CONTRIBUTING.
  - Blast Radius: CI only.
  - Rollback Plan: Revert workflow or temporarily disable check.
  - Tags: {testing, reliability, DX}.
  - Prerequisites: Task M1.W1.T1.
  - Blockers: Secrets for artifact hosting (if needed).
- **Task M1.W2.T2 – Align pre-commit with CI**
  - Goal: Refresh `.pre-commit-config.yaml` to run Ruff fmt/check, mypy (fast subset), bandit, gitleaks, pytest --collect-only,
    and commitlint optional hook.
  - Acceptance Criteria: `pre-commit run --all-files` succeeds; CI job enforces parity; CONTRIBUTING updated.
  - Blast Radius: Tooling.
  - Rollback Plan: Revert config + workflow step.
  - Tags: {DX, testing, security}.
  - Prerequisites: Task M1.W2.T1.
  - Blockers: Hook runtime (tune `pass_filenames` and caching).
- **Task M1.W2.T3 – Developer bootstrap command**
  - Goal: Provide single-command onboarding (`make dev` / `make check`) with troubleshooting notes.
  - Acceptance Criteria: README “First Hour Guide” present; command executes lint/type/test locally within 5 minutes.
  - Blast Radius: Docs + automation.
  - Rollback Plan: Revert Makefile/docs changes.
  - Tags: {DX, docs}.
  - Prerequisites: Task M1.W2.T2.
  - Blockers: None.

## Milestone 2 – Type Safety & Code Health
### Definition of Done
- `make type` (mypy strict) passes without ignores.
- Config schema validated with clear error messaging and `.env.example` parity.
- Utilities decomposed with compatibility shims and ADR documenting architecture decision.

### Workstream M2.W1 – Strict Typing Expansion
- **Task M2.W1.T1 – Eliminate typing debt**
  - Goal: Annotate modules, remove `# type: ignore`, and ensure mypy strict passes.
  - Acceptance Criteria: mypy clean, pyproject excludes minimal, docs note typing expectations.
  - Blast Radius: Runtime (medium risk).
  - Rollback Plan: Revert targeted typing commits.
  - Tags: {DX, reliability}.
  - Prerequisites: Milestone 1 complete.
  - Blockers: Dynamic behaviour in `utils` may require refactors.
- **Task M2.W1.T2 – Config schema upgrade**
  - Goal: Replace manual parsing with typed schema (Pydantic or attrs), add `.env.example`, validation errors with context.
  - Acceptance Criteria: Tests cover invalid inputs; CLI surfaces actionable errors; docs updated.
  - Blast Radius: Config path (medium/high).
  - Rollback Plan: Guard behind feature flag (e.g., `ZSCRIPTS_USE_PYDANTIC=false`).
  - Tags: {reliability, security, DX}.
  - Prerequisites: Task M2.W1.T1.
  - Blockers: Dependency selection and licensing review.

### Workstream M2.W2 – Module Decomposition
- **Task M2.W2.T1 – Split `zscripts.utils`**
  - Goal: Extract traversal, filtering, rendering, and IO concerns into dedicated modules with orchestrator facade.
  - Acceptance Criteria: Tests updated; compatibility imports maintained; ADR captured; feature flag toggles new pipeline.
  - Blast Radius: High (core logic).
  - Rollback Plan: Disable feature flag, revert orchestrator changes.
  - Tags: {DX, reliability, performance}.
  - Prerequisites: Task M2.W1.T1, ADR drafted.
  - Blockers: Coordination with downstream consumers.
- **Task M2.W2.T2 – Public API curation**
  - Goal: Define explicit exports via `__all__`, add deprecation warnings/timeline for legacy wrappers, document supported APIs.
  - Acceptance Criteria: Tests assert warnings; CHANGELOG communicates timeline; README updated.
  - Blast Radius: Medium.
  - Rollback Plan: Remove warnings/exports changes.
  - Tags: {DX, docs, reliability}.
  - Prerequisites: Task M2.W2.T1.
  - Blockers: Communication plan for downstream users.

## Milestone 3 – Testing & Quality Assurance
### Definition of Done
- Golden-path CLI snapshots with deterministic fixtures.
- Performance integration test for large repo fixture (opt-in).
- Coverage thresholds enforced (≥85% core modules) with artifacts uploaded in CI.

### Workstream M3.W1 – Regression Coverage
- **Task M3.W1.T1 – Golden CLI snapshots**
  - Goal: Snapshot CLI outputs for `collect`, `consolidate`, `tree` using `examples/sample_project` fixtures.
  - Acceptance Criteria: Deterministic outputs; update workflow documented; tests marked `snapshot`.
  - Blast Radius: Tests.
  - Rollback Plan: Remove snapshots/markers.
  - Tags: {testing, reliability}.
  - Prerequisites: Milestone 2 stable APIs.
  - Blockers: Platform newline handling.
- **Task M3.W1.T2 – Large-repo integration suite**
  - Goal: Generate synthetic large fixture at runtime; assert runtime budget and memory thresholds.
  - Acceptance Criteria: Test marked `slow`/optional; metrics recorded; docs note opt-in flag.
  - Blast Radius: Tests (runtime cost).
  - Rollback Plan: Skip/disable marker.
  - Tags: {testing, performance}.
  - Prerequisites: Task M3.W1.T1.
  - Blockers: CI runtime limits (opt into nightly job if necessary).

### Workstream M3.W2 – Coverage & Reporting
- **Task M3.W2.T1 – Enforce coverage thresholds**
  - Goal: Configure pytest-cov thresholds, upload HTML/XML reports, add badge.
  - Acceptance Criteria: `make test` fails <85% coverage; CI uploads artifacts; README badge live.
  - Blast Radius: Tests + CI.
  - Rollback Plan: Relax threshold or revert config.
  - Tags: {testing, reliability}.
  - Prerequisites: Task M3.W1.T1.
  - Blockers: Storage for artifacts (use GitHub Actions artifacts).
- **Task M3.W2.T2 – Mutation/property testing expansion**
  - Goal: Enhance Hypothesis strategies for config/CLI; add nightly mutation testing job (e.g., mutmut) gated by label.
  - Acceptance Criteria: Tests documented; optional CI workflow added; failures triaged with action items.
  - Blast Radius: Tests.
  - Rollback Plan: Disable workflow/markers.
  - Tags: {testing, reliability}.
  - Prerequisites: Task M3.W1.T1.
  - Blockers: Runtime; may require nightly schedule.

## Milestone 4 – Security & Observability
### Definition of Done
- Automated SBOM + secret scanning integrated in CI; SECURITY.md updated with process.
- Structured logging (JSON/text) available via flag with context IDs.
- Metrics/tracing hooks integrated behind noop exporters.

### Workstream M4.W1 – Supply Chain Security
- **Task M4.W1.T1 – SBOM & secret scanning automation**
  - Goal: Run CycloneDX, gitleaks/trivy in CI, publish artifacts, document remediation policy.
  - Acceptance Criteria: CI fails on findings; SECURITY.md outlines escalation; artifacts downloadable.
  - Blast Radius: CI.
  - Rollback Plan: Disable workflows / revert configs.
  - Tags: {security, reliability}.
  - Prerequisites: Milestone 1 baseline.
  - Blockers: Tool runtime (cache results where possible).
- **Task M4.W1.T2 – Configuration hardening**
  - Goal: Redact secrets in logs, enforce env validation, introduce safe defaults.
  - Acceptance Criteria: Tests for misconfigurations; docs note secure defaults.
  - Blast Radius: Runtime config (medium).
  - Rollback Plan: Feature flag fallback.
  - Tags: {security, reliability}.
  - Prerequisites: Task M2.W1.T2.
  - Blockers: Additional dependencies (e.g., `python-dotenv`).

### Workstream M4.W2 – Observability Foundations
- **Task M4.W2.T1 – Structured logging**
  - Goal: Implement structured logging with correlation IDs, log level controls, JSON/text formatter selection.
  - Acceptance Criteria: CLI flag/env toggles; integration tests validate output; docs updated.
  - Blast Radius: CLI output (high).
  - Rollback Plan: Default flag off or revert module.
  - Tags: {reliability, DX}.
  - Prerequisites: Task M2.W2.T1.
  - Blockers: Format stability + downstream tooling.
- **Task M4.W2.T2 – Metrics & tracing hooks**
  - Goal: Add optional OpenTelemetry counters/timers with noop default and docs for exporters.
  - Acceptance Criteria: Integration test uses in-memory exporter; README includes deployment guidance.
  - Blast Radius: Medium (optional path).
  - Rollback Plan: Disable exporters / revert instrumentation.
  - Tags: {reliability, performance}.
  - Prerequisites: Task M4.W2.T1.
  - Blockers: Dependency footprint (ensure optional extras handling).

## Milestone 5 – Performance & Resilience
### Definition of Done
- Benchmark harness quantifies baseline and improvements.
- Traversal optimizations deliver ≥20% improvement on large fixture, gated behind feature flag.
- CLI gracefully handles cancellations/retries with cleanup semantics.

### Workstream M5.W1 – Performance Optimization
- **Task M5.W1.T1 – Benchmark harness**
  - Goal: Add `pytest-benchmark` (or similar) to measure traversal/log writing times; integrate with CI baseline.
  - Acceptance Criteria: `make benchmark` command; CI stores results; README documents usage.
  - Blast Radius: Tests/automation.
  - Rollback Plan: Remove harness.
  - Tags: {performance, testing}.
  - Prerequisites: Task M3.W1.T2.
  - Blockers: CI runtime (possible nightly job).
- **Task M5.W1.T2 – Optimize traversal pipeline**
  - Goal: Apply profiling-driven improvements (memoization, concurrency, async IO) behind feature flag targeting ≥20% speedup.
  - Acceptance Criteria: Benchmarks show improvement; docs note flag; changelog records optimisation.
  - Blast Radius: High (core logic).
  - Rollback Plan: Disable flag or revert changes.
  - Tags: {performance, reliability}.
  - Prerequisites: Task M5.W1.T1.
  - Blockers: Cross-platform filesystem semantics.

### Workstream M5.W2 – Resilience & UX
- **Task M5.W2.T1 – Graceful cancellation & retries**
  - Goal: Implement signal handling, transient IO retry/backoff, and cleanup for partially written outputs.
  - Acceptance Criteria: Tests simulate failures; docs describe behaviour; defaults configurable.
  - Blast Radius: Runtime control flow (medium).
  - Rollback Plan: Feature flag fallback.
  - Tags: {reliability, DX}.
  - Prerequisites: Task M2.W2.T1.
  - Blockers: Platform-specific signal support.
- **Task M5.W2.T2 – `zscripts doctor` health command**
  - Goal: Add CLI subcommand to validate environment, configuration, telemetry connectivity, and output readiness.
  - Acceptance Criteria: Command documented; tests cover pass/fail scenarios; integrates with structured logging.
  - Blast Radius: Low/medium (new feature).
  - Rollback Plan: Remove command.
  - Tags: {DX, reliability}.
  - Prerequisites: Task M4.W2.T1.
  - Blockers: None.

## Milestone 6 – Release Automation & Adoption
### Definition of Done
- Release workflow automated with semantic versioning, signed artifacts, and SBOM attachment.
- docs/plans/STATUS.md summarises current health, pending risks, and next steps.
- Documentation bundle provides “First Hour Guide”, “Common Tasks”, and “Troubleshooting”.

### Workstream M6.W1 – Release & Change Management
- **Task M6.W1.T1 – Semantic release pipeline**
  - Goal: Automate versioning, changelog generation, SBOM inclusion, and PyPI publication using GitHub Actions and OIDC.
  - Acceptance Criteria: Dry-run release documented; workflow publishes signed artifacts to draft release; CHANGELOG updates
    automatically.
  - Blast Radius: CI/release.
  - Rollback Plan: Disable workflow.
  - Tags: {DX, reliability, security}.
  - Prerequisites: Milestones 1–4 stabilised.
  - Blockers: PyPI permissions and signing keys.
- **Task M6.W1.T2 – Adoption enablement docs**
  - Goal: Publish onboarding guides (`docs/first-hour.md`, `docs/common-tasks.md`, `docs/troubleshooting.md`) and refresh
    docs/plans/STATUS.md with modernization summary and next steps.
  - Acceptance Criteria: Docs merged, cross-linked from README; docs/plans/STATUS.md updated post-PR.
  - Blast Radius: Docs.
  - Rollback Plan: Revert docs.
  - Tags: {docs, DX}.
  - Prerequisites: Task M6.W1.T1.
  - Blockers: None.

## Sequencing & Parallelism Guidance
- Milestone 1 provides guardrails; do not start runtime refactors (Milestone 2+) until CI/pre-commit hardening is complete.
- Typing and modularisation (Milestone 2) should land before observability/performance work to minimise merge conflicts.
- Testing improvements (Milestone 3) can run in parallel with late Milestone 2 tasks once APIs stabilise.
- Security & observability (Milestone 4) depends on typed config and modular utilities for safe instrumentation.
- Performance work (Milestone 5) requires benchmarks + regression suites to measure improvement safely.
- Release automation (Milestone 6) is final to ensure pipeline codifies mature processes.

## Risk Management & Rollback Strategy
- All runtime-impacting changes must ship behind feature flags or opt-in environment variables until validated in production
  scenarios.
- Every PR updates docs/plans/STATUS.md with summary, risk notes, and next steps.
- Architecture Decision Records (`docs/adr/YYYYMMDD-*.md`) document major structural choices and link to related PRs.
- Rollbacks rely on git revert plus feature-flag disablement to ensure rapid mitigation without redeploy.
