# Operational Baseline

Status: **current repository baseline**, reviewed against `83d0f8ae99d27c24d8b202ba92b33ab5754657c2` on 2026-09-21.

This file describes declared and hosted repository contracts. Historical machine-specific
acceptance records live in the dated audit/release documents and must not be read as current
validation.

## Product and runtime

- Primary product: local-first Repository Review workspace — `Scan → Explore → Review → Compare → Handoff`.
- Maintained secondary capability: structured log collection, normalization, redaction, diagnostics, and reporting.
- Python: `>=3.11`.
- Required core runtime dependency: `jsonschema>=4.21,<5`.
- Repository Review server extra: FastAPI, Pydantic, and Uvicorn through `.[workspace]`.
- Frontend: React/React DOM with exact-pinned private build/test tooling under `workspace-ui/`.
- Legacy helpers are optional compatibility material under #73 and are not part of the strict core identity.

## Quality profiles

`scripts/quality_gate.py` is the canonical cross-platform gate.

- `check`: contributor profile, including Python/frontend checks, Repository Review safety/API/persistence checks, helper-boundary contracts, Bandit, and tests.
- `quality`: complete local quality profile; extends `check` with dependency audit, binary scan, coverage (85% minimum), docs, editable/wheel/zipapp smokes, and diagnostics.
- `release`: extends local `quality` with redaction validation, tracked-worktree/full-history Gitleaks, and a clean-worktree requirement.

Hosted CI intentionally differs in one respect: the merge-required `quality` job runs the
maintained code-quality/product gates and detect-secrets, while `dependency-audit` runs as a
separate visible job. A failing audit remains a security/release failure; separation prevents
an unresolved upstream advisory from freezing unrelated development.

## Current hosted checkpoint

At `83d0f8ae99d27c24d8b202ba92b33ab5754657c2`:

- required hosted `quality`: passed;
- Python suite in hosted quality: 484 passed, 2 skipped;
- aggregate coverage: approximately 90%, above the 85% gate;
- frontend frozen install/format/lint/type/tests/build: passed;
- Repository Review safety, snapshot-store, API and packaged-workspace checks: passed;
- documentation, editable install, wheel, zipapp and diagnostics checks: passed;
- CodeQL default setup completed Actions, JavaScript/TypeScript and Python analyses successfully;
- independent dependency audit: failed on the separately tracked NLTK condition under #54.

This is not a stable-release declaration.

## Supply-chain controls

- GitHub Actions are full-SHA pinned.
- Workflow permissions are read-only (`contents: read`).
- checkout uses `persist-credentials: false`.
- pnpm is pinned to `10.18.1` for the frontend contract.
- detect-secrets uses the committed baseline; the local release profile additionally requires Gitleaks.
- current action provenance and dependency rationale are maintained in `docs/DEPENDENCIES.md`.
