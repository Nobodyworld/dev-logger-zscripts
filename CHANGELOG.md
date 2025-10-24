# Changelog

## [Unreleased]
### Added
- Architecture, API, workflow, dependency, and final summary documentation under `docs/` to support the Codex refinement chain.
- README usage walkthroughs and CLI help examples for common collection flows.
- Strict linting, typing, security scanning, and property tests wired into `make check` and pre-commit hooks.
- Structured logging with error identifiers across CLI utilities and the sample database manager.
- Hypothesis-based regression tests covering CLI parsers and ignore pattern expansion.
- `--dry-run` and `--verbose` flags across CLI commands plus utilities for planning log generation and tree previews.
- `--max-bytes` and `--output -` flags enabling tree and consolidate commands to stream artifacts directly to STDOUT.
- Environment variable override (`ZSCRIPTS_CONFIG_PATH`) for pointing the CLI at alternative configuration files.
- Centralised preset registry under `zscripts/presets.py` with serialisable metadata.
- Agent adapter module (`agents/cli_adapter.py`) that exports CLI command schemas and presets for automation.
- Tests covering output-path validation and agent metadata payloads.

### Changed
- ToolkitService now caches sandbox runners and validates sandbox command sequences before execution.
- CLI collect handler surfaces friendly error messages (exit code 2) when log sources are missing or malformed.
- Sample project models refactored to dataclasses with deterministic timestamps.
- Legacy wrapper scripts simplified to import the shared CLI directly.
- README now documents verification commands, observability practices, and SLO expectations.
- Ignore handling refactored with cached gitignore ingestion, case-aware matching, and support for negated patterns.
- CLI help strings now derive type choices from the preset registry to avoid drift.
- README, ARCHITECTURE, and AI interface documentation updated for agent workflows.

### Fixed
- Prevent empty `--command` sequences from reaching the sandbox, ensuring actionable validation errors reach users.
- Lint violations throughout the sample assets and wrappers detected by Ruff.
- Consolidated dependency list with pinned tooling for reproducible local runs.
- Config loader now warns on duplicate entries and rejects paths that escape the configured log root.
- Consolidate/tree commands validate output destinations up front, yielding actionable errors on permission issues.
