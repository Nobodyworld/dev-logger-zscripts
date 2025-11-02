# Repository Specification – dev-logger-zscripts

_Last updated: 2025-02-15_

## Overview

Zscripts is a Python 3.11 toolkit that aggregates logs, normalises them through a
schema, and generates reports for automation workflows. The project centres on
the `zscripts` package (CLI, runtime services, observability) with supporting
adapters, agent metadata, and developer scripts. The repository now follows a
clean separation between runtime code, documentation, configuration, examples,
and automation assets.

## Tech Stack

- **Language:** Python 3.11+
- **Packaging:** `pyproject.toml` with optional `.[dev]` extras
- **Testing:** `pytest`
- **Linting & Formatting:** `ruff`
- **Type Checking:** `mypy` (strict defaults, per-module overrides allowed)
- **Security Scanning:** `bandit`
- **Task Tracking:** `TASKLIST.md`

## Key Components

- `zscripts/` – Core runtime with the CLI (`cli.py`), configuration helpers,
  operations, observability, and extension scaffolding.
- `adapters/` – Language-specific integrations that expose project structures to
  the toolkit.
- `agents/` – Automation helpers that describe the CLI surface for AI agents.
- `scripts/` – Developer utilities for scaffolding modules, collecting quality
  metrics, and managing releases.
- `configs/zscripts.config.json` – JSON mirror of default configuration values
  for legacy consumers.
- `docs/INDEX.md` – Entry point to architecture notes, guides, automation plans,
  and release history.

## Workflows

- **Install:** `pip install .[dev]`
- **Check-only:** `make check` (runs formatting, linting, mypy, bandit, pytest)
- **Tests:** `pytest`
- **Type checks:** `mypy zscripts agents scripts`
- **Lint:** `ruff check`

Developers should keep `CHANGELOG.md`, `README.md`, and `TASKLIST.md` up to date
when shipping notable changes.

## Configuration

- Runtime defaults originate from `zscripts/config.py`.
- JSON configuration (`configs/zscripts.config.json`) mirrors legacy settings for
  scripts that expect a file-based configuration source.
- CLI invocations accept `--config` (TOML/JSON) and `--set key=value` overrides.

## Documentation

- `README.md` – Quickstart and development workflow.
- `docs/architecture/ARCHITECTURE.md` – Module responsibilities and extension
  guidance.
- `docs/guides/` – How-to documents for adapters, extensions, and automation.
- `STYLE-GUIDE.md` – Organisation-wide coding conventions.
- `SUPPORT.md` / `SECURITY.md` – Operational contacts and reporting process.

## Quality Expectations

- Maintain 100% passing status for `pytest`, `ruff check`, and `mypy zscripts agents scripts`.
- Avoid committing generated artifacts outside of the `artifacts/` hierarchy.
- Every directory at the repository root (and major runtime packages) includes a
  `README.md` describing its purpose.
- Tasks must be logged and closed in `TASKLIST.md` using the documented format.

## Contacts

- Maintainers: Zscripts Maintainers (see `pyproject.toml`)
- Support: See `SUPPORT.md`
- Security: See `SECURITY.md`
