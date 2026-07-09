# Quality Audit

## Status Classification

- Historical notes in this file are retained for traceability.
- Authoritative current public-readiness status is recorded in:
  - `docs/operations/PUBLIC_RELEASE_FINAL_VERDICT.md`
  - `docs/operations/CLEAN_CLONE_RELEASE_VALIDATION.md`

Current classification:

`KEEP PRIVATE - FINAL PUBLIC SHOWCASE VALIDATION REQUIRED`

## Historical Snapshot (2026-06-23)

This older run occurred before tooling bootstrap was aligned in the sandbox and
is no longer authoritative for current HEAD.

| Check | Historical Result |
| --- | --- |
| Security (`bandit`) | Failed in that environment due to missing executable. |
| Coverage (`coverage`) | Failed in that environment due to missing module. |

## PR #47 Clean-Worktree Snapshot (2026-07-08)

Validated source head: `124c1e4f85204aaec76d4f7feafdbd0912513bd7`  
Merged showcase baseline: `7d6e03f4674c22401e8d15a57b02f856941fed55`

| Check | Command | Result |
| --- | --- | --- |
| Format | `ruff format --check .` | Pass. |
| Lint | `ruff check .` | Pass. |
| Binary scan | `python scripts/no_binaries.py` | Pass. |
| Tests | `python -m pytest -q --basetemp=<external-temp>` | Pass (`176 passed, 13 warnings`). |
| Docs links | `python scripts/validate_docs_links.py` | Pass. |
| Diff whitespace | `git diff --check` | Pass. |
| Type | `mypy zscripts/application zscripts/config.py zscripts/configuration.py zscripts/observability/logging.py zscripts/observability/metrics.py zscripts/observability/health.py zscripts/observability/instrumentation.py zscripts/extensions/scaffolding.py zscripts/schemas` | Pass. |
| Coverage | `coverage run -m pytest && coverage report --fail-under=85` | Pass (92% total). |
| Build | `python scripts/build_artifact.py` | Pass. |
| Packaged smoke | `python artifacts/build/zscripts.pyz guardrails` | Pass. |
| Packaged adapters smoke | `python artifacts/build/zscripts.pyz adapters --format json` | Pass. |
| Raw-log report demo | `python cli.py --adapter ci report --input examples/raw_to_report/raw.log --format markdown --redact --output artifacts/build/raw_to_report_demo.md` | Pass. |
| Report redaction scan | provider-token / fixture pattern scan against generated report | Pass. |
| Security (Bandit) | `python -m bandit -q -r zscripts examples/sample_project` | Pass under Python 3.14.0. |
| Dependency audit | `python -m pip_audit` | Pass. |
| Secret scan (tracked) | `gitleaks detect --no-git --source . --redact --verbose` | Pass. |
| Secret scan (history) | `gitleaks detect --source . --redact --verbose` | Pass. |

## Current Quality Risks

- Hosted GitHub Actions reported `startup_failure` for the validated PR head and
  produced no job-level evidence.
- CodeQL, GitHub Secret Protection, and push protection are deferred until the
  repository is public or the account has private-repository coverage.
- Follow-up CI/Dependabot/Gitleaks configuration hardening must be locally
  validated after merge.
- A final clean-worktree release gate is still required on the exact final
  `main` commit before repository visibility changes.

## Profiling Note

- `python -m cProfile -s cumulative cli.py summarize --input examples/python/sample.log`
  remains useful for startup profiling; import-heavy startup is still an
  optimization area, but not a public-release blocker.
