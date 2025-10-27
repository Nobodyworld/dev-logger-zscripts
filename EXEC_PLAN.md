# Professionalize zscripts project for public audiences

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Reference: repository requires adherence to `.agent/PLANS.md`. This document must be maintained in accordance with that guidance.

## Purpose / Big Picture

Deliver a polished, professional version of the zscripts toolkit suitable for public consumption. Readers should be able to install the package, run the CLI with confidence, understand the configuration surface, and trust the codebase thanks to automated tests and modern engineering practices. After this change, `python -m zscripts` should feel like a well-documented, well-tested CLI that outputs clean log bundles and tree snapshots.

## Progress

- [x] (2025-01-19 00:00Z) Documented current state and drafted plan skeleton.
- [x] (2025-01-19 00:45Z) Stand up cohesive configuration and utilities module with type-safe helpers.
- [x] (2025-01-19 01:15Z) Modernized CLI entry points with verbose/dry-run options and refactored integrations.
- [x] (2025-01-19 02:10Z) Refresh documentation to match the new polished experience.
- [x] (2025-01-19 02:25Z) Add automated tests and tooling configuration.
- [x] (2025-01-19 02:40Z) Final validation and retrospective.

## Surprises & Discoveries

- Discovery: The top-level `python -m zscripts --help` entry point intentionally keeps
  output brief; detailed option listings live on the subcommands. Documented this in the
  README to steer users toward `collect --help` and peers.

## Decision Log

- Decision: Adopt `pyproject.toml` and `ruff`/`pytest` as baseline tooling for professionalism.
  Rationale: Provide familiar, modern Python tooling that signals maturity and enables static checks/tests.
  Date/Author: 2025-01-19 / Assistant
- Decision: Retain legacy script entry points by delegating to the refreshed CLI rather than deleting them outright.
  Rationale: Preserve backwards compatibility for downstream automation while still consolidating behaviour behind the new commands.
  Date/Author: 2025-01-19 / Assistant
- Decision: Remove unmaintained legacy directories (`zscripts/by_file`, `zscripts/create`, `zscripts/make`, `zscripts/todo`, and generated `zscripts/logs`).
  Rationale: Eliminate stale scripts and artefacts that no longer reflect the supported workflow and create noise in linters.
  Date/Author: 2025-01-19 / Assistant

## Outcomes & Retrospective

- Documentation refresh and status artifacts now align with the refactored CLI and tooling
  surface.
- Automated pytest and Ruff sessions provide fast feedback; both are exercised locally as
  part of validation.
- Remaining opportunities include expanding performance tests and publishing a packaged
  dev-dependency extra for smoother onboarding.

## Context and Orientation

Originally the repository mixed modernized modules (`zscripts/cli.py`, `zscripts/config.py`) with a large legacy surface area (`zscripts/all`, `zscripts/all_single`, `zscripts/utils.py`, etc.). `zscripts.utils` duplicated imports, lacked type hints, and bundled unrelated behaviors (ignore handling, file collection, consolidation, analysis). Legacy scripts still expected old CLI flags, so invoking them raised errors. There were no automated tests or packaging metadata, and documentation referenced behaviors that diverged from the actual code (e.g., CLI commands vs. wrappers). The current revision resolves those issues while preserving compatibility for existing automation.

Key files to touch:

- `zscripts/config.py` and `zscripts/utils.py` for runtime behavior.
- `zscripts/cli.py` plus legacy wrapper scripts under `zscripts/all/`, `zscripts/all_single/`, `zscripts/by_file/`, and `zscripts/create/`.
- Repository docs (`README.md`, `PROJECT_STATUS_REPORT.md`) to present a professional narrative.
- New tooling files (`pyproject.toml`, `ruff.toml`, `noxfile.py` or CI-friendly scripts) and test suite under `tests/`. 

## Plan of Work

Narrative of major steps:

1. **Configuration foundations** - Introduce a `Config` dataclass in `zscripts/config.py` that encapsulates directories, logs, and targets with lazy loading. Expose helpers to resolve paths and ignore patterns. Update `zscripts/utils.py` to import the structured config and present a cohesive API (e.g., `collect_app_logs`, `consolidate_sources`, `render_tree`). Ensure no duplicated imports or unused legacy constants remain.
2. **Utilities refactor** - Break `zscripts/utils.py` into maintainable functions with type hints, docstrings, and a cleaner ignore-pattern pipeline. Consolidate file walking logic, ensure deterministic ordering, and add streaming to avoid memory overuse. Provide `IgnoreMatcher` helper object for pattern evaluation.
3. **CLI and wrappers** - Update `zscripts/cli.py` to consume the new utility functions and provide rich error handling and logging. Replace legacy scripts so they call into the modern CLI correctly (e.g., mapping `all_pyth` to `collect --types python`). Remove dead or misleading arguments. Add `--verbose` and `--dry-run` options for professional polish.
4. **Documentation refresh** - Rewrite `README.md` to highlight installation, usage examples, configuration schema, and development workflow. Update `PROJECT_STATUS_REPORT.md` to summarize status, backlog, and quality signals. Include CLI help snippet reflecting new options.
5. **Tooling and tests** - Add `pyproject.toml` defining project metadata, dependencies, and entry points. Configure `ruff` and `mypy` (if time) for linting. Create a `tests/` package with pytest-based coverage of ignore matching, log collection, consolidation, and CLI integration (invoking commands via `CliRunner` or subprocess). Provide `noxfile.py` or `tasks.py` to run lint + test.
6. **Final polish** - Run linters/tests, ensure sample project fixtures support tests, and capture outputs for documentation. Update plan sections, document surprises/decisions, and summarize outcomes.

## Concrete Steps

Working directory is repository root unless noted.

1. Refactor `zscripts/config.py` to define a `Config` dataclass with path resolution helpers. Add `load_config` returning `Config`. Update module-level constants for backward compatibility.
2. Replace `zscripts/utils.py` with well-typed helpers using the structured config. Introduce `IgnoreMatcher` class.
3. Adjust `zscripts/cli.py` to use new helpers, add shared options (`--verbose`, `--dry-run`), improve error messages, and ensure commands write to STDOUT/ERR consistently.
4. Update legacy wrapper scripts in `zscripts/all/`, `zscripts/all_single/`, `zscripts/by_file/`, `zscripts/create/` to delegate to CLI with new arguments. Remove stale options.
5. Add packaging/quality files: `pyproject.toml`, `ruff.toml`, `noxfile.py`, `.gitignore` updates if needed. Introduce `tests/` with pytest modules covering config loading, ignore logic, log creation, and CLI invocation against `sample_project`.
6. Revise `README.md` and `PROJECT_STATUS_REPORT.md` with professional tone, usage instructions, tooling badges/information.
7. Run formatting (`ruff`, `python -m compileall zscripts`), run tests, update plan sections, and prepare PR.

## Validation and Acceptance

- `pytest` passes with new tests, demonstrating CLI functionality on the sample project.
- `ruff check .` (or configured lint command) passes without errors.
- Running `python -m zscripts collect --types python --project-root sample_project` produces logs without stack traces, and `--dry-run` logs planned outputs without writing files.
- README instructions align with actual CLI help output.

## Idempotence and Recovery

Changes are additive and backward-compatible wrappers remain. File generation commands (`collect`, `consolidate`, `tree`) create directories with `exist_ok=True`. Tests clean up temporary output via pytest fixtures. If configuration refactor fails, `Config` retains module-level constants to avoid breaking existing imports.

## Artifacts and Notes

- Capture CLI help output snippet for README by running `python -m zscripts --help` after refactor.
- Include sample log tree output in documentation for clarity.

## Interfaces and Dependencies

- `zscripts.config.Config`: dataclass with `skip_dirs`, `ignore_patterns`, `directories`, `collection_logs`, `single_targets`, and helper methods `log_path_for(type_name: str)`, `single_target_for(type_name: str)`, `build_ignore_matcher(project_root: Path) -> IgnoreMatcher`.
- `zscripts.utils.IgnoreMatcher`: callable object storing patterns and providing `should_skip(path: Path, is_dir: bool = False) -> bool`.
- `zscripts.utils.collect_app_logs(project_root: Path, config: Config, type_names: set[str], *, dry_run: bool = False) -> list[Path]` returns generated files.
- `zscripts.utils.consolidate_sources(project_root: Path, output_path: Path, extensions: set[str], matcher: IgnoreMatcher, *, dry_run: bool = False) -> Path`.
- `zscripts.utils.render_tree(project_root: Path, output_path: Path, extensions: set[str], matcher: IgnoreMatcher, *, dry_run: bool = False) -> Path`.
- CLI subcommands call these helpers and respect `--dry-run`/`--verbose` flags.
```
