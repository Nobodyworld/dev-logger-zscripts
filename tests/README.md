# Tests

All automated coverage for the helpers resides here. Pytest is the primary
runner and is orchestrated through `python scripts/tasks.py gate`.

## Structure

- `helpers/` — unit and integration tests mapped to the helper packages.
- `conftest.py` — shared fixtures, including temporary directory and network
  helpers.

When adding a new helper, create a matching test module under this tree. Prefer
fast, deterministic tests so the quality gate remains lightweight.
