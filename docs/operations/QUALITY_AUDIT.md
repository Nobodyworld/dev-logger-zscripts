# Quality Audit

## Status Classification

- Historical notes in this file are retained for traceability.
- Authoritative current public-readiness status is recorded in:
  - `docs/operations/PUBLIC_RELEASE_FINAL_VERDICT.md`
  - `docs/operations/CLEAN_CLONE_RELEASE_VALIDATION.md`

Current classification:

`KEEP PRIVATE - HOSTED CI REVALIDATION AND FINAL MAIN VALIDATION REQUIRED`

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
| Type | supported mypy release surface | Pass. |
| Coverage | `coverage run -m pytest && coverage report --fail-under=85` | Pass (92% total). |
| Build | `python scripts/build_artifact.py` | Pass. |
| Packaged smoke | `python artifacts/build/zscripts.pyz guardrails` | Pass. |
| Packaged adapters smoke | `python artifacts/build/zscripts.pyz adapters --format json` | Pass. |
| Raw-log report demo | supported adapter-first CLI invocation | Pass. |
| Report redaction scan | provider-token / fixture pattern scan against generated report | Pass. |
| Security (Bandit) | `python -m bandit -q -r zscripts examples/sample_project` | Pass under Python 3.14.0. |
| Dependency audit | `python -m pip_audit` | Pass. |
| Secret scan (tracked) | `gitleaks detect --no-git --source . --redact --verbose` | Pass. |
| Secret scan (history) | `gitleaks detect --source . --redact --verbose` | Pass. |

## PR #48 Hosted CI Evidence

GitHub Actions run #8 started normally and produced job-level evidence. The
following checks passed under Ubuntu and Python 3.11:

- editable installation with `.[dev,helpers]`;
- Ruff formatting and lint;
- supported mypy surface;
- Bandit, `pip-audit`, and the binary-file scan;
- all 176 pytest tests.

The run then failed in the diagnostics snapshot step with
`ModuleNotFoundError: No module named 'zscripts'` because the helper was invoked
as a direct file path. PR #48 now remediates that failure and strengthens the
hosted gate with explicit package discovery, editable and isolated-wheel
installation smokes, module-based diagnostics invocation, coverage enforcement,
documentation-link validation, and zipapp smokes.

A fresh hosted run is required. The prior passing steps are useful evidence but
do not make the latest branch green.

## Current Quality Risks

- The latest PR #48 changes have not yet received a successful hosted CI result.
- The full PR #48 branch still requires local clean-worktree validation because
  the connector cannot execute the release commands.
- CodeQL, GitHub Secret Protection, and push protection are deferred until the
  repository is public or the account has private-repository coverage.
- Tracked-file and full-history Gitleaks scans remain part of the final local
  release gate rather than the hosted workflow.
- A final clean-worktree release gate is still required on the exact final
  `main` commit before repository visibility changes.

## Profiling Note

- `python -m cProfile -s cumulative cli.py summarize --input examples/python/sample.log`
  remains useful for startup profiling; import-heavy startup is still an
  optimization area, but not a public-release blocker.
