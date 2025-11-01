# Comprehensive documentation sweep

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Maintain this plan in accordance with `.agent/PLANS.md` from the repository root.

## Purpose / Big Picture

After this change a new contributor can explore the repository and understand how to use the CLI, automate it through the agent adapter, and navigate the sample project without guesswork. Every Python module exposes precise docstrings, major Markdown guides provide architecture, API, and usage coverage, and documentation tone stays consistent.

## Progress

- [x] (2025-02-14 00:00Z) Recorded baseline plan and research scope.
- [x] (2025-02-14 00:45Z) Add docstrings to configuration, wrapper entry points, and sample project modules.
- [x] (2025-02-14 00:50Z) Standardise docstring voice (imperative, descriptive first sentence) and tighten type references.
- [x] (2025-02-14 01:15Z) Expand README.md with architecture summary, walkthrough examples, and navigation pointers.
- [x] (2025-02-14 01:20Z) Update docs/architecture/ARCHITECTURE.md and docs/AI_INTERFACE.md with richer explanations and cross-links.
- [x] (2025-02-14 01:25Z) Refresh auxiliary Markdown files (STATUS, SUPPORT, etc.) to align tone and provide actionable info.
- [x] (2025-02-14 01:35Z) Compile final review, run formatting/checks, and document outcomes.

## Surprises & Discoveries

- Observation: README expansion increased duplication with docs/architecture/ARCHITECTURE.md but
  cross-links keep content maintainable.
  Evidence: README now links directly to docs/architecture/ARCHITECTURE.md and docs/AI_INTERFACE.md.

## Decision Log

- Decision: Limit auxiliary doc refresh to SUPPORT.md and docs/plans/STATUS.md where gaps
  were present to avoid unnecessary churn in governance templates.
  Rationale: Those files lacked cross-links and actionable escalation checklists.
  Date/Author: 2025-02-14 / assistant

## Outcomes & Retrospective

Documentation now presents a cohesive narrative: module docstrings clarify
configuration helpers and sample project utilities, and Markdown guides provide
quickstarts, architecture references, and automation entry points. Linting still
flags longstanding warnings unrelated to this sweep; note these for future
cleanup alongside planned CLI refactors.

## Context and Orientation

The codebase centres around the `zscripts` package (`zscripts/cli.py`, `zscripts/config.py`, `zscripts/utils.py`, `zscripts/presets.py`) which powers the CLI. Additional wrapper modules live under `zscripts/all/` and `zscripts/all_single/` for legacy entry points. The sample project in `examples/sample_project/` demonstrates multi-stack usage and includes Python modules without complete docstrings. Documentation resides in `README.md`, `docs/architecture/ARCHITECTURE.md`, `docs/AI_INTERFACE.md`, governance documents (e.g., `SUPPORT.md`, `docs/plans/STATUS.md`), and ADRs under `docs/adr/`.

## Plan of Work

First, add module and function docstrings to the remaining Python files lacking inline documentation: `zscripts/config.py` (multiple helper functions), wrapper entry points in `zscripts/all/` and `zscripts/all_single/`, and sample project modules (`backend/models.py`, `backend/views.py`, `scripts/manage_db.py`, plus package `__init__` files). Use consistent, imperative first sentences and include parameter context where clarity is needed (e.g., configuration merging helpers).

Next, standardise docstring formatting in existing modules where tone deviates (e.g., expand `_load_raw_config` docstring to describe error handling, annotate `compile_readme` with behaviour). Ensure each module has a top-level docstring that explains its role in the ecosystem.

Then overhaul Markdown documentation. Expand `README.md` with: a quickstart, architecture overview referencing key modules, CLI usage matrix with copy-paste examples, automation/CI guidance, and links to deeper docs. Update `docs/architecture/ARCHITECTURE.md` to describe module interactions, data flow, and extension points. Augment `docs/AI_INTERFACE.md` with integration steps, schema details, and practical automation recipes. Refresh governance/support documents with consistent voice and actionable checklists where applicable. Add navigation cross-links between docs to reinforce a cohesive experience.

## Concrete Steps

1. Edit Python modules to insert or revise docstrings:
    - `zscripts/config.py`: add module docstring and docstrings for `_load_raw_config`, `_warn_on_duplicates`, `_ensure_iterable_of_strings`, `_ensure_mapping_of_strings`, `_freeze_mapping`, `_normalise_raw_config`, `_merge_config_data`, `_ensure_within_root`, `resolve_paths`, `load_config`, `get_config`, `get_file_group_resolver`, and the dynamic attribute accessor. Clarify side effects and error cases.
    - `zscripts/all/app_all_types.py` and modules under `zscripts/all_single/`: add concise module docstrings describing their legacy adapter role.
    - `zscripts/zreadme/readme_build.py`: document module purpose and the `compile_readme` process including failure handling.
    - Sample project modules (`backend/models.py`, `backend/views.py`, `scripts/manage_db.py`, and package initialisers): add explanatory module docstrings and missing function docstrings (`_now`, `_new_id`, `build_parser`, `dispatch`, `main`).
2. Review docstrings for stylistic consistency (sentence case, no trailing whitespace) and adjust as needed across touched modules.
3. Revise Markdown documentation:
    - `README.md`: add an “At a glance” section, highlight the CLI workflow with realistic end-to-end walkthroughs, embed architecture overview referencing `docs/architecture/ARCHITECTURE.md`, and describe automation via agent metadata.
    - `docs/architecture/ARCHITECTURE.md`: extend with module responsibilities, component relationships, sequence of CLI execution, and guidance on extending presets/agents.
    - `docs/AI_INTERFACE.md`: include integration checklist, payload contract, and troubleshooting guidance.
    - Reinforce auxiliary guides (`SUPPORT.md`, `docs/plans/STATUS.md`, `CHANGELOG.md` introduction if necessary) with consistent language and cross-links. Document when to consult ADRs.
4. Proof-read for consistency, ensuring Markdown headings follow sentence case and include navigation cues.
5. Run `make fmt` if docstring reflow affects formatting-sensitive tools, and execute `make lint` or targeted checks if needed.
6. Update this plan’s `Progress`, `Decision Log`, `Surprises`, and `Outcomes` sections to reflect discoveries and completion state before final commit.

## Validation and Acceptance

- Run `make fmt` to normalise imports/formatting after docstring changes.
- Run `make lint` to confirm docstring updates did not introduce lint errors (particularly Ruff’s docstring style rules).
- Optionally run `make test` to ensure sample project docstrings did not break imports.
- Manually review `README.md`, `docs/architecture/ARCHITECTURE.md`, and `docs/AI_INTERFACE.md` in a Markdown preview to confirm clarity and consistent tone.

## Idempotence and Recovery

Docstring additions are additive and safe to reapply. Markdown updates can be re-run by re-editing the files; ensure README remains the canonical compiled output (do not run `zscripts/zreadme/readme_build.py` automatically). If formatting commands fail, revert specific files via `git checkout -- <path>` and rerun steps.

## Artifacts and Notes

_Pending edits._

## Interfaces and Dependencies

- Python docstrings must satisfy Ruff’s docstring rules (first line summary, blank line separation where appropriate).
- Markdown uses standard GitHub Flavored Markdown; ensure tables and code fences remain valid.
- Do not alter existing command semantics; documentation may reference `agents.cli_adapter.export_cli_metadata` and CLI entry points in `zscripts/cli.py`.
