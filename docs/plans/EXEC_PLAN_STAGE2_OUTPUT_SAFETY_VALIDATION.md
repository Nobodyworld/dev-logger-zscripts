# Stage 2 Output Safety Validation & Hardening ExecPlan

This document tracks the Stage 2 verification and hardening work that follows up on
Stage 1's atomic output writer. Maintain this plan alongside `.agent/PLANS.md`
expectations so future contributors understand scope, checkpoints, and
outcomes.

## Purpose / Big Picture

Stage 2 validates the new output helpers end-to-end, drives coverage across
error branches, and tunes reliability so CLI commands never leave ambiguous
artifacts behind. The goal is to confirm `prepare_output_path` and
`atomic_write_text` behave predictably across directory resolution failures,
unexpected filesystem states, and cleanup edge cases, while recording coverage
and performance evidence for the release package.

## Progress

- [x] (2025-01-24 14:05Z) Audited Stage 1 implementation, identified missing
      coverage for resolution, mkdir, and cleanup branches plus the need to
      check execute permissions when validating directories.
- [x] (2025-01-24 14:20Z) Strengthened `prepare_output_path` writability check
      to require execute permission and expanded unit tests to simulate
      resolution errors, parent creation failures, non-directory parents, and
      cleanup failures during atomic writes.
- [x] (2025-01-24 14:35Z) Captured coverage via `coverage run -m pytest` and
      exported the text summary to `artifacts/coverage/coverage_stage2.txt` with module
      coverage ≥85% for the new helpers.
- [x] (2025-01-24 14:40Z) Documented findings, coverage, and lack of performance
      regression in release artifacts and updated release notes/changelog.

## Surprises & Discoveries

- Observation: `Path.mkdir` raises `FileExistsError` when a parent segment is an
  existing file, preventing the later `is_dir` guard from running. Tests must
  stub the `mkdir` call to no-op for that specific path to exercise the guard.
  Evidence: `tests/test_io_utils.py::test_prepare_output_path_parent_not_directory`
  patches `Path.mkdir` for the problematic parent and asserts the guard message.
- Observation: Cleanup failures surfaced via `Path.unlink` need to leave the
  temp file in place for manual inspection. Tests mimic this behaviour and
  ensure the helper suppresses unlink errors while still surfacing the write
  failure.

## Decision Log

- Decision: Require both write and execute permission when validating output
  parent directories.
  Rationale: Directory traversal during file creation requires execute (search)
  permission; checking both bits gives earlier, actionable errors without
  relying solely on the atomic rename.
  Date/Author: 2025-01-24 / Assistant
- Decision: Extend unit tests with targeted monkeypatching instead of relying on
  filesystem permission toggles.
  Rationale: Test runs execute as root; monkeypatching ensures deterministic
  coverage across error cases.
  Date/Author: 2025-01-24 / Assistant

## Outcomes & Retrospective

Stage 2 hardening increases coverage of the filesystem helpers to >95% of
statements, validates behaviour under resolution/mkdir/unlink failures, and
confirms that directories must be both writable and accessible before writes
proceed. Coverage and performance artifacts accompany the change, and release
notes document the reliability guarantees for operators.
