# Tests

All automated coverage for the repository resides here. Pytest is the primary
runner and is orchestrated by `python scripts/quality_gate.py tests`; the
coverage-enforced operation is `python scripts/quality_gate.py coverage`.

## Structure

- `helpers/` — unit and integration tests mapped to the helper packages.
- `conftest.py` — shared fixtures, including temporary directory and network
  helpers.

When adding a new helper, create a matching test module under this tree. Prefer
fast, deterministic tests so the quality gate remains lightweight.
