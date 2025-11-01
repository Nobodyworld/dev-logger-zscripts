```md
# Harden configuration immutability and tooling ergonomics

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Reference: follow `.agent/PLANS.md` for structure and maintenance expectations.

## Purpose / Big Picture

Lock down the default configuration so downstream callers cannot accidentally mutate global state, and ensure the advertised developer workflow (`make fmt`, `make lint`, etc.) actually runs. After these changes, attempts to modify `zscripts.config.get_config()` fields will fail with a clear `TypeError`, and `make lint`/`make check` will execute without Makefile syntax errors.

## Progress

- [x] (2025-02-14 00:00Z) Captured current gaps and drafted plan skeleton.
- [x] (2025-02-14 00:20Z) Makefile target bodies use real tab prefixes so developer commands succeed.
- [x] (2025-02-14 00:30Z) `Config` dataclass stores immutable mappings and exposes safe copies for callers.
- [x] (2025-02-14 00:33Z) Expand configuration tests to prove immutability and regression guardrails.
- [x] (2025-02-14 00:40Z) Run validation commands and document outcomes; finalize retrospective.

## Surprises & Discoveries

- Observation: `make lint` failed before changes because Makefile recipes were space-indented.
  Evidence: Running `make lint` after inserting tabs now executes Ruff successfully (see validation commands).

## Decision Log

- Decision: Freeze configuration mapping fields with `MappingProxyType`.
  Rationale: Prevent callers from mutating global defaults returned by `get_config()` while keeping API read-only.
  Date/Author: 2025-02-14 / Assistant

## Outcomes & Retrospective

- Configuration mapping fields are now immutable proxies, preventing accidental mutation of global state.
- Additional tests guard immutability and `Config.to_dict` copy semantics.
- Makefile workflow is restored; `make lint` and `make test` succeed and align with README guidance.

## Context and Orientation

`zscripts/config.py` currently materializes a `Config` dataclass whose `file_types`, `directories`, `collection_logs`, and `single_targets` fields are mutable `dict` instances. Because `load_config()` returns the module-level singleton when no overrides are provided, any consumer that mutates one of those dictionaries silently alters global defaults. Tests do not guard against this and developer tooling in the `Makefile` fails because tab-indented command bodies were replaced with spaces, so `make lint` aborts.

Key files:

- `Makefile` – developer entry points advertised in README.
- `zscripts/config.py` – configuration loader, dataclass definition, helper functions.
- `tests/test_config.py` – existing coverage for configuration behavior.

## Plan of Work

1. Update `Makefile` so every recipe line starts with a hard tab. Verify `.PHONY` target remains intact.
2. Introduce a helper in `zscripts/config.py` (e.g., `_freeze_mapping`) that converts a `dict[str, str]` into an immutable `MappingProxyType`. Adjust the `Config` dataclass to annotate mapping fields as `Mapping[str, str]` and ensure `_normalise_raw_config` and `_merge_config_data` use `_freeze_mapping` so all stored mappings are read-only. Confirm module-level constants still expose copies where appropriate.
3. Extend `_merge_config_data` to build merged dictionaries via `dict(defaults.field) | dict(overrides.field)` before freezing, preserving override precedence while maintaining immutability.
4. Amend `tests/test_config.py` to assert that attempting to mutate `Config` mapping fields raises `TypeError` and that `Config.to_dict()` still yields mutable copies.
5. Run `make lint`, `make test`, and `pytest` directly to validate linting/tests, updating this plan with any surprises, decisions, and final outcomes.

## Concrete Steps

- Edit `Makefile`, replacing each space-indented command with a tab-indented command.
- In `zscripts/config.py`, import `Mapping` from `collections.abc` (if not already), add `from types import MappingProxyType`, define `_freeze_mapping(mapping: Mapping[str, str]) -> Mapping[str, str]`, and apply it within `_normalise_raw_config` and `_merge_config_data`. Update the `Config` dataclass field annotations accordingly.
- Update `Config.to_dict()` to continue returning plain `dict` objects (no change, but confirm compatibility) and ensure module-level constants like `FILE_TYPES` still call `dict(...)` to produce copies.
- Modify `_merge_config_data` to build merged dictionaries using `dict(defaults.file_types)` and freeze the result; repeat for directories, collection logs, and single targets.
- In `tests/test_config.py`, add assertions that mutating `config.file_types`, `config.directories`, and `config.collection_logs` raises `TypeError`, and confirm `config.to_dict()` returns mutable copies by appending to them.
- Execute `make lint`, `make test`, and `pytest` from the repository root, capturing outputs for validation.

## Validation and Acceptance

- `make lint` succeeds, running Ruff without Makefile syntax errors.
- `make test` passes and mirrors `pytest` success.
- Direct `pytest` run still yields all passing tests.
- New tests confirm configuration immutability: assignment attempts raise `TypeError` while `Config.to_dict()` returns mutable copies.

## Idempotence and Recovery

Edits are textual and repeatable. Re-running the validation commands is safe. If freezing mappings introduces regressions, revert to the previous commit or re-run `_normalise_raw_config` without `_freeze_mapping` to restore behavior temporarily.

## Artifacts and Notes

- Capture command transcripts for `make lint`, `make test`, and `pytest` post-change.

## Interfaces and Dependencies

- `zscripts.config.Config` mapping fields behave as read-only `MappingProxyType` instances.
- `_freeze_mapping` returns a `Mapping[str, str]` that raises `TypeError` on mutation attempts.
- Tests import `TypeError` expectations via `pytest.raises` to guard the behavior.
```
