# Quality Audit

## Automated Checks

| Check | Command | Result |
| --- | --- | --- |
| Format | `make fmt` | Pass – Ruff reformatted 30 files. |
| Lint | `make lint` | Pass – Ruff reported no violations. |
| Type | `make type` | Pass – mypy succeeded across 14 modules. |
| Security | `make security` | Failed – `bandit` executable missing in sandbox (install required). |
| Tests | `make test` | Pass – Pytest ran 151 tests (all passed). |
| Coverage | `make coverage` | Failed – `coverage` module unavailable; install `coverage[toml]`. |
| Build | `make build` | Pass – zipapp created at `artifacts/build/zscripts.pyz`. |
| Deploy Smoke | `make deploy` | Pass – zipapp guardrails run emitted JSON snapshot. |

## Profiling

- `python -m cProfile -s cumulative cli.py summarize --input examples/python/sample.log` completed in ~0.21s (105k calls); CLI
  module import dominates cumulative time, indicating opportunities to lazily load adapters when optimizing startup.

