# Public Release Audit

Zscripts is a structured log collection, normalization, redaction, diagnostics, and reporting toolkit for developers and automation systems.

This document is a historical operations-facing mirror.

## Canonical Audit Source

The authoritative current record is:

- `docs/operations/PUBLIC_RELEASE_FINAL_VERDICT.md`

Historical index at repository root:

- `PUBLIC_RELEASE_AUDIT.md`

This copy exists in the documentation tree so release workstreams can reference
it through `docs/INDEX.md` and operations runbooks.

## Historical Delta (2026-06-27)

The following follow-up actions were completed after the initial baseline audit:

- Package metadata aligned to the canonical product identity.
- Installed console command added via project entry points (`zscripts`).
- CI hardened to run strict lint/type/test and security scans (`bandit`,
  `pip-audit`, binary-file check).
- Additional tests added for adapter inventory, redaction ordering, and zipapp
  runtime execution.
- ETL/schema documentation extended with a case study and mapping examples.
- Clean-clone validation procedure and outcome recorded.
