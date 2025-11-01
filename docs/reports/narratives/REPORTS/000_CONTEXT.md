# Environment & Context Summary

## Languages, Frameworks, and Tooling

- **Primary language:** Python 3.10+ (`pyproject.toml` specifies `requires-python >=3.10`; tooling pins 3.11 for nox sessions).
- **Python packaging:** Standard `setuptools` build via `pyproject.toml`; CLI entry point `zscripts.cli:main` exposed through the `zscripts` console script and `python -m zscripts`.
- **Automation & quality tools:** Ruff (lint + formatter), mypy (strict typing), pytest (tests), coverage (configured via `[tool.coverage.run]`), bandit (security scan), nox (automation sessions), pre-commit (listed in `requirements.txt`).
- **Sample stacks:** `examples/sample_project/` includes Python, JavaScript/TypeScript, shell, and YAML files for aggregation demonstrations; no runtime frameworks bundled beyond standard library modules.

## Dependency & Build Management

- **Python dependency managers:** `requirements.txt` enumerates dev tools. The project installs via `pip` against `pyproject.toml`/`setuptools`; editable installs supported.
- **Automation scripts:** `Makefile` exposes `fmt`, `lint`, `type`, `security`, `test`, and aggregate `check` targets; `noxfile.py` defines `tests` and `lint` sessions.
- **Configuration:** Default runtime configuration stored in `configs/zscripts.config.json`, consumed by `zscripts.config` helpers and CLI flags.

## Repository Structure Overview

- `zscripts/` – Core Python package (CLI, config loader, log aggregation helpers, cached templates). Subdirectories include `all/`, `all_single/`, `logs/`, and `zreadme/` assets used during log generation and documentation builds.
- `tests/` – Pytest suite covering CLI behaviors, configuration handling, and regression fixtures; includes temporary working directories under `tests/tmp-case*` (ignored by mypy/bandit).
- `examples/sample_project/` – Demonstration codebase mixing backend/front-end/infrastructure files for collection tests.
- `Makefile`, `noxfile.py`, `requirements.txt`, and `pyproject.toml` – Tooling definitions.
- Documentation and planning artefacts: multiple `EXEC_PLAN_*.md` files, `docs/plans/PROJECT_STATUS_REPORT.md`, `docs/plans/REPORT.md`, and logs inside `examples/artifacts/zscripts_logs/`.

## Conventions & CI Expectations

- **Formatting & linting:** Ruff enforces imports (`I`), style (`E`, `W`), bugbear (`B`), and modernization (`UP`) rules with 100-character line length; `ruff format` used for code formatting.
- **Typing:** mypy runs in strict mode for the package, with explicit overrides allowing untyped tests and Hypothesis modules.
- **Testing:** pytest configured via `pyproject.toml`; coverage tracing enabled for `zscripts` package.
- **Security checks:** `bandit` configured to ignore temp test folders.
- **CI style:** Expect pipelines to run `make check` or equivalent (fmt + lint + type + security + tests) followed by packaging commands; no explicit CI config committed but tooling implies the workflow.

## Notable Environment Variables & Config Paths

- `ZSCRIPTS_CONFIG_PATH` allows overriding the default JSON configuration file (documented in `README.md`).
- CLI flags `--config`, `--project-root`, `--dry-run`, and `--verbose` provide runtime customization.

