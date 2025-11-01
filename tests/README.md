# Test Suite

The pytest suite exercises adapters, CLI orchestration, observability, and
infrastructure helpers. Tests use fixtures from `examples/` and schemas from
`schemas/` to validate the end-to-end behaviour of the toolkit.

Run the full test matrix with `pytest` or `make test`. Additional quality gates
(`ruff`, `mypy`) are exposed through the `make check` target.
