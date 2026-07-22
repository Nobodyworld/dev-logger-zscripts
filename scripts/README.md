# Scripts

Automation entry points that support development and CI workflows live here.
Contributor, hosted CI, and local release checks share one implementation.

## Key Tools

- `quality_gate.py` — canonical cross-platform operation registry and the
  `check`, `quality`, and `release` profiles. GitHub Actions retains separately
  named steps while delegating each operation here.
- `validate_commit_message.py` — deterministic, standard-library-only
  Conventional Commit validator used by the local `commit-msg` hook.
- `no_binaries.py` — guards against committing binary artefacts.

If a script requires configuration, document it in `configs/README.md` and link
the relevant section from the top-level `README.md`.
