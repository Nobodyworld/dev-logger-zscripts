# Clean-Clone Release Validation

- Repository: `Nobodyworld/dev-logger-zscripts`
- Validation date: 2026-07-08
- Branch context: PR #47 / merged showcase baseline
- Merged `main` baseline: `7d6e03f4674c22401e8d15a57b02f856941fed55`
- Clean-worktree validated source head: `124c1e4f85204aaec76d4f7feafdbd0912513bd7`
- Environment: Windows clean worktree, Python 3.14.0
- Status: `VALIDATED FOR PR #47 - PR #48 LOCAL AND FINAL MAIN VALIDATION STILL REQUIRED`

## PR #48 Hosted Revalidation

GitHub Actions run #20 passed against the packaging and CI hardening head
`8b80c74d974658ae6d6480c3c171bba6f7507e9d` under Ubuntu and Python 3.11.

The hosted gate completed successfully:

- installation of `.[dev,helpers]`;
- editable-package imports and CLI smokes outside the repository root;
- Ruff formatting and lint;
- the supported mypy surface;
- Bandit, dependency audit, and binary-file scan;
- all 176 tests with the 85% coverage threshold enforced;
- documentation-link validation;
- isolated wheel build, installation, imports, and CLI smokes;
- zipapp build and CLI smokes;
- diagnostics snapshot generation;
- quality-report artifact upload.

This resolves the earlier run #8 diagnostics failure. Run #8 had passed all 176
tests but failed because `scripts/diagnostics_probe.py` was invoked directly,
which made the script directory rather than the repository root the import root.
The workflow now uses `python -m scripts.diagnostics_probe`, and package
discovery explicitly includes the runtime `zscripts`, `adapters`, `agents`, and
`scripts` package trees.

The hosted result is strong branch evidence, but this document still records the
earlier PR #47 Windows clean-worktree run. The complete latest PR #48 head must
receive local clean-worktree validation before merge, and the exact merged
`main` SHA must be validated again before any visibility change.

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
- Hosted CI is green for PR #48's packaging and workflow changes.
- The complete latest PR #48 head still requires local clean-worktree validation.
- A final clean-worktree validation must be run against the exact final `main`
  commit immediately before any visibility change.
