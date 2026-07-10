# Clean-Clone Release Validation

- Repository: `Nobodyworld/dev-logger-zscripts`
- Validation date: 2026-07-08
- Branch context: PR #47 / merged showcase baseline
- Merged `main` baseline: `7d6e03f4674c22401e8d15a57b02f856941fed55`
- Clean-worktree validated source head: `124c1e4f85204aaec76d4f7feafdbd0912513bd7`
- Environment: Windows clean worktree, Python 3.14.0
- Status: `VALIDATED FOR PR #47 - PR #48 AND FINAL MAIN VALIDATION STILL REQUIRED`

## Current PR #48 Revalidation State

GitHub Actions run #8 for PR #48 started successfully and completed the editable
installation, formatting, lint, supported mypy surface, Bandit, dependency audit,
binary scan, and all 176 tests. It then failed while invoking
`scripts/diagnostics_probe.py` directly because the script directory, rather than
the repository root, became Python's import root.

PR #48 now includes the following remediation, which requires a fresh hosted CI
result before merge:

- explicit setuptools discovery for `zscripts*` packages;
- editable-install imports and CLI smokes from outside the repository root;
- isolated wheel build, installation, import, and CLI smokes;
- module-based diagnostics invocation with
  `python -m scripts.diagnostics_probe`;
- hosted coverage enforcement at the existing 85% threshold;
- documentation-link validation and zipapp smoke tests.

This document records the earlier PR #47 clean-worktree evidence. It must not be
used as final evidence for PR #48 or for a visibility change.

## Objective

Verify that a fresh checkout can install tooling, pass strict quality and
security checks, validate adapter inventory behavior, execute packaged CLI smoke
workflows, and prove raw-log report redaction before public showcase use.

## Validation Setup

The authoritative PR #47 validation was run from a clean worktree with the pytest
temp base outside the repository to avoid Windows ACL/stale-temp-directory
artifacts.

Representative setup:

```powershell
python -m pip install --upgrade pip
python -m pip install -e .[dev,helpers]
$base = Join-Path $env:TEMP "zscripts-pytest-$([guid]::NewGuid())"
```

## Validation Steps

```sh
ruff format --check .
ruff check .
python scripts/no_binaries.py
python -m pytest -q --basetemp="$base"
python scripts/validate_docs_links.py
git diff --check
mypy zscripts/application zscripts/config.py zscripts/configuration.py zscripts/observability/logging.py zscripts/observability/metrics.py zscripts/observability/health.py zscripts/observability/instrumentation.py zscripts/extensions/scaffolding.py zscripts/schemas
python -m coverage erase
python -m coverage run -m pytest --basetemp="$base"
python -m coverage report --fail-under=85
python scripts/build_artifact.py
python artifacts/build/zscripts.pyz guardrails
python artifacts/build/zscripts.pyz adapters --format json
python cli.py --adapter ci report --input examples/raw_to_report/raw.log --format markdown --redact --output artifacts/build/raw_to_report_demo.md
python -m bandit -q -r zscripts examples/sample_project
python -m pip_audit
gitleaks detect --no-git --source . --redact --verbose
gitleaks detect --source . --redact --verbose
```

## Validation Results

| Check | Result |
| --- | --- |
| Install | Pass (`python -m pip install -e .[dev,helpers]`) |
| Format | Pass (`ruff format --check .`) |
| Lint | Pass (`ruff check .`) |
| Binary scan | Pass (`python scripts/no_binaries.py`) |
| Tests | Pass (`176 passed, 13 warnings`) |
| Documentation links | Pass (`python scripts/validate_docs_links.py`) |
| Diff whitespace | Pass (`git diff --check`) |
| Type checks | Pass (supported mypy surface) |
| Coverage | Pass (92%, threshold 85%) |
| Build | Pass (`python scripts/build_artifact.py`) |
| Packaged guardrails smoke | Pass |
| Packaged adapter inventory smoke | Pass |
| Raw-log-to-report demo | Pass with supported `python cli.py --adapter ci report ...` order |
| Report redaction scan | Pass; no unredacted fixture or common provider-token patterns |
| Bandit | Pass under Python 3.14.0 |
| Dependency audit | Pass (`python -m pip_audit`) |
| Gitleaks tracked-file scan | Pass |
| Gitleaks full-history scan | Pass |

## Notes

- This record replaces older 2026-07-01 counts and fixture notes.
- PR #47 validation is strong product evidence, but it is not a final public
  release gate for the repository after follow-up code, documentation, and
  configuration changes.
- PR #48 must receive a successful hosted CI result and branch-level local
  validation before merge.
- A final clean-worktree validation must be run against the exact final `main`
  commit immediately before any visibility change.
