# Hardening the zscripts CLI and utilities

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

zscripts bundles project source files into navigable log archives. The current implementation works but mixes legacy patterns, has inconsistent error handling, and lacks targeted tests around safety-critical paths. After this change maintainers can rely on a clearer configuration API, hardened filesystem traversal that resists symlink escapes, and a CLI that reports errors gracefully. Users will run `python -m zscripts ...` and see predictable output, confident that generated logs respect ignore rules without leaking outside the project root. Validation consists of the automated test suite exercising CLI flows and utility helpers against real filesystem fixtures.

## Progress

- [x] (2025-10-16T19:59:24+00:00) Baseline assessment complete; code hotspots identified.
- [x] (2025-10-16T20:06:54+00:00) Hardened configuration loading with validation helpers and refreshed documentation.
- [x] (2025-10-16T20:06:54+00:00) Tightened filesystem utilities (ignore handling, symlink safety, relative path helpers) and documented public APIs.
- [x] (2025-10-16T20:06:54+00:00) Refactored CLI parsing to share extension metadata, provide structured error handling, and accept richer tree command options.
- [x] (2025-10-16T20:06:54+00:00) Refreshed and focused the automated tests to cover new edge cases while keeping runtime low.
- [x] (2025-10-16T20:16:34+00:00) Ran tests and updated documentation; ready to finalize the PR message.
- [x] (2025-10-17T00:00:00+00:00) Perform RC verification: enforce lint/type/security gates, add property tests, and document operational guidance.
- [x] (2025-10-21T06:45:00+00:00) Expand output preflight checks and CLI permission handling for production readiness.

## Surprises & Discoveries

- Legacy integration tests exercised unrealistic timing guarantees. Replacing
  them with targeted filesystem checks kept runtime low while covering the
  newly added error handling.
- CLI emits helpful warnings before permission failures (e.g., consolidate
  warns about custom paths) which required tests to capture the final error
  line rather than the first stderr line.

## Decision Log

- Decision: Merge custom configuration files with repository defaults instead
  of replacing missing sections outright.
  Rationale: Users can now override individual keys without recreating the
  entire schema, lowering the risk of drift.
  Date/Author: 2025-10-16 / gpt-5-codex
- Decision: Require the project root to exist and make tree dumps omit contents
  unless `--include-contents` is set.
  Rationale: Prevents confusing empty outputs and avoids unexpected large
  files, while giving operators an explicit opt-in flag.
  Date/Author: 2025-10-16 / gpt-5-codex
- Decision: Raise a dedicated CLI permission error (exit code 3) and tighten
  allowed-root validation before touching the filesystem.
  Rationale: Operators now receive actionable feedback without creating
  directories when misconfigured paths or ACLs block writes.
  Date/Author: 2025-10-21 / gpt-5-codex

## Outcomes & Retrospective

The CLI now enforces validated input, merges configuration overrides safely,
and refuses to traverse outside the project root. Filesystem helpers stream
data while respecting ignore patterns, and the test suite focuses on these
behaviours instead of synthetic performance checks.

## Context and Orientation

The repository centres around the `zscripts` package. Key modules:

* `zscripts/config.py` exposes configuration constants and a `Config` dataclass built from `zscripts.config.json`. Global module state loads JSON on import.
* `zscripts/utils.py` contains filesystem traversal helpers used by the CLI.
* `zscripts/cli.py` implements the command-line interface with three subcommands (`collect`, `consolidate`, `tree`).
* Tests reside in `tests/` and currently cover CLI flows, configuration, utilities, and backwards compatibility shims. Several tests are redundant or unrealistic (e.g., timing assertions).

The goal is to keep module boundaries intact while modernising their interfaces and documenting behaviour. Configuration must become resilient against malformed input (type validation, helpful errors). Filesystem helpers should work with resolved paths, reject symlink escapes, and avoid reading huge files into memory unnecessarily. CLI commands should report errors deterministically instead of raising exceptions that bleed into stdout. Tests must assert the new contracts and drop brittle checks.

## Plan of Work

1. **Configuration hardening**
   - Add a module docstring and reorganise `zscripts/config.py` so helper functions are clearly documented.
   - Introduce a `_validate_raw_config` helper that enforces expected types (lists, dicts) and converts values appropriately, ensuring `Config` always receives canonical structures. Provide descriptive `RuntimeError`s when data is malformed.
   - Expose a `resolve_paths` utility that returns fully qualified directories (log root, etc.) instead of module-level constants, reducing reliance on global state for consumers that need dynamic locations.
   - Ensure `load_config` reuses `_validate_raw_config` and merges with defaults rather than returning partially populated objects.

2. **Filesystem utility improvements**
   - Replace the ad-hoc import try/except with explicit re-export from `zscripts.config`—documented for maintainability.
   - Introduce `safe_relative_path(project_root, candidate)` to guard against paths escaping the root (resolves symlinks, raises `ValueError` if traversal occurs). Use it inside `collect_app_logs`, `consolidate_files`, and `create_filtered_tree`.
   - Update `IgnoreMatcher` to precompile patterns with `fnmatch.translate` for performance. Document the matching semantics.
   - Stream file writes in `collect_app_logs`/`consolidate_files` by yielding entries instead of storing everything in memory.
   - Ensure tree output optionally omits file contents by default for performance and adds a size guard when including contents.

3. **CLI refactor**
   - Move extension mappings into a dedicated helper (e.g., `_get_extension_map`) that can be shared between commands and derived from config file types when possible.
   - Wrap command execution in `main()` with robust error handling: catch `UnknownTypeError`, `RuntimeError`, and `OSError`, printing user-friendly messages to stderr and returning non-zero exit codes.
   - Validate provided project roots and output directories, creating directories when necessary while ensuring they remain within the filesystem root.
   - Add a CLI flag to control whether the `tree` command includes file contents (default `False` to avoid huge outputs) and wire through to the utility function.

4. **Test suite refresh**
   - Replace brittle performance and timing assertions with deterministic filesystem tests that validate new safety features (symlink rejection, path traversal prevention, CLI error codes, config validation).
   - Add fixtures for creating nested directories and symlinks where supported.
   - Ensure tests assert exit codes and stdout/stderr messages for error cases.
   - Remove redundant tests that duplicate others without providing unique coverage.

5. **Validation and polish**
   - Run `ruff check --fix` and `pytest`.
   - Update `README.md` if CLI usage semantics change (e.g., new `--include-contents` flag, error behaviour).
   - Prepare a concise, professional PR message summarising the improvements.

6. **RC verification and hardening (follow-up)**
   - Enforce linting, formatting, typing, and security scanners in automation; capture configuration in `pyproject.toml` and pre-commit hooks.
   - Add property-based regression tests for configuration normalisation, CLI type parsing, and ignore pattern expansion.
   - Refine sample assets to satisfy lint rules and exemplify modern patterns without dead code.
   - Provide operator-focused documentation: deterministic Makefile targets, quickstart commands, changelog, and observability notes.

7. **Output preflight productionization**
   - Make `ensure_writable_path` reject non-directory allowed roots, clarify its return contract, and capture the resolved parent in error messages.
   - Rename and streamline the collect preflight helper so it returns resolved directories and validates they share a single base path for logging.
   - Catch `PermissionError` explicitly in the CLI to emit actionable diagnostics instead of the generic "os error" prefix.
   - Add regression tests for these behaviours, covering CLI flows and direct utility calls so future refactors keep the guarantees intact.

## Concrete Steps

- From the repository root, edit `zscripts/config.py` following the plan above, adding helper functions and docstrings.
- Update `zscripts/utils.py` to use the new path-safety helpers, streaming IO, and improved matcher implementation.
- Refactor `zscripts/cli.py` to adopt the new extension metadata, error handling, and tree content flag.
- Modify or add tests under `tests/` to reflect new behaviour. Remove obsolete tests after confirming coverage overlaps.
- Run `ruff check --fix` (if available) and `pytest` from the repository root.
- Review `README.md` for CLI flag documentation updates; adjust as needed.

## Validation and Acceptance

- `pytest` must pass without failures, covering new edge cases.
- Running `python -m zscripts collect --types invalid` should exit non-zero with a descriptive message, leaving no partial outputs.
- Executing `python -m zscripts tree --include-contents` against the sample project should produce a tree file without following symlinks outside the project root.
- Configuration loading should raise a clear error for malformed JSON and succeed with partial overrides.

## Idempotence and Recovery

The changes are additive and safe to re-run. All helper functions are pure or idempotent, and commands create directories with `exist_ok=True`. If validation detects an invalid state, informative errors guide correction. Tests clean up temporary directories automatically.

## Artifacts and Notes

Keep relevant pytest transcripts showing new cases. Include sample CLI outputs in the PR description if behaviour changes materially.

## Interfaces and Dependencies

- `zscripts.config` must expose `Config`, `load_config`, `get_config`, `resolve_paths`, and `get_file_group_resolver` with stable signatures.
- `zscripts.utils` must export `IgnoreMatcher`, `expand_skip_dirs`, `load_gitignore_patterns`, `collect_app_logs`, `consolidate_files`, and `create_filtered_tree`. `safe_relative_path` may remain internal.
- CLI entry point remains `zscripts.cli:main`, returning an integer exit code and printing user-facing messages to stdout/stderr.

