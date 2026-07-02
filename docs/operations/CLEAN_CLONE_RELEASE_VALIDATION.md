# Clean-Clone Release Validation

- Repository: dev-logger-zscripts
- Validation date: 2026-07-01
- Branch: main
- Validated commit SHA: fd379e40907ed257640dfe5d0faa7cdd9d1cd88f
- Environment: clean clone with Python 3.14.0

## Objective

Verify that a fresh checkout can install tooling, pass strict quality and
security checks, validate adapter inventory behavior, and execute packaged CLI
smoke workflows.

## Validation Steps

```sh
git clone <repo-url>
cd dev-logger-zscripts
python -m pip install --upgrade pip
python -m pip install -e .[dev,helpers]
ruff format --check .
ruff check .
mypy zscripts/application zscripts/config.py zscripts/configuration.py zscripts/observability/logging.py zscripts/observability/metrics.py zscripts/observability/health.py zscripts/observability/instrumentation.py zscripts/extensions/scaffolding.py zscripts/schemas
bandit -q -r zscripts examples/sample_project
pip-audit -r requirements.txt
python scripts/no_binaries.py
python -m detect_secrets scan --force-use-all-plugins $(git ls-files)
python -m coverage erase
python -m coverage run -m pytest
python -m coverage report --fail-under=85
python scripts/build_artifact.py
python artifacts/build/zscripts.pyz guardrails
python artifacts/build/zscripts.pyz adapters --format json
python cli.py report --input examples/raw_to_report/raw.log --format markdown --redact --output artifacts/build/raw_to_report_demo.md
python scripts/validate_docs_links.py
```

## Validation Results

- Installation: passed (`python -m pip install -e .[dev,helpers]`).
- Formatting: passed (`ruff format --check .` -> 272 files already formatted).
- Lint: passed (`ruff check .` -> all checks passed).
- Type checks: passed (`mypy ...` -> success, no issues in 14 source files).
- Bandit: passed (`bandit -q -r zscripts examples/sample_project`), with no failing findings; informational `nosec` warnings observed.
- Dependency audit: passed (`pip-audit -r requirements.txt` -> no known vulnerabilities; local package `zscripts` skipped as non-PyPI dependency).
- Binary scan: passed (`python scripts/no_binaries.py` -> no binary-like files detected).
- Secret scan (HEAD tracked files): passed with no verified credentials; fixture placeholders flagged in example docker-compose sample.
- Tests: passed (`pytest` and `python -m coverage run -m pytest` -> 168 collected, 168 passed, 0 failed, 0 skipped).
- Coverage: passed (`python -m coverage report --fail-under=85` -> 92% total) against required threshold 85%.
- Build: passed (`python scripts/build_artifact.py` -> `artifacts/build/zscripts.pyz`).
- Packaged CLI smoke test: passed (`python artifacts/build/zscripts.pyz guardrails`) with JSON output including:
  - `dangerous_mode: false`
  - `timeout_seconds: 120`
  - `allowed_paths` rooted at the clean-clone workspace.
- Packaged adapter inventory smoke: passed (`python artifacts/build/zscripts.pyz adapters --format json`) with deterministic identifier order: `ci, docker, dotnet, go, java, javascript, python, rust`.
- Raw-log-to-report demo: passed (`python cli.py report --input examples/raw_to_report/raw.log --format markdown --redact --output artifacts/build/raw_to_report_demo.md`).
- Documentation-link validation: passed (`python scripts/validate_docs_links.py`).

## Notes

- This validation is designed to mirror CI behavior for release confidence.
- If GitHub Actions is disabled, this clean-clone run is the authoritative
  release validation record.
