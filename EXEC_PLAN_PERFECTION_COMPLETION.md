# Elevate zscripts CLI reliability and ergonomics

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Reference: repository mandates adherence to `.agent/PLANS.md`; this plan follows that specification.

## Purpose / Big Picture

Deliver a production-grade polish pass on the zscripts command line interface and supporting utilities. Operators will benefit from safer configuration handling (invalid filenames rejected early), automatic project-root discovery when running from subdirectories, and consistent human-readable output routed through a reporter abstraction that is easy to test. Type preset definitions become authoritative and de-duplicated, reducing drift between collect and consolidate commands. The result is a CLI that is harder to misconfigure, easier to script, and fully covered by regression tests and documentation updates.

## Progress

- [x] (2025-01-20 14:10Z) Drafted ExecPlan after auditing CLI, config, and utils modules for remaining TODOs.
- [x] (2025-01-20 15:05Z) Implemented shared type preset registry and filename validation helpers in `zscripts/cli.py`.
- [x] (2025-01-20 15:25Z) Introduced reporter abstraction, refactored CLI commands, and surfaced fallback warnings for empty `--types` values.
- [x] (2025-01-20 15:45Z) Enhanced project-root resolution with auto-detection, preserved raw inputs in errors, and expanded CLI tests.
- [x] (2025-01-20 16:15Z) Updated documentation and completed `make check` (format, lint, mypy, bandit, pytest).

## Surprises & Discoveries

- Observation: Top-level source files are grouped under `root.txt` in collected logs, so tests asserting auto-detection had to inspect that file instead of deriving a file-per-module name.
  Evidence: Adjusted `test_cli_collect_auto_detects_project_root` to read `root.txt` after running `collect`.
- Observation: Creating a minimal `.git` directory is sufficient for repository detection logic, avoiding the need to initialise a full git repository during tests.
  Evidence: Auto-detection test populates `tmp_path / "auto-project" / ".git"` before invoking the CLI.

## Decision Log

- Decision: Centralise type presets in a single data structure rather than parallel dictionaries.
  Rationale: Prevents divergence between collect/consolidate defaults and enables type-driven metadata (extensions, default filenames) to stay consistent.
  Date/Author: 2025-01-20 / Assistant
- Decision: Add a `Reporter` abstraction that writes to configurable text streams and exposes `info`, `detail`, `success`, and `warning` helpers.
  Rationale: Improves testability of CLI messaging while preparing for future non-stdout sinks.
  Date/Author: 2025-01-20 / Assistant
- Decision: Auto-detect project roots by walking upward from the provided path (or CWD when omitted) until a Git directory or `pyproject.toml` is found, falling back to the resolved user path when detection fails.
  Rationale: Mirrors developer expectations when running commands from nested directories without requiring repeated `--project-root` arguments.
  Date/Author: 2025-01-20 / Assistant

## Outcomes & Retrospective

- CLI constants derive from a single preset registry, eliminating duplication and providing consistent default log/target names across commands.
- Reporter abstraction centralises human-facing output, enabling deterministic warning capture in tests while leaving payload streaming untouched.
- Project-root auto-detection behaves predictably from nested directories, with clear logging when detection occurs. Additional tests cover invalid configuration filenames and empty type fallbacks.
- Documentation highlights auto-detection and filename validation, and `make check` now passes end-to-end (ruff, mypy, bandit, pytest).

## Context and Orientation

Key areas of the repository relevant to this work:

- `zscripts/cli.py` orchestrates command parsing and execution. It currently defines separate extension maps and uses bare `print` statements for user output. TODO comments flag filename validation gaps, lack of reporter abstraction, and missing project-root auto-detection.
- `zscripts/utils.py` provides filesystem helpers (ignore matcher, tree iterators). It already exposes caching and path safety primitives leveraged by the CLI; no major refactor expected beyond potential helper reuse.
- Tests in `tests/test_cli.py` cover core behaviour but do not assert new features such as automatic root detection, reporter-driven warnings, or validation failures for invalid log filenames.
- Documentation (`README.md`, possibly `PROJECT_STATUS_REPORT.md`) lists CLI capabilities and should mention auto-detected project roots plus stricter config validation once implemented.

## Plan of Work

1. **Type preset registry & validation**: Define a `TypePreset` dataclass (extensions, default collect log name, default single-target filename). Build an ordered mapping keyed by type identifiers (`python`, `html`, `css`, `js`, `python_html`). Generate `COLLECT_TYPE_EXTENSIONS` and `SINGLE_TYPE_EXTENSIONS` from this registry while deriving default filenames. Implement `_validate_log_filenames` that rejects configuration entries containing Windows-reserved characters or name components such as `.` or `..`.
2. **Reporter abstraction and CLI refactor**: Create `Reporter` in `zscripts/cli.py` (or a small helper module if more appropriate) with `info`, `detail`, `success`, `warning`, and `blank` methods writing to injected `TextIO` streams (defaulting to `sys.stdout` / `sys.stderr`). Refactor `collect_command`, `consolidate_command`, and `tree_command` to use the reporter, ensuring dry-run lists still print detail lines. Emit a warning via reporter when `_parse_type_list` yields no entries (empty `--types`).
3. **Project-root resolution enhancements**: Extend `_resolve_project_root` to maintain the original raw argument for error messages and to auto-detect repository roots by walking upward from the provided path when the argument is `None` or `"."`. Detection should check for `.git` or `pyproject.toml`. If detection fails, fall back to the resolved path but record detection outcome for logging and tests. Update error messages to retain the raw input string.
4. **Testing & documentation**: Expand `tests/test_cli.py` to cover (a) reporter-driven warning when `--types` is empty, (b) automatic root detection when invoking from a nested directory, and (c) configuration filename validation (likely via a temporary config override raising `RuntimeError`/`ValueError`). Update README (and status report if it mentions CLI usage) to document automatic project-root detection and stricter config filename validation. Run `make check` to ensure formatting, linting, typing, security, and tests all pass.

## Concrete Steps

1. Edit `zscripts/cli.py` to introduce `TypePreset`, regenerate extension constants, add filename validation helper, and instantiate a `Reporter` used throughout command handlers.
2. Modify `_resolve_project_root` with detection logic and integrate detection metadata into logging if helpful.
3. Adjust `_build_log_paths` / `_build_single_targets` to rely on the preset defaults and invoke filename validation. Ensure cached ignore loading remains intact.
4. Update or add tests in `tests/test_cli.py` for new behaviours. Where necessary, craft temporary config files or monkeypatch environment variables to trigger filename validation errors.
5. Amend `README.md` (and `PROJECT_STATUS_REPORT.md` if necessary) to describe the new CLI behaviour. Mention reporter-based consistent output only if user-facing (e.g., new warning message).
6. Run `ruff format .`, `ruff check .`, `mypy .`, `bandit -q -r zscripts sample_project`, and `pytest` (or simply `make check`). Capture outputs for final report.

## Validation and Acceptance

Work is complete when:

- `pytest` passes with new tests verifying reporter warnings and auto-detected project roots.
- `make check` (or its constituent commands) succeeds without errors.
- README (and related docs) mention automatic project-root detection and configuration filename validation.
- Manual smoke test (`python -m zscripts collect --types="" --sample --dry-run`) shows a reporter warning and default type fallback.

## Idempotence and Recovery

- The reporter abstraction introduces no persistent state; repeated CLI invocations behave identically.
- Filename validation runs before filesystem writes, so misconfigurations fail fast without partial side effects.
- Project-root detection only affects default resolution; specifying an explicit path remains deterministic.
- Tests create and clean temporary directories, ensuring repeated runs remain clean.

## Artifacts and Notes

- Capture representative CLI output snippets (warning for empty types, auto-detection log line) for documentation if space permits.

## Interfaces and Dependencies

- `zscripts.cli.TypePreset` dataclass with fields `name`, `extensions`, `collect_log`, `single_target`.
- `zscripts.cli.COLLECT_TYPE_EXTENSIONS` and `SINGLE_TYPE_EXTENSIONS` generated from presets; existing consumers continue to import these constants.
- `zscripts.cli.Reporter` class with methods `info(message: str)`, `detail(message: str)`, `success(message: str)`, `warning(message: str)`, and `blank()`.
- `_resolve_project_root(raw_root: str | None, *, sample: bool, auto_detect: bool = True) -> Path` supporting detection.
- `_validate_log_filenames(paths: Mapping[str, Path]) -> None` raising `ValueError` on invalid names.

Plan last updated: 2025-01-20 16:15Z after docs refresh and validation run.
