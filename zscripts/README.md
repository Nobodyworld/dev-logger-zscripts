# zscripts Package

This package contains the runtime, CLI entry point, and supporting utilities for
collecting and analysing project logs.

Key modules:

* `cli.py` – argparse-driven command surface that orchestrates the toolkit.
* `application/` – report formatters, services, and IO helpers used by the CLI.
* `infrastructure/` – adapters, sandboxing, and example handling.
* `observability/` – logging, metrics, tracing, and health check plumbing.
* `extensions/` – extension hooks and scaffolding helpers for custom integrations.

See `docs/architecture/ARCHITECTURE.md` for a detailed breakdown of each module.
