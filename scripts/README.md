# Scripts

Automation entry points that support development and CI workflows live here.
These utilities are designed to be invoked through `python scripts/tasks.py` but
can also be executed directly when necessary.

## Key Tools

- `tasks.py` — consolidated task runner providing linting, typing, testing, and
  dependency utilities.
- `quality_gate.py` — legacy contributor task runner; hosted CI executes its
  explicit Ruff, supported-mypy, Bandit, dependency-audit, binary-scan, pytest,
  coverage, packaging, documentation, and diagnostics steps from
  `.github/workflows/ci.yml`.
- `no_binaries.py` — guards against committing binary artefacts.
- `trace_coverage_summary.py` — compiles coverage artefacts into
  `artifacts/coverage/`.

If a script requires configuration, document it in `configs/README.md` and link
the relevant section from the top-level `README.md`.
