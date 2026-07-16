# Operational Baseline

## Runtime Summary
- Python interpreter: 3.11.12 (`python --version`).
- Pip tooling: 25.2 (`pip --version`).
- Primary CLI entry point: `python cli.py` delegating to `zscripts.cli.main()`.

## Automation Surface
- Make targets: formatting (`fmt`), linting (`lint`), typing (`type`), security scan (`security`), unit tests (`test`), coverage export (`coverage`), quality gate (`quality`), SBOM generation (`sbom`).
- Developer scripts: bootstrap/install helpers, diagnostics probes, sandbox utilities, release helpers, and scaffolding tooling located under `scripts/`.

## CI Configuration
- GitHub Actions workflow `CI` executes the quality gate on pushes to `main` and pull requests.
- Steps: checkout, Python 3.11 setup, editable install with `.[dev]`, run `python scripts/dev_start.py`, capture diagnostics via `scripts/diagnostics_probe.py`, and upload `reports/` artifacts.

## Environment Controls
- `QUALITY_COVERAGE_MIN`: minimum acceptable coverage percentage honoured by `scripts/dev_start.py` when running the quality gate.

## Dependency & License Inventory
- Runtime package declares no mandatory dependencies (`pyproject.toml`).
- Dev/test toolchain:
  - `pytest` 8.4.1 — MIT license.
  - `ruff` 0.12.11 — license metadata unavailable in the local wheel.
  - `mypy` 1.17.1 — MIT license.
  - `bandit` — not present in the current environment; install required for security scans.
  - `coverage` — available via `coverage[toml]` extra once dependencies are installed.
