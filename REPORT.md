# Repo Intelligence Report

## System Overview
- **Domains**: Source aggregation and documentation support for multi-language repositories. Core responsibilities include scanning project trees, grouping files by stack, and emitting per-stack logs or consolidated bundles.
- **Primary Modules**:
  - `zscripts.cli`: Argparse-based entrypoint (`python -m zscripts` / `zscripts` console script). Orchestrates config loading, validates filesystem targets, and dispatches to util functions. Provides dry-run/reporting helpers.
  - `zscripts.config`: JSON-backed configuration schema with immutability guarantees. Exposes `Config` dataclass, default path resolution, and environment-variable override (`ZSCRIPTS_CONFIG_PATH`).
  - `zscripts.utils`: 500+ line module handling filesystem traversal, ignore pattern parsing (gitignore aware), grouping by app, log writing, and repository tree emission. Hosts reusable primitives for both CLI and legacy wrappers.
  - Legacy wrappers (`zscripts/all`, `zscripts/all_single`): Thin modules that import CLI helpers to preserve historic module-level entry points.
  - Packaging glue (`__main__.py`, `_cache.py`, `presets.py`): Provide typed LRU cache decorator and extension maps used by CLI/options.
- **Data Flow**:
  1. CLI parses arguments → resolves project root (walks up to git root/pyproject) → loads JSON config.
  2. Config is hydrated via `load_config`/`resolve_paths`, ensuring log directories and filenames are canonical.
  3. CLI invokes utils (`collect_app_logs`, `consolidate_files`, `create_filtered_tree`) which iterate the filesystem, using ignore patterns + extension maps from `presets`.
  4. Outputs materialize as per-directory log files, consolidated bundles, or textual tree snapshots under configured directories.
- **Public APIs/CLIs/Jobs**:
  - Console script `zscripts` / module `python -m zscripts` with subcommands `collect`, `consolidate`, `tree` (support `--dry-run`, `--verbose`).
  - Legacy module APIs (`from zscripts.all import all_both` etc.) kept for backwards compatibility.
  - No background jobs or services; tooling is CLI-focused.

## Tech Stack & Dependency Graph
- **Runtime**: Python 3.10–3.12, standard library only. No third-party runtime deps.
- **Tooling**: Ruff (lint+format), mypy (strict), pytest (unit/property tests), bandit (security scan), nox & make for task runners.
- **Artifacts**: README generated from `zscripts/zreadme`, sample project mixing Python/JS/CSS/YAML for integration coverage.
- **Dependency Graph**:
  - `cli` → (`config`, `presets`, `utils`, `_cache`).
  - `utils` → (`pathlib`, `itertools`, `fnmatch`, `json`, `re`, `_cache` minimal) and uses helper functions defined internally; shared with legacy wrappers.
  - `config` → (`json`, `pathlib`, `typing`).
  - Legacy wrappers → (`cli`).
- **Hotspots**:
  - `zscripts/utils.py` (505 LOC, multi-responsibility) lacks module partitioning, making typing and targeted tests harder.
  - CLI argument parsing includes custom validation logic that could benefit from schema validation to reduce bespoke code.
- **Dead Code Signals**:
  - `zscripts/all_single` exports near-identical wrappers; tests ensure they import without raising but do not exercise functionality. Consider deprecating behind flag after migration plan.
  - No direct references to `zscripts/config.json` (appears legacy). Verify before removal.

## Risks & Quick Wins
- **Risks**:
  - Single, monolithic util module increases chance of regression when introducing typing/observability.
  - Absence of automated CI/CD or pre-commit allows style drift and security regressions.
  - Configuration validation is bespoke; malformed JSON/structure failures surface late in CLI execution.
  - Lack of SBOM/lockfile management can mask supply-chain exposure once deps are added.
  - Observatory gap (no logging/tracing/metrics) reduces diagnosability for large repositories.
- **Quick Wins**:
  - Introduce GitHub Actions pipeline running `make check` across supported Python versions.
  - Add repository-level governance docs/templates (CONTRIBUTING, SECURITY, CODEOWNERS) for onboarding consistency.
  - Establish pre-commit hooks aligning with Ruff/black (or Ruff format) + mypy/pytest smoke.
  - Generate SBOM via `syft` or `cyclonedx-bom` in CI for future dependencies.
  - Create `.env.example` capturing config-related environment variables.

## Top 10 Opportunities by ROI
1. **Governance & CI Foundations** – Add CODEOWNERS, contributing guide, issue/PR templates, EditorConfig, conventional commit validation, and GitHub Actions for lint/type/test. *(Tags: DX, reliability, testing, docs)*
2. **Pre-commit Automation** – Ship pre-commit config orchestrating Ruff format/lint, mypy, pytest --fast. Ensures consistent developer workflows. *(DX, testing)*
3. **Typed Config Schema** – Introduce pydantic/dataclasses JSON schema validation to catch config drift early; add `.env.example` & runtime validation. *(Reliability, security)*
4. **Module Decomposition** – Break `utils.py` into focused modules (filesystem traversal, tree rendering, collectors) with explicit interfaces. Improves maintainability and testability. *(DX, performance)*
5. **Strict Typing Coverage** – Expand typing to legacy wrappers, remove loose `Any`, enforce mypy across repo including tests where feasible. *(DX, reliability)*
6. **Observability Layer** – Add structured logging hooks, metrics counters (e.g., OpenTelemetry logging exporter), and debug tracing of file traversal counts. *(Observability, reliability)*
7. **Test Pyramid Expansion** – Add integration fixtures for large projects, golden-file tests for CLI output, and performance regression benchmarks. *(Testing, performance)*
8. **Security Tooling** – Integrate Gitleaks/Trivy secret & dependency scanning, add Renovate for automated dependency updates. *(Security)*
9. **Release Automation** – Configure semantic-release (or changesets) to publish wheels/archives with signed artifacts and generated CHANGELOG. *(DX, reliability)*
10. **Performance Profiling & Caching** – Add benchmarking harness + instrumentation for traversal functions; explore multiprocessing or path memoization for large repos. *(Performance)*
