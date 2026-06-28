# Clean-Clone Release Validation

- Repository: dev-logger-zscripts
- Validation date: 2026-06-27
- Branch: main
- Environment: clean clone with Python 3.11

## Objective

Verify that a fresh checkout can install tooling, pass strict quality checks,
and execute the packaged zipapp entry point.

## Validation Steps

```sh
git clone <repo-url>
cd dev-logger-zscripts
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
ruff format --check .
ruff check .
mypy zscripts/application zscripts/config.py zscripts/configuration.py zscripts/observability/logging.py zscripts/observability/metrics.py zscripts/observability/health.py zscripts/observability/instrumentation.py zscripts/extensions/scaffolding.py zscripts/schemas
bandit -q -r zscripts examples/sample_project
pip-audit
pytest
python scripts/build_artifact.py
python artifacts/build/zscripts.pyz guardrails
```

## Expected Results

- Quality tools complete without skipped mandatory steps.
- Security scans complete and report actionable failures when present.
- Test suite passes.
- Zipapp launches and prints guardrail JSON including `allowed_paths`.

## Notes

- This validation is designed to mirror CI behavior for release confidence.
- If GitHub Actions is disabled, this clean-clone run is the authoritative
  release validation record.
