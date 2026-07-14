# Quality Audit

## Status Classification

Historical notes in this file are retained for traceability. Authoritative
current public-readiness status is recorded in:

- `docs/operations/PUBLIC_RELEASE_FINAL_VERDICT.md`
- `docs/operations/CLEAN_CLONE_RELEASE_VALIDATION.md`

Current classification:

`PUBLIC BETA CANDIDATE - LOCAL PR VALIDATION AND FINAL MAIN VALIDATION REQUIRED`

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

GitHub Actions run #23 passed against head
`14bcfb545c92fc196911ce4a0b8114f0c16e095b` under Ubuntu and Python 3.11.

Passed hosted checks:

- installation of `.[dev,helpers]`;
- editable imports and CLI smokes outside the checkout;
- Ruff formatting and lint;
- supported mypy surface;
- Bandit, `pip-audit`, and binary-file scan;
- all 176 tests with the 85% coverage threshold enforced;
- documentation-link validation;
- isolated wheel build, installation, imports, and CLI smokes;
- zipapp build and CLI smokes;
- diagnostics snapshot generation;
- quality-report artifact upload.

This resolves the earlier diagnostics and package-discovery failures. The
workflow validates the installed distribution independently of pytest's
repository-root path configuration.

## Security Policy Correction (2026-07-14)

The branch now removes unsupported publication claims from `SECURITY.md` and
`CODE_OF_CONDUCT.md`:

- unverified `security@zscripts.dev` contact removed;
- unverified PGP fingerprint removed;
- fixed response-time promises removed;
- vulnerability reports directed to GitHub private vulnerability reporting;
- no replacement mailbox published without owner confirmation;
- public disclosure of sensitive vulnerability details remains prohibited.

The README now carries the intended classification
`PUBLIC BETA — ACTIVE DEVELOPMENT` and warns that format coverage and automated
redaction are not guarantees.

These documentation-only changes require hosted CI and local release-gate
validation on the complete latest PR head.

## Current Quality Risks

- The complete latest PR #48 head still requires local clean-worktree validation
  because the connector cannot execute the local release commands.
- Tracked-worktree and full-history Gitleaks scans remain part of the final local
  release gate rather than the hosted workflow.
- A final clean-worktree release gate is required on the exact merged `main`
  commit before the visibility change.
- GitHub private vulnerability reporting, CodeQL where eligible, secret scanning,
  push protection, Dependabot alerts, and security updates must be enabled or
  verified after publication.

## Profiling Note

`python -m cProfile -s cumulative cli.py summarize --input examples/python/sample.log`
remains useful for startup profiling. Import-heavy startup is an optimization
area, not a public-release blocker.
