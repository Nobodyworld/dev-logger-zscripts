# Changelog

## [Unreleased]
### Added
- Strict linting, typing, security scanning, and property tests wired into `make check` and pre-commit hooks.
- Structured logging with error identifiers across CLI utilities and the sample database manager.
- Hypothesis-based regression tests covering CLI parsers and ignore pattern expansion.
- `--dry-run` and `--verbose` flags across CLI commands plus utilities for planning log generation and tree previews.
- `--max-bytes` and `--output -` flags enabling tree and consolidate commands to stream artifacts directly to STDOUT.
- Environment variable override (`ZSCRIPTS_CONFIG_PATH`) for pointing the CLI at alternative configuration files.

### Changed
- Sample project models refactored to dataclasses with deterministic timestamps.
- Legacy wrapper scripts simplified to import the shared CLI directly.
- README now documents verification commands, observability practices, and SLO expectations.
- Ignore handling refactored with cached gitignore ingestion, case-aware matching, and support for negated patterns.

### Fixed
- Lint violations throughout the sample assets and wrappers detected by Ruff.
- Consolidated dependency list with pinned tooling for reproducible local runs.
- Config loader now warns on duplicate entries and rejects paths that escape the configured log root.
