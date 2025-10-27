# Stage 1 Output Destination Hardening ExecPlan

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with `.agent/PLANS.md` and remains self-contained for future contributors.

## Purpose / Big Picture

Operators rely on `zscripts` CLI commands to capture, normalize, and report build logs in CI. Today `collect`, `parse`, `redact`, and `report` accept `--output` paths but write directly via `Path.write_text`. If the target directory is missing or lacks permissions, the failure surfaces as a low-level `OSError` after work has already been performed, leading to confusing partial runs. Stage 1 will introduce validated, atomic output handling that checks destinations up front, creates parent directories safely, and returns actionable error messages. After this change, writing to an unwritable location immediately surfaces `error: unable to write to ...` and no partial files remain. Documentation and tests will cover the new guarantees.

## Progress

- [x] (2025-01-24 12:10Z) Drafted ExecPlan covering purpose, context, and validation strategy.
- [x] (2025-01-24 12:35Z) Implemented filesystem helper module for validating and atomically writing CLI outputs.
- [x] (2025-01-24 12:42Z) Integrated helper into CLI commands and ensured telemetry logging for failures.
- [x] (2025-01-24 13:00Z) Expanded unit tests for helpers and CLI error handling, covering atomic writes and permission failures.
- [x] (2025-01-24 13:15Z) Updated README and docs to describe output path validation and atomic writes.
- [x] (2025-01-24 13:30Z) Ran `pytest` and `ruff check .`; captured outputs (`884682`, `45d966`) and updated plan outcomes.

## Surprises & Discoveries

- Observation: Repository tests run as the root user, so Unix permission bits do not reliably block writes; simulated failures must patch filesystem helpers instead of relying on chmod.
  Evidence: `tests/test_io_utils.py::test_prepare_output_path_detects_unwritable_parent` uses `monkeypatch` to force `os.access` failure.

## Decision Log

- Decision: Focus Stage 1 on hardening CLI output destinations via a shared helper rather than per-command patches.
  Rationale: Centralizing validation avoids drift between commands and paves the way for reuse in future workflows (e.g., `consolidate`, `tree`).
  Date/Author: 2025-01-24 / Assistant
- Decision: Validate writability with `os.access` prior to atomic writes to surface quick failures while still relying on the write step for final enforcement.
  Rationale: The pre-check improves user messaging without attempting speculative writes; the atomic rename keeps correctness even if permissions change mid-run.
  Date/Author: 2025-01-24 / Assistant

## Outcomes & Retrospective

Stage 1 delivered a reusable atomic writer for CLI outputs, integrated it across
commands, and added tests verifying directory/permission failures alongside
successful replacements. Documentation now calls out automatic directory
creation and failure messaging. Pytest and ruff both pass, giving confidence in
the refactor.

## Context and Orientation

The CLI entry point lives in `zscripts/cli.py` and dispatches commands such as `collect`, `parse`, `redact`, and `report`. Each command delegates to `ToolkitService` for heavy lifting but writes results to disk through the private `_write_output` helper, which simply calls `Path(output_path).write_text`. When directories are missing or lack permissions, Python raises `FileNotFoundError` or `PermissionError` after processing completes. Tests covering CLI behavior reside in `tests/test_cli.py`. Service and reporting utilities live in `zscripts/application/`.

We will introduce a small filesystem utility (e.g., `zscripts/application/io_utils.py`) responsible for preparing destinations, ensuring parent directories exist, checking writability, and performing atomic writes by using a temporary file and `os.replace`. The CLI will call this helper instead of directly writing. Tests will cover success, directory conflicts, and permission failures using pytest's `tmp_path` fixtures. Documentation updates in `README.md` and `docs/reporting.md` will explain the safer semantics.

## Plan of Work

1. Create `zscripts/application/io_utils.py` defining:
   - `OutputPathError` exception for user-friendly messaging.
   - `prepare_output_path(path: Path) -> Path` that expands `~`, rejects directories, ensures parents exist, and raises `OutputPathError` with context on failure.
   - `atomic_write_text(path: Path, payload: str) -> None` that writes to a temporary file in the destination directory, flushes/fsyncs, and replaces the target atomically. It should surface failures as `OutputPathError` with chained originals.
2. Update `zscripts/application/__init__.py` if necessary to export new helpers.
3. Modify `zscripts/cli.py`:
   - Import helpers.
   - Update `_write_output` to short-circuit when `output_path` is falsy, otherwise call `atomic_write_text` and catch `OutputPathError`, passing message to `_fail`.
   - Ensure telemetry logging in `_handle_report` still occurs when `SystemExit(1)` is raised (no change expected but re-verify flow).
4. Add unit tests:
   - `tests/test_io_utils.py` verifying `prepare_output_path` behavior (creates parents, rejects directories, handles permissions via patched `os.access`) and `atomic_write_text` atomicity (existing file replaced, intermediate temp removed).
   - Extend `tests/test_cli.py` to check the CLI emits friendly errors when the output target is invalid (e.g., path resolves to a directory), ensuring `_fail` surfaces the helper message.
5. Update documentation:
   - `README.md` output examples to mention automatic directory creation and atomic writes.
   - `docs/reporting.md` and `docs/dev_workflow.md` (if necessary) to describe error messaging for unwritable paths.
6. Validation: run `pytest` and `ruff check .`, capture outputs (chunk IDs) for the ExecPlan.

## Concrete Steps

1. Implement new helper module `zscripts/application/io_utils.py` with dataclasses/functions described above, including docstrings and type hints.
2. Export helpers via package `__all__` if required.
3. Refactor `zscripts/cli.py` to use helpers and provide `_fail` messaging on `OutputPathError`.
4. Write new tests under `tests/test_io_utils.py` and expand CLI tests for error handling.
5. Update documentation files with new behavior.
6. Run `pytest` and `ruff check .`; update this plan's Progress, Surprises, Decision Log (if needed), and Outcomes sections accordingly.

## Validation and Acceptance

- Running `python cli.py report --input examples/python/sample.log --output /root/protected/report.json` on an unwritable directory should exit with code 2 and display a descriptive `error: unable to write to ...` message (unit tests cover the permission branch when direct reproduction is not feasible).
- Writing to new directories such as `tmp/output/report.json` should succeed, creating intermediate directories automatically.
- Existing files should be replaced atomically; tests verify the final content matches the payload with no partial writes.
- `pytest` and `ruff check .` complete successfully.

## Idempotence and Recovery

The helper functions create parent directories if missing and are safe to call repeatedly. Atomic replacement ensures reruns cannot leave partially written files even if interrupted mid-write. If directory preparation fails, the helper leaves no artifacts and surfaces a descriptive exception so the user can adjust permissions before retrying.

## Artifacts and Notes

- `pytest` run with 119 passing tests (`884682`).
- `ruff check .` confirming lint success (`45d966`).

## Interfaces and Dependencies

- New module `zscripts/application/io_utils.py` exposes:

      class OutputPathError(RuntimeError):
          """Raised when an output destination cannot be prepared or written."""

      def prepare_output_path(path: Path) -> Path:
          """Return an expanded, validated path ready for writing."""

      def atomic_write_text(path: Path, payload: str) -> None:
          """Write text to ``path`` atomically, raising OutputPathError on failure."""

- CLI `_write_output` will depend on `atomic_write_text`.
- Tests reference these functions directly.

