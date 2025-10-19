# Harden zscripts configuration and CLI for production readiness

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Reference: repository requires adherence to `.agent/PLANS.md`. This document must be maintained in accordance with that guidance.

## Purpose / Big Picture

Elevate zscripts from "polished beta" to a hardened production tool. After this work, operators can point the CLI at large projects with confidence that configuration overrides, ignore rules, and output paths behave predictably. The CLI will expose clearer ergonomics (type suggestions, byte limits, stdout streaming), configuration loading gains environment awareness and defensive validation, and ignore handling supports modern `.gitignore` semantics. Users can dry-run or execute commands repeatedly without stale state, while tests and docs demonstrate the new capabilities end-to-end.

## Progress

- [x] (2025-01-19 04:10Z) Drafted initial plan after auditing configuration, CLI, and utility modules.
- [x] (2025-01-19 05:05Z) Implemented configuration loader upgrades (environment override, lazy load, duplicate diagnostics).
- [x] (2025-01-19 05:35Z) Improved ignore matching, gitignore ingestion, and traversal caching.
- [x] (2025-01-19 06:05Z) Extended CLI ergonomics (type suggestions, stdout output, max-bytes option) and refactored extension presets.
- [x] (2025-01-19 06:25Z) Expanded tests/docs, ran validation commands, and captured retrospective notes.

## Surprises & Discoveries

- Observation: Existing tests all pass, indicating behavioural stability; improvements must preserve compatibility.
  Evidence: `pytest` run before changes succeeded (see plan context).
- Observation: Python's module-level ``__getattr__`` allowed exporting lazy config attributes without breaking legacy imports.
  Evidence: `zscripts/config.py` now serves ``SKIP_DIRS`` et al. through cached accessors while keeping API intact.

## Decision Log

- Decision: Use environment variable `ZSCRIPTS_CONFIG_PATH` for overriding the default configuration file.
  Rationale: Provides explicit, namespaced override with minimal risk of collision.
  Date/Author: 2025-01-19 / Assistant
- Decision: Stream consolidate/tree output directly to stdout when requested while reporting status to stderr.
  Rationale: Preserves scriptability of generated logs without interleaving control messages with data payloads.
  Date/Author: 2025-01-19 / Assistant

## Outcomes & Retrospective

- Config loader now defers disk I/O until first use, honours environment overrides,
  and surfaces duplicate-value warnings so operators can fix noisy settings.
- Ignore handling caches gitignore reads, supports negated patterns, and treats
  Windows-style casing consistently without regressing legacy behaviour.
- CLI exposes a unified extension matrix, suggests close matches for typos, and
  streams consolidate/tree outputs to stdout with controllable byte limits for
  tree content. New pytest coverage locks in the expected behaviour.
- Documentation (README, status report, changelog) highlights the new workflow,
  and both `ruff check .` plus `pytest` pass, confirming end-to-end health.

## Context and Orientation

Key modules involved:

- `zscripts/config.py` currently loads configuration eagerly, lacks environment overrides, and silently suppresses duplicate skip or ignore entries.
- `zscripts/utils.py` houses `IgnoreMatcher` (no negation support, recompiles patterns), tree/collection helpers, and gitignore loading (ignores `.git/info/exclude`).
- `zscripts/cli.py` defines extension presets in two separate dicts, lacks suggestions for unknown types, cannot stream logs/tree to stdout, and has TODOs for dry-run messaging and max-bytes configuration.
- Tests in `tests/` cover happy paths but omit new functionality such as environment overrides, negated ignore patterns, or stdout output.
- Documentation (`README.md`, `PROJECT_STATUS_REPORT.md`) does not mention environment overrides, new CLI options, or ignore semantics.

## Plan of Work

1. **Configuration loader upgrades**
   - Introduce helper `_determine_default_config_path()` honoring `ZSCRIPTS_CONFIG_PATH` and validate existence lazily.
   - Replace module-level `_DEFAULT_CONFIG` with a cached loader function (`_get_default_config()`) to avoid disk I/O on import; update consumers to call helpers.
   - Enhance `_ensure_iterable_of_strings` to record duplicates and surface warnings via `warnings.warn`; track unknown keys and raise `RuntimeError` with helpful message listing unexpected keys.
   - Extend `resolve_paths` to reject directories that escape the root by verifying `.resolve()` stays under base.
   - Provide `load_config` API returning both overrides merged and metadata (if needed) while maintaining backwards compatibility.

2. **Ignore handling and filesystem utilities**
   - Refactor `IgnoreMatcher` to normalise case on Windows, support negated patterns (`!pattern`), and use an LRU cache for regex compilation to eliminate repeated work.
   - Allow `file_matches_any_pattern` to accept `str` inputs and reuse shared compilation logic.
   - Update `load_gitignore_patterns` to include patterns from `.git/info/exclude`, respect cached results per root+inputs, and emit warnings for unreadable files.
   - Ensure `_iter_source_files` caches extension sets and sorts deterministically; optionally expose generator for tree to reuse cached ignore matcher.

3. **CLI ergonomics and refactor**
   - Define single authoritative extension preset mapping and derive `COLLECT_TYPE_EXTENSIONS`/`SINGLE_TYPE_EXTENSIONS` views from it.
   - Provide `difflib.get_close_matches` suggestion when `_parse_type_list` encounters unknown value.
   - Cache `_augment_ignore_patterns` calls via `functools.lru_cache` keyed by project root + config identity.
   - Add `--max-bytes` option to `tree` command, plumb through to `iter_filtered_tree_lines` and `create_filtered_tree`.
   - Allow `--output -` on `consolidate` and `tree` commands to stream to stdout while respecting dry-run.
   - Improve dry-run outputs by showing counts and using consistent bullet formatting; ensure output uses `print` wrappers.
   - Preserve existing defaults and error codes.

4. **Tests and documentation**
   - Add tests covering environment override, duplicate warnings, unknown keys, negated ignore patterns, `.git/info/exclude`, case normalisation, stdout output, and `--max-bytes` behaviour.
   - Update README/PROJECT_STATUS_REPORT to describe new env var, CLI flags, and ignore semantics.
   - Ensure changelog/report mention enhancements.
   - Run lint/test commands, capture outputs, and update plan sections accordingly.

## Concrete Steps

1. Modify `zscripts/config.py` per configuration upgrades; update imports to include `os`, `functools`, `warnings`.
2. Adjust `zscripts/utils.py` to refactor `IgnoreMatcher`, gitignore loading, and tree helpers as described.
3. Update `zscripts/cli.py` to consume new utilities, extend argument parser, and handle stdout output.
4. Add/modify tests in `tests/test_config.py`, `tests/test_utils.py`, `tests/test_cli.py` for new behaviours; create dedicated fixtures if required.
5. Refresh `README.md`, `PROJECT_STATUS_REPORT.md`, and `CHANGELOG.md` to document enhancements.
6. Run `ruff check .`, `pytest`, and any additional relevant commands (e.g., `python -m zscripts ...` dry-run) to validate changes. Update plan progress, logs, and retrospective.

## Validation and Acceptance

- `pytest` succeeds with new tests highlighting environment overrides, ignore negation, stdout output, and `--max-bytes` functionality.
- `ruff check .` passes without errors.
- Manual CLI invocation (`python -m zscripts tree --sample --dry-run --max-bytes 128`) shows new options and warnings behave as documented.

## Idempotence and Recovery

- Default config loader caches results and can be re-run without side effects; environment overrides remain optional.
- Ignore matcher caches respect arguments and can be invalidated by process restart; no persistent state is introduced.
- CLI stdout output only triggers when explicitly requested; file outputs remain unaffected.
- Tests create temporary directories and clean up via pytest fixtures.

## Artifacts and Notes

- Capture warning examples when duplicates are encountered for documentation/testing.
- Include sample CLI dry-run output (with counts and suggestions) in README if space permits.

## Interfaces and Dependencies

- `zscripts.config._get_default_config()` -> `Config`
- `zscripts.config.determine_config_path(path: Path | str | None) -> Path`
- `zscripts.utils.IgnoreMatcher` gains negation support and optional case normalisation; maintain `.matches` API.
- `zscripts.utils.load_gitignore_patterns` signature unchanged but now caches and includes extra sources.
- CLI `tree` command accepts `--max-bytes` (int, default 4096) and supports `--output -`.
- `consolidate` command supports `--output -` for stdout streaming.
