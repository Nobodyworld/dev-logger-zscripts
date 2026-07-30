# Scripts

Automation entry points that support development and CI workflows live here.
Contributor, hosted CI, and local release checks share one implementation.

## Key Tools

- `quality_gate.py` — canonical cross-platform operation registry and the
  `check`, `quality`, and `release` profiles. GitHub Actions retains separately
  named steps while delegating each operation here.
- `check_legacy_helper_boundary.py` — standard-library-only Phase 2A surface,
  compatibility-manifest, maintained-core import, wheel-membership, and
  review-time helper-immutability checks. It never imports helper source.
- `validate_commit_message.py` — deterministic, standard-library-only
  Conventional Commit validator used by the local `commit-msg` hook.
- `no_binaries.py` — guards against committing binary artefacts.
- `evaluate_repository_review.py` — generates deterministic public dogfood
  fixtures and records sanitized, bounded Repository Review measurements
  through the existing application service. Evaluation output and SQLite data
  directories are mandatory explicit paths and must remain outside every
  analyzed repository.

Example:

```powershell
python scripts/evaluate_repository_review.py generate `
  --root C:\tmp\repository-review-public
python scripts/evaluate_repository_review.py evaluate `
  --subject public-medium=C:\tmp\repository-review-public\public-medium `
  --output C:\tmp\repository-review-results\medium.json `
  --data-directory C:\tmp\repository-review-results\data
```

The evaluator records Python `tracemalloc` peaks, which do not represent full
process or native memory. It never emits source text or absolute subject paths.

If a script requires configuration, document it in `configs/README.md` and link
the relevant section from the top-level `README.md`.
