# Clean-Clone Release Validation

## Current Record

- Classification: `PUBLIC BETA — ACTIVE DEVELOPMENT`
- Repository visibility: public
- Final locally validated SHA: `399792b687549ea97e9319ad9728c7494a0c7ede`
- PR #48 squash merge: `b90a0eefe481c8920f9c413731df3289df75749a`
- PR #53 squash merge: `399792b687549ea97e9319ad9728c7494a0c7ede`

The clean Windows gate at the final SHA passed with Python 3.14.0: 176 tests,
13 known deprecation warnings, 92% coverage, pre-commit, Ruff, supported mypy,
Bandit, dependency audit, binary scan, documentation links, editable/wheel/
zipapp smokes, diagnostics, redaction, and Gitleaks worktree/history scans.
This evidence does not describe a stable release.

## Current Hosted State

Public run `29454174475` failed in `quality` because `pip-audit` detected
`PYSEC-2026-3447` in runner-installed `setuptools 79.0.1`; 83.0.0 is the fixed
version. Bandit completed first. The combined shell stopped before the binary
scan and all later gates. The hardening PR preserves the required context
`quality`, constrains setuptools to the fixed release, and separates the three
security commands for diagnostics. Public run `29879401419`, job `88796699682`,
then completed the full `quality` job successfully on commit
`4b59291ac5bdcef281db2ff112e0aff2307824fc`.

## Reproduction Gate

Use a clean clone or disposable worktree and a fresh virtual environment. Keep
pytest temporary data outside the checkout when platform ACLs require it.

```text
python -m pip install --upgrade pip
python -m pip install -e ".[dev,helpers]"
python -m pip check
pre-commit run --all-files
ruff format --check .
ruff check .
python scripts/no_binaries.py
python -m pytest -q
python scripts/validate_docs_links.py
git diff --check
```

Run mypy on the supported surface listed in `.github/workflows/ci.yml`, then run
coverage with `--fail-under=85`, Bandit, and `pip-audit`. Build an isolated
wheel and verify imports for `zscripts`, `jsonschema`, `adapters`, `agents`, and
`scripts` from outside the checkout. Smoke both console entry points, confirm
adapter ordering, build and smoke the zipapp, and run the existing diagnostics
and redaction release gates.

Run both secret scans:

```text
gitleaks detect --no-git --source . --redact --verbose
gitleaks detect --source . --redact --verbose
```

## Historical Evidence

PR #47 and the pre-merge PR #48 validations remain useful historical snapshots,
but their former publication sequence is complete. PRs #48 and #53 were
squash-merged and the repository is public. Future release decisions must use
the current branch SHA and current hosted result rather than those older
candidate-state instructions.
