# CLI output safety and supply-chain hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

We will harden zscripts' CLI so that operators receive immediate, actionable errors when they point tree and consolidate commands at unwritable or suspicious destinations. In parallel we will add baseline supply-chain controls (SBOM generation and secret scanning) so every release surfaces dependency metadata and rejects leaked credentials. After this change, a maintainer can run `zscripts tree --output /restricted` and see a helpful error before any traversal happens, and CI will fail if a secret is committed or if the SBOM build breaks.

## Progress

- [x] (2025-01-27 18:00Z) Draft ExecPlan after reviewing CLI path handling, Makefile, and CI workflows.
- [x] (2025-01-27 18:35Z) Added `ensure_writable_path` helper with unit coverage in `tests/test_cli_security.py`.
- [x] (2025-01-27 18:40Z) Routed consolidate/tree commands through the helper and expanded security-focused CLI tests.
- [x] (2025-01-27 18:55Z) Added `make sbom` target, dev dependency, and artifact ignore rules.
- [x] (2025-01-27 19:05Z) Extended pre-commit with detect-secrets, added `.secrets.baseline`, introduced gitleaks CI job, and generated ADR/docs updates.
- [x] (2025-01-27 19:15Z) Updated README/CONTRIBUTING, recorded ADR 20250127, and appended docs/plans/STATUS.md summary.
- [x] (2025-01-27 19:25Z) Ran pytest, ruff, mypy; documented `make sbom`/`pre-commit` network limitations for final reporting.

## Surprises & Discoveries

- Observation: Unable to install `cyclonedx-bom` from PyPI during development due to restricted network egress.
  Evidence: `pip install cyclonedx-bom` returned proxy 403 failures in the container.
- Observation: `pre-commit run --all-files` cannot fetch hook repositories in the sandboxed environment.
  Evidence: Git fetch for `ruff-pre-commit` failed with HTTP 403 when initializing hooks.

## Decision Log

- Decision: Commit a handcrafted `.secrets.baseline` seeded with default detector configuration to unblock detect-secrets integration under offline development constraints.
  Rationale: Without internet access we could not run `detect-secrets scan`, so we recorded the baseline structure manually and documented regeneration steps.
  Date/Author: 2025-01-27 / Assistant

## Outcomes & Retrospective

- Pending implementation.

## Context and Orientation

`zscripts/cli.py` orchestrates the user-facing commands. It already calls `_ensure_output_path` for `consolidate` but leaves `tree` paths unchecked and does not guard against paths escaping the configured log root. `zscripts/utils.py` implements filesystem helpers; we can safely extend it with shared path validation logic. Tests for CLI behaviors live in `tests/test_cli.py` and `tests/test_cli_security.py`. CI is defined in `.github/workflows/ci.yml` and uses `make` targets from the root `Makefile`. Tooling dependencies are documented in `requirements.txt`.

## Plan of Work

First, introduce a helper (likely in `zscripts/utils.py`) that validates an intended output path: it should create parent directories if absent, ensure the target is not a directory when a file is expected, confirm writability, and optionally assert that the resolved path stays within an allowed root. Write focused unit tests in `tests/test_cli_security.py` or `tests/test_cli.py` that simulate unwritable directories using temporary paths to ensure the CLI exits early with descriptive errors.

Next, integrate this helper into both `consolidate_command` and `tree_command` in `zscripts/cli.py`, replacing ad-hoc logic. Ensure error handling surfaces `PermissionError` or `RuntimeError` with clear text and consistent logging (reuse existing `ERROR_ID_RUNTIME`). Update tests to cover success and failure flows, including streaming to stdout to confirm unaffected behavior.

Then, augment the developer tooling. Add a `sbom` make target in `Makefile` that invokes `cyclonedx-py` to generate JSON and XML manifests under `artifacts/sbom/`. Include `cyclonedx-bom` in `requirements.txt`. Extend `.github/workflows/ci.yml` with a job or steps that run the new target and upload artifacts. For local enforcement, update `.pre-commit-config.yaml` to include `detect-secrets` scanning and add a repository-level baseline file if necessary; document baseline regeneration in CONTRIBUTING. In CI, run `gitleaks` via the maintained GitHub Action to catch committed secrets without requiring local installation.

Finally, document the new workflow in README/CONTRIBUTING and append a docs/plans/STATUS.md entry summarizing the PR. Capture the security tooling adoption in a new ADR (`docs/adr/YYYYMMDD-supply-chain-hardening.md`). Ensure validation instructions cover `make sbom`, `pre-commit run --all-files`, `pytest`, and `mypy`.

## Concrete Steps

1. Add path validation helper and tests.
2. Integrate helper into CLI commands with logging adjustments.
3. Update Makefile, requirements, and CI/pre-commit configs for SBOM and secret scanning.
4. Add documentation updates (README, CONTRIBUTING) and create ADR.
5. Update docs/plans/STATUS.md with summary and next steps.
6. Run ruff, mypy, pytest, pre-commit; ensure `make sbom` works locally.

## Validation and Acceptance

- Running `pytest` should include new tests verifying CLI errors for unwritable paths.
- `mypy` and `ruff` must pass without suppressions.
- `make sbom` should create `artifacts/sbom/sbom.json` and `artifacts/sbom/sbom.xml`.
- `pre-commit run --all-files` should pass, including detect-secrets.
- CI workflow should include SBOM generation step and gitleaks secret scanning job.

## Idempotence and Recovery

The path validation helper will be idempotent—creating directories if absent and reusing them otherwise. `make sbom` can be run repeatedly; it overwrites artifacts safely. If SBOM generation fails, rerun after installing dependencies. Pre-commit baselines can be regenerated using documented commands.

## Artifacts and Notes

We will produce SBOM files under `artifacts/sbom/` and update documentation to reference them. Test fixtures will use `tmp_path` to simulate restricted directories without modifying real files.

## Interfaces and Dependencies

- New helper function exported from `zscripts/utils.py` (e.g., `ensure_writable_path` returning `Path`).
- CLI commands `consolidate_command` and `tree_command` must call the helper prior to writing outputs.
- Makefile `sbom` target depends on `cyclonedx-bom` CLI (`cyclonedx-py`).
- Pre-commit uses `detect-secrets`; CI uses `zricethezav/gitleaks-action@v2`.
