# Clean-Clone Release Validation

- Repository: dev-logger-zscripts
- Validation date: 2026-06-29
- Branch: main
- Validated commit SHA: 98cb9ee8cf6d2f6339a2b36e747b083a035ba1f4
- Environment: clean clone with Python 3.14.0

## Objective

Verify that a fresh checkout can install tooling, pass strict quality checks,
and execute the packaged zipapp entry point.

## Validation Steps

```sh
git clone <repo-url>
cd dev-logger-zscripts
python -m pip install --upgrade pip
python -m pip install -e .[dev]
ruff format --check .
ruff check .
mypy zscripts/application zscripts/config.py zscripts/configuration.py zscripts/observability/logging.py zscripts/observability/metrics.py zscripts/observability/health.py zscripts/observability/instrumentation.py zscripts/extensions/scaffolding.py zscripts/schemas
bandit -q -r zscripts examples/sample_project
pip-audit -r requirements.txt
python scripts/no_binaries.py
python -m coverage erase
python -m coverage run -m pytest
python -m coverage report
python scripts/build_artifact.py
python artifacts/build/zscripts.pyz guardrails
```

## Validation Results

- Installation: passed (`python -m pip install -e .[dev]`).
- Formatting: passed (`ruff format --check .` -> 272 files already formatted).
- Lint: passed (`ruff check .` -> all checks passed).
- Type checks: passed (`mypy ...` -> success, no issues in 14 source files).
- Bandit: passed (`bandit -q -r zscripts examples/sample_project`), with no failing findings; informational `nosec` warnings observed.
- Dependency audit: passed (`pip-audit -r requirements.txt` -> no known vulnerabilities; local package `zscripts` skipped as non-PyPI dependency).
- Binary scan: passed (`python scripts/no_binaries.py` -> no binary-like files detected).
- Tests: passed (`python -m coverage run -m pytest` -> 166 collected, 166 passed, 0 failed, 0 skipped).
- Coverage: passed (`python -m coverage report` -> 93% total) against required threshold 85%.
- Build: passed (`python scripts/build_artifact.py` -> `artifacts/build/zscripts.pyz`).
- Packaged CLI smoke test: passed (`python artifacts/build/zscripts.pyz guardrails`) with JSON output including:
  - `dangerous_mode: false`
  - `timeout_seconds: 120`
  - `allowed_paths` rooted at the clean-clone workspace.

## Notes

- This validation is designed to mirror CI behavior for release confidence.
- If GitHub Actions is disabled, this clean-clone run is the authoritative
  release validation record.
