# Repo Intelligence Report

_Last updated: 2025-10-19_

## Executive Summary
Zscripts is a Python-first command-line toolkit that inventories source trees, normalises log bundles, and provides audit-ready
artifacts for downstream security and incident response workflows. The repository currently packages a reusable library, a CLI,
polyglot sample data, and extensive developer tooling. While the core feature set is stable, modernization is required to
standardise governance, harden automation, and unlock future refactors with confidence.

## System Overview
### Product Mission & Personas
- **Mission**: Give security, SRE, and compliance teams a deterministic way to capture repository state, classify artefacts by
  technology stack, and export evidence bundles.
- **Primary personas**: Security engineers (log bundles), SREs (filesystem audits), Release managers (pre-flight change review),
  Contributors (local CLI tooling).

### Deployable & Executable Units
| Artifact | Description | Delivery Path |
|----------|-------------|---------------|
| `zscripts` CLI | Entry point for all user interactions (installable via pip). | `python -m zscripts` or console script. |
| Python API | Importable modules (`zscripts.cli`, `zscripts.utils`, `zscripts.config`). | Consumed by automation scripts. |
| Governance bundle | Documentation & policy assets (README, SECURITY, CODEOWNERS, templates). | Repository root. |
| Developer automation | Makefile, Nox sessions, pre-commit hooks, GitHub Actions. | `/Makefile`, `/noxfile.py`, `.github/`. |
| Sample fixture | `sample_project` polyglot monorepo used for integration tests & documentation screenshots. | `/sample_project`. |

### Runtime Architecture & Data Flow
1. **Invocation layer**: Console entry point `zscripts.cli:main` provides subcommands `collect`, `consolidate`, and `tree`, plus
   hidden legacy aliases exposed via `zscripts/all*.py` for backwards compatibility.
2. **Configuration**: `zscripts.config` assembles defaults, CLI arguments, environment variables (`ZSCRIPTS_CONFIG_PATH`), and
   JSON configuration files. Validation is manual; no schema enforcement is in place yet.
3. **Execution**: `zscripts.utils` orchestrates filesystem discovery, ignore pattern resolution, grouping by extension presets
   from `zscripts.presets`, caching helpers in `_cache`, and log emission utilities.
4. **Outputs**: Results are written under `zscripts_logs/` (default) or a caller-defined directory. Dry-run and verbose flags
   pivot output toward stdout via `Reporter` classes.
5. **Observability**: Logging is minimal (stdout/stderr text). There is no structured logging, metrics, or tracing pipeline.

### Repository Topology
```
zscripts/
├─ zscripts/                  # Core library & CLI code
│  ├─ cli.py                  # argparse wiring, dispatch
│  ├─ config.py               # dataclass config + env resolution
│  ├─ utils.py                # traversal, grouping, IO (hotspot)
│  ├─ presets.py              # extension → log bundle mapping
│  ├─ _cache.py               # typed helper around functools.lru_cache
│  ├─ logs/, zreadme.py       # template assets
│  └─ all.py, all_single.py   # legacy compatibility imports
├─ tests/                     # pytest-based unit/integration suites
├─ sample_project/            # integration fixture (polyglot)
├─ docs/adr/                  # historical architecture decisions
├─ Makefile, noxfile.py       # developer automation entry points
├─ .github/workflows/         # CI (lint, test, security scanning)
└─ Governance docs            # README, SECURITY, CONTRIBUTING, etc.
```

### Public Interfaces & CLIs
| Command | Synopsis | Key Flags | Output |
|---------|----------|-----------|--------|
| `zscripts collect` | Capture project artefacts grouped by stack preset. | `--target`, `--dry-run`, `--verbose`. | Files under `zscripts_logs/`. |
| `zscripts consolidate` | Merge disparate artefacts into a compressed bundle. | `--output`, `--include`, `--exclude`. | Consolidated archive / stdout summary. |
| `zscripts tree` | Render filtered directory tree based on presets. | `--preset`, `--depth`, `--format`. | Tree report text. |
| `python -m zscripts` | Mirrors CLI entry point for environments without script installation. | Same as subcommands. | Same as CLI. |

The Python API exposes functions within `zscripts.utils` and configuration helpers for advanced automation scenarios. There are
no background daemons or long-running services.

### Configuration & Data Contracts
- **Primary config**: `zscripts.config.Config` dataclass; accepts CLI args, JSON payloads, and environment overrides.
- **File formats**: JSON presets; log bundles emitted as plaintext or user-defined archives.
- **Environment variables**: `ZSCRIPTS_CONFIG_PATH`, `ZSCRIPTS_OUTPUT_DIR`, optional toggles for dry-run/verbosity.
- **Assumptions**: Local filesystem access, POSIX-like semantics; Windows support requires path sanitation already embedded in
  CLI layer.

## Tech Stack & Dependency Graph
- **Language**: Python 3.10+ (tooling validated on 3.11, target to expand to 3.12).
- **Runtime dependencies**: Standard library only (intentionally zero external runtime deps for supply-chain hygiene).
- **Dev/test/tooling**: Ruff (lint & format), mypy (strict), pytest/pytest-cov, bandit, cyclonedx, gitleaks, pre-commit,
  commitlint, nox, Makefile targets. Node is optionally used for commitlint.
- **Packaging**: `pyproject.toml` with setuptools backend and console script registration; versioning manual.
- **Automation**: `make fmt|lint|type|test|security|check|sbom`; `nox` sessions mirror the Make targets; `.pre-commit-config.yaml`
  enforces formatting and linting locally.
- **CI/CD**: `.github/workflows/ci.yml` runs lint/type/test/security steps on push/PR; `gitleaks.yml` scans secrets; release
  automation is absent.

#### Dependency Graph (condensed)
```
cli        → config, presets, utils, _cache
config     → dataclasses, json, pathlib, os (stdlib)
utils      → pathlib, os, itertools, shutil, presets, _cache
presets    → json, pathlib
_cache     → functools.lru_cache (stdlib)
legacy all → cli, utils
```
Tests exercise CLI/config/utils and rely on `sample_project` fixtures.

### Hotspots, Debt, and Observability Gaps
- **`zscripts/utils.py`**: ~500 LOC orchestrating traversal, filtering, IO, and reporting, mixing concerns without clear
  abstractions. Refactors need guardrails (feature flags, golden tests).
- **Config validation**: Manual parsing yields unclear errors; lacks schema validation and `.env` parity. High leverage fix.
- **Logging**: Reliant on print statements; no structured logs, correlation IDs, or metrics. Limits debuggability.
- **Governance sprawl**: Multiple legacy EXEC_PLAN* docs cause onboarding noise; README does not yet surface modernization
  status.
- **Testing gaps**: Integration coverage limited to CLI argument parsing; no snapshot or performance regression tests.

### Potential Dead Code / Low-Value Assets
- `zscripts/config.json` appears unused (legacy artifact) — confirm via rg/tests before removal.
- `zscripts/logs/*` templates rarely imported; need telemetry to justify retention.
- Legacy wrappers `zscripts/all.py` and `zscripts/all_single.py` are thin proxies; maintain until formal deprecation window.
- Historical planning docs under `EXEC_PLAN_*` and `REPORTS/` duplicate the modern report/plan; candidates for archival.

## Risk Inventory & Mitigations
| Risk | Impact | Likelihood | Mitigation Strategy |
|------|--------|------------|---------------------|
| Monolithic utilities mask regressions. | High | High | Decompose with feature flags, add snapshot tests, enforce coverage gates. |
| Config parsing lacks schema validation. | High | Medium | Introduce typed schema (Pydantic/pydantic-core), document `.env.example`, add validation tests. |
| CI drift between local tooling and GitHub Actions. | Medium | Medium | Align Makefile, pre-commit, and CI to single source of truth (`make check`). |
| Supply-chain visibility (SBOM/secrets). | Medium | Medium | Automate CycloneDX + gitleaks, publish artifacts in CI, document policy. |
| Observability void (no structured logs/metrics). | Medium | Medium | Add structured logging with opt-in flag, adopt OpenTelemetry hooks behind noop default. |
| Release workflow manual and opaque. | Medium | Medium | Implement semantic-release pipeline with dry-run gating, CODEOWNERS review. |
| Sample project drift from real workloads. | Medium | Low | Periodically regenerate fixtures, document expected stacks, add property-based tests. |
| Legacy compatibility modules linger without deprecation plan. | Low | Medium | Introduce deprecation warnings + timeline, communicate in CHANGELOG. |

## Quick Wins (0–2 week ROI)
1. **Governance normalisation** – Link governance docs from README, rationalise templates, ensure CODEOWNERS coverage.
2. **CI matrix & caching** – Expand GitHub Actions to Python 3.10–3.12, add pip caching, upload coverage/security artifacts.
3. **Pre-commit alignment** – Update hooks to match CI, add fast mypy and pytest smoke checks; document in CONTRIBUTING.
4. **SBOM automation** – Run CycloneDX in CI and store artifacts; document dependency update policy in SECURITY.md.
5. **Developer bootstrap** – Provide `make dev`/`make check` workflow, “First Hour Guide”, and local parity notes.

## Top 10 Opportunities by ROI
| # | Opportunity | Expected Impact | Effort | Prerequisites | Tags |
|---|-------------|----------------|--------|---------------|------|
| 1 | Harden governance, CODEOWNERS, CI status checks, and documentation cross-links. | High | Low | None | {DX, docs, reliability} |
| 2 | Align pre-commit & CI (Ruff fmt/check, mypy strict, security scans) with commitlint enforcement. | Medium | Low | #1 | {DX, testing, security} |
| 3 | Typed config schema + `.env.example` parity with feature-flag rollback. | High | Medium | #1–2 | {reliability, security, DX} |
| 4 | Modularise `utils` into traversal/logging/reporting packages with compatibility facade. | High | High | #2–3 | {DX, reliability, performance} |
| 5 | Structured logging & context propagation behind opt-in flag. | Medium | Medium | #3–4 | {reliability, DX} |
| 6 | Golden-path CLI snapshot & regression suite (collect/consolidate/tree). | High | Medium | #2 | {testing, reliability} |
| 7 | Supply-chain automation (SBOM, gitleaks, dependency policy, Renovate). | Medium | Medium | #1 | {security, reliability} |
| 8 | Benchmark & profiling harness to quantify traversal performance. | Medium | Medium | #6 | {performance, testing} |
| 9 | Semantic release pipeline (semantic versioning, signed artefacts, changelog automation). | High | Medium | #1, #7 | {DX, reliability} |
| 10 | Feature-flag strategy for legacy wrappers with published deprecation timeline. | Medium | Medium | #3–4 | {DX, reliability} |

## Evidence & Next Steps
- `STATUS.md` will capture progress per PR with risk/rollback notes.
- New ADRs will document high-impact decisions (module decomposition, schema selection, observability strategy).
- Metrics to instrument during modernization: CLI execution duration, file count processed, log size, validation error rates.
- Target success criteria: ≥85% coverage on core modules, CI runtime <10 minutes, zero manual release steps, developer setup in
  <5 minutes.
