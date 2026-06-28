# Public Release Audit

This document tracks release-readiness checks for external/public distribution.

## Canonical Audit Source

The primary audit record is maintained at repository root:

- `PUBLIC_RELEASE_AUDIT.md`

This copy exists in the documentation tree so release workstreams can reference
it through `docs/INDEX.md` and operations runbooks.

## 2026-06-27 Delta

The following follow-up actions were completed after the initial baseline audit:

- Package metadata aligned to product identity as a structured log toolkit.
- Installed console command added via project entry points (`zscripts`).
- CI hardened to run strict lint/type/test and security scans (`bandit`,
  `pip-audit`, binary-file check).
- Additional tests added for adapter inventory, redaction ordering, and zipapp
  runtime execution.
- ETL/schema documentation extended with a case study and mapping examples.
- Clean-clone validation procedure and outcome recorded.
