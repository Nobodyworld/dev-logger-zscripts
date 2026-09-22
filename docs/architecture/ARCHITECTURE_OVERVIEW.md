# Architecture Overview

Zscripts has two maintained surfaces with one explicit product priority:

1. **Repository Review — primary product.** Local-first, deterministic, read-only Python
   repository analysis with SQLite snapshots and a localhost React workspace.
2. **Log toolkit — maintained capability.** Adapter-based log collection/normalization,
   redaction, reporting, diagnostics, observability, and extension tooling.

Legacy helpers are compatibility-only under #73.

```text
Repository Review
Repository → bounded discovery → AST/static evidence → relationships/findings
           → atomic SQLite snapshot → localhost API → React workspace

Log toolkit
File/stdin/selected command → adapter → normalized schema
                            → redaction/reporting/diagnostics
```

Repository Review never imports or executes analyzed project modules. Command collection is a
separate trust boundary and may execute a user-selected command with process-level guardrails;
those guardrails are not OS/container isolation.

See [ARCHITECTURE.md](ARCHITECTURE.md) for component responsibilities and
[../repository-review.md](../repository-review.md) for product/privacy semantics.
