# Quality Audit

## Status Classification

- Historical notes in this file are retained for traceability.
- Authoritative current release readiness is recorded in:
  - `docs/operations/PUBLIC_RELEASE_FINAL_VERDICT.md`
  - `docs/operations/CLEAN_CLONE_RELEASE_VALIDATION.md`

## Historical Snapshot (2026-06-23)

This older run occurred before tooling bootstrap was aligned in the sandbox and
is no longer authoritative for current HEAD.

| Check | Historical Result |
| --- | --- |
| Security (`bandit`) | Failed in that environment due to missing executable. |
| Coverage (`coverage`) | Failed in that environment due to missing module. |

## Current-HEAD Snapshot (2026-07-01, clean clone)

Validated on commit `fd379e40907ed257640dfe5d0faa7cdd9d1cd88f` before final
readiness documentation updates.

| Check | Command | Result |
| --- | --- | --- |
| Format | `ruff format --check .` | Pass (272 files already formatted). |
| Lint | `ruff check .` | Pass. |
| Type | `mypy zscripts/application zscripts/config.py zscripts/configuration.py zscripts/observability/logging.py zscripts/observability/metrics.py zscripts/observability/health.py zscripts/observability/instrumentation.py zscripts/extensions/scaffolding.py zscripts/schemas` | Pass (14 source files). |
| Security (Bandit) | `bandit -q -r zscripts examples/sample_project` | Pass (informational `nosec` warnings only). |
| Dependency audit | `pip-audit -r requirements.txt` | Pass (`zscripts` skipped as local editable package). |
| Binary scan | `python scripts/no_binaries.py` | Pass. |
| Tests | `pytest` | Pass (168 passed). |
| Coverage | `coverage run -m pytest && coverage report --fail-under=85` | Pass (92% total). |
| Build | `python scripts/build_artifact.py` | Pass (`artifacts/build/zscripts.pyz`). |
| Packaged smoke | `python artifacts/build/zscripts.pyz guardrails` | Pass. |
| Packaged adapters smoke | `python artifacts/build/zscripts.pyz adapters --format json` | Pass. |

## Profiling Note

- `python -m cProfile -s cumulative cli.py summarize --input examples/python/sample.log`
  remains useful for startup profiling; import-heavy startup is still an
  optimization area, but not a public-release blocker.
