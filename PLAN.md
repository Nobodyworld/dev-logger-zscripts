# Execution Plan

This plan sequences modernization work from low-risk governance foundations through deeper architectural, security, and performance improvements. Each task is designed as a reviewable PR-sized unit with clear acceptance criteria and rollback guidance.

## Milestone 1: Foundation & Governance

### Workstream 1.1: Repository Governance
- **Task 1.1.1 – Establish governance docs & templates**  
  Goal: Publish CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, SUPPORT.md, CODEOWNERS, LICENSE verification, and ISSUE/PR templates aligned with project values.  
  Acceptance Criteria: Documents rendered in root/.github; templates auto-apply on GitHub; CODEOWNERS matches maintainer team; README references governance docs.  
  Blast Radius: Documentation only.  
  Rollback: Revert added markdown/templates.  
  Tags: {docs, DX, security}.  
  Prerequisites: Repo intelligence report (complete).  
  Blockers: None.
- **Task 1.1.2 – Introduce Conventional Commits & editor config**  
  Goal: Add commitlint config, npm package (if needed) or python-based hook, and `.editorconfig` for whitespace consistency.  
  Acceptance Criteria: Commitlint enforced via CI/pre-commit; documentation updated with commit guidelines; `.editorconfig` covers repo file types.  
  Blast Radius: Tooling/config only.  
  Rollback: Remove configs/hooks.  
  Tags: {DX}.  
  Prerequisites: Task 1.1.1 (documentation references commit guidelines).  
  Blockers: Potential need for Node runtime decision (documented).

### Workstream 1.2: CI/CD Bootstrap
- **Task 1.2.1 – GitHub Actions pipeline**  
  Goal: Create workflow running `make fmt --check`, `make lint`, `make type`, `make security`, and `make test` across Python 3.10–3.12 with caching.  
  Acceptance Criteria: Workflow passes locally via `act` or documented dry-run; badges added to README; failure gates merges.  
  Blast Radius: CI only.  
  Rollback: Disable or delete workflow file.  
  Tags: {testing, reliability, security, DX}.  
  Prerequisites: Task 1.1.1 (governance docs referencing CI) optional.  
  Blockers: None.
- **Task 1.2.2 – Pre-commit hook suite**  
  Goal: Configure `.pre-commit-config.yaml` aligning with Ruff format/lint, mypy (fast), bandit, commitlint, and pyproject sorter if adopted.  
  Acceptance Criteria: `pre-commit run --all-files` clean; README/CONTRIBUTING updated with installation; CI job ensures hook compliance.  
  Blast Radius: Tooling.  
  Rollback: Remove config/CI checks.  
  Tags: {DX, testing, security}.  
  Prerequisites: Task 1.2.1 (CI runner to enforce).  
  Blockers: None.
- **Task 1.2.3 – Makefile/Task runner refresh**  
  Goal: Ensure `make dev` / `make check` provide one-command bootstrap; add `justfile` or `taskfile` if needed.  
  Acceptance Criteria: Documented local bootstrap command; ensures environment parity instructions updated.  
  Blast Radius: Docs + scripts.  
  Rollback: Revert Makefile changes.  
  Tags: {DX}.  
  Prerequisites: Task 1.2.2 (align commands with hooks).  
  Blockers: None.

## Milestone 2: Type Safety & Code Hygiene

### Workstream 2.1: Strict Typing Rollout
- **Task 2.1.1 – mypy baseline cleanup**  
  Goal: Remove unused/ignored sections, ensure strict typing passes without `type: ignore` debt in core modules.  
  Acceptance Criteria: `make type` passes with minimal ignores; typing docs updated.  
  Blast Radius: Python modules.  
  Rollback: Revert targeted typing changes.  
  Tags: {DX, reliability}.  
  Prerequisites: Milestone 1 complete (CI ready).  
  Blockers: None.
- **Task 2.1.2 – Typed configuration schema**  
  Goal: Introduce `pydantic` or `attrs`-based validation to replace bespoke checks, emit JSON schema, and document `.env.example`.  
  Acceptance Criteria: Config loader validates structure; tests cover invalid/missing fields; `.env.example` created; docs updated.  
  Blast Radius: Config load path; requires regression tests.  
  Rollback: Revert module swap to prior dataclass approach.  
  Tags: {reliability, security, DX}.  
  Prerequisites: Task 2.1.1 (clean baseline).  
  Blockers: Choice of dependency (document & ADR).

### Workstream 2.2: Module Decomposition
- **Task 2.2.1 – Extract filesystem traversal module**  
  Goal: Split `zscripts.utils` into `fs.py` (walking, ignore parsing) and `render.py` (tree/log writing) with explicit exports.  
  Acceptance Criteria: No behavioural regressions; tests updated; new modules documented; legacy wrappers import from new packages with compatibility layer.  
  Blast Radius: Core util functions; high.  
  Rollback: Revert module split (ensure commit isolations).  
  Tags: {DX, reliability}.  
  Prerequisites: Task 2.1.1 (typing) to avoid compounding issues.  
  Blockers: Need ADR.
- **Task 2.2.2 – Introduce public API surface**  
  Goal: Add `zscripts/__init__.py` exports documenting supported functions; mark legacy wrappers deprecated with warnings & feature flags.  
  Acceptance Criteria: API documented in README; deprecation warnings behind env/flag; tests verifying warnings.  
  Blast Radius: Medium (import paths).  
  Rollback: Revert exports/warnings.  
  Tags: {DX, docs}.  
  Prerequisites: Task 2.2.1.  
  Blockers: None.

## Milestone 3: Testing & Quality Assurance

### Workstream 3.1: Test Pyramid Expansion
- **Task 3.1.1 – Golden CLI output tests**  
  Goal: Add snapshot tests for `collect`, `consolidate`, `tree` (dry-run + real).  
  Acceptance Criteria: Pytest golden files stored under `tests/data`; deterministic seeds; docs explain update workflow.  
  Blast Radius: Tests only.  
  Rollback: Remove new tests if blocking.  
  Tags: {testing, reliability}.  
  Prerequisites: Milestone 2 completion for stable APIs.  
  Blockers: None.
- **Task 3.1.2 – Integration fixture for large repos**  
  Goal: Build synthetic large project fixture to measure traversal speed and ensure no stack regressions.  
  Acceptance Criteria: Fixture generated on-the-fly (not checked in huge); tests assert runtime thresholds; metrics recorded.  
  Blast Radius: Tests/time; ensure gating via markers.  
  Rollback: Disable fixture-based test.  
  Tags: {testing, performance}.  
  Prerequisites: Task 3.1.1.  
  Blockers: Runtime cost (mitigate with markers).

### Workstream 3.2: Coverage & Reporting
- **Task 3.2.1 – Coverage thresholds & reporting**  
  Goal: Enforce ≥85% coverage on core modules; integrate coverage XML + badge + PR annotations.  
  Acceptance Criteria: CI fails under threshold; coverage uploaded (codecov or built-in); README badge.  
  Blast Radius: Tests/CI.  
  Rollback: Raise/lower threshold config.  
  Tags: {testing, reliability}.  
  Prerequisites: Task 1.2.1 (CI).  
  Blockers: External service configuration (document fallback).
- **Task 3.2.2 – Mutation / property testing expansion**  
  Goal: Extend hypothesis-based tests for config + CLI argument parsing; optional mutmut run.  
  Acceptance Criteria: New hypothesis strategies; CI job optional nightly; documentation for running long suite.  
  Blast Radius: Tests.  
  Rollback: Skip new tests.  
  Tags: {testing, reliability}.  
  Prerequisites: Task 3.1.1.  
  Blockers: Runtime.

## Milestone 4: Security & Observability

### Workstream 4.1: Supply Chain & Secrets
- **Task 4.1.1 – SBOM & dependency policy**  
  Goal: Generate CycloneDX SBOM in CI; add policy for vetting dependencies; integrate Trivy/Gitleaks scanning.  
  Acceptance Criteria: Workflow artifact produced; README/SECURITY doc outlines policy; secret scan gating merges.  
  Blast Radius: CI only.  
  Rollback: Disable workflows.  
  Tags: {security}.  
  Prerequisites: Milestone 1 CI scaffolding.  
  Blockers: Installing scanning tools (document caching).
- **Task 4.1.2 – Configuration hardening**  
  Goal: Validate config/environment inputs with schema + secrets redaction; add `.env.example` and runtime warnings for missing env.  
  Acceptance Criteria: CLI fails fast on invalid config; docs updated; tests cover failure paths.  
  Blast Radius: Runtime config; medium.  
  Rollback: Revert validation hook.  
  Tags: {security, reliability}.  
  Prerequisites: Task 2.1.2 (typed config).  
  Blockers: None.

### Workstream 4.2: Observability
- **Task 4.2.1 – Structured logging + verbosity controls**  
  Goal: Introduce structured logging adapter (JSON/text), correlation IDs, and log-level configuration.  
  Acceptance Criteria: CLI respects `--verbose` and env var for log level; logs structured; tests cover new flows; documentation updated.  
  Blast Radius: CLI output (high).  
  Rollback: Feature flag gating (default off).  
  Tags: {observability, DX}.  
  Prerequisites: Task 2.2.1 (module split for easier instrumentation).  
  Blockers: None.
- **Task 4.2.2 – Metrics & tracing hooks**  
  Goal: Add optional OpenTelemetry integration capturing counts/durations, with noop default.  
  Acceptance Criteria: CLI accepts `--otel-endpoint`; metrics exported in integration test; docs provide deployment guide.  
  Blast Radius: Medium (optional).  
  Rollback: Disable feature flag.  
  Tags: {observability, performance}.  
  Prerequisites: Task 4.2.1.  
  Blockers: Additional dependency evaluation.

## Milestone 5: Performance & Resilience

### Workstream 5.1: Performance Profiling
- **Task 5.1.1 – Benchmark suite**  
  Goal: Add `pytest-benchmark` or custom harness measuring traversal/log writing; track baseline in repo.  
  Acceptance Criteria: Benchmarks runnable via `make benchmark`; results stored in CI artifacts; README documents regression policy.  
  Blast Radius: Tests/time.  
  Rollback: Disable benchmark job.  
  Tags: {performance, testing}.  
  Prerequisites: Task 3.1.2 (large fixture).  
  Blockers: CI time.
- **Task 5.1.2 – Optimise traversal pipeline**  
  Goal: Use caching/iterators to reduce filesystem calls; consider multiprocessing for large repos; maintain feature parity.  
  Acceptance Criteria: Benchmarks show ≥20% improvement on large fixture; no regression in functionality; feature flagged if risky.  
  Blast Radius: High (core path).  
  Rollback: Toggle feature flag or revert commit.  
  Tags: {performance, reliability}.  
  Prerequisites: Task 5.1.1 (baseline).  
  Blockers: Platform-specific differences.

### Workstream 5.2: Resilience
- **Task 5.2.1 – Graceful cancellation & retries**  
  Goal: Add signal handling for CLI, timeouts for long operations, and retry/backoff for transient filesystem errors.  
  Acceptance Criteria: CTRL+C leaves partial outputs clean; tests simulate exceptions; docs updated.  
  Blast Radius: Medium (I/O).  
  Rollback: Disable signal hooks.  
  Tags: {reliability}.  
  Prerequisites: Task 2.2.1 (modular utilities).  
  Blockers: Cross-platform behavior.
- **Task 5.2.2 – Health checks for integrations**  
  Goal: Provide `zscripts doctor` subcommand verifying environment, config, and optional telemetry endpoints.  
  Acceptance Criteria: Command documented; tests cover success/failure; integrates with observability instrumentation.  
  Blast Radius: Low/medium (new command).  
  Rollback: Remove command.  
  Tags: {reliability, DX, observability}.  
  Prerequisites: Task 4.2.2 (telemetry).  
  Blockers: None.

## Milestone 6: Release & Adoption

### Workstream 6.1: Release Automation
- **Task 6.1.1 – Semantic release pipeline**  
  Goal: Configure release workflow to cut tagged builds, generate changelog, publish to PyPI, attach SBOM/signatures.  
  Acceptance Criteria: Dry-run release documented; pipeline uses OIDC for PyPI; CHANGELOG updates automated.  
  Blast Radius: CI/release only.  
  Rollback: Disable workflow.  
  Tags: {DX, reliability, security}.  
  Prerequisites: Milestones 1–4 for stability.  
  Blockers: PyPI credentials.
- **Task 6.1.2 – Adoption enablement docs**  
  Goal: Produce First Hour Guide, Common Tasks, Troubleshooting, and migration notes for new features (flags, new commands).  
  Acceptance Criteria: Docs published in `docs/` & linked from README; STATUS.md updated with final recommendations.  
  Blast Radius: Docs.  
  Rollback: Revert docs.  
  Tags: {docs, DX}.  
  Prerequisites: Completion of preceding milestones.  
  Blockers: None.

## Sequencing Notes
- Milestone 1 is prerequisite for all subsequent work; ensures governance and automation guardrails before changing runtime behaviour.
- Milestones 2 & 3 can progress in parallel after foundational CI, with module decomposition preceding major testing/observability changes.
- Security/observability (Milestone 4) depends on typed config and modular utilities to minimize risk.
- Performance/resilience efforts (Milestone 5) build on expanded tests/benchmarks for safe optimisation.
- Release automation (Milestone 6) is last to guarantee stable, observable system prior to automated publishing.

## Risk Management & Communication
- Every task requiring behaviour changes must ship behind feature flags or environment toggles, with documentation in `STATUS.md` and CHANGELOG entries.
- High-risk tasks (module splits, performance refactors) require dedicated ADRs and dry-run artefacts before merge.
- STATUS.md will be updated after each PR summarising progress and next steps.
