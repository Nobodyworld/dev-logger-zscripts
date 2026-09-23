# Archive Decision

Status: **ARCHIVED REFERENCE IMPLEMENTATION — NOT PRODUCTION READY**

Decision date: **2026-09-22**

For the full project origin and evolution—from a June 2024 Django/source-context compiler used
to prepare code for ChatGPT web chats through the later log-toolkit and Repository Review
eras—see [HISTORY.md](HISTORY.md).

## Why development stops here

Zscripts accumulated multiple useful but increasingly separate eras:

1. the June 2024 Django/source-context compiler that prepared repository source and structural
   names for ChatGPT web chats that could not directly inspect the codebase;
2. a generalized structured development-log collection, normalization, redaction, diagnostics,
   and reporting toolkit;
3. a broad legacy helper collection kept temporarily for compatibility; and
4. a local Repository Review workspace with deterministic static analysis, SQLite snapshots,
   findings, comparisons, and bounded handoffs.

Each era and layer produced useful implementation and design evidence. Keeping all three under one
product, however, made the repository boundary increasingly unclear and caused old compatibility
surfaces to continue driving dependency, packaging, security, and maintenance work unrelated to
the newest product direction.

The repository is therefore preserved rather than refactored indefinitely. Future products
should start with a clear boundary in a new repository and selectively extract only the
contracts, tests, or implementation ideas they actually need.

## What is worth preserving

The archive intentionally retains:

- deterministic, read-only Repository Review discovery and Python AST analysis;
- relationship, finding, review-state, comparison, and handoff contracts;
- atomic SQLite snapshot persistence and migration history;
- hostile-input, cancellation, partial-evidence, privacy, and source-evidence safeguards;
- localhost API/CSP and packaged React workspace work;
- log normalization, redaction, adapter, diagnostics, and reporting implementation;
- supply-chain hardening, quality-gate design, tests, CodeQL history, and security reasoning;
- legacy-helper compatibility decisions and deprecation evidence;
- historical issues, pull requests, plans, audits, failures, and acceptance records.

No successor repository is declared by this archive decision. A future successor should be
created only when its narrower product boundary is clear.

## Known state at archival

- No stable production release was declared.
- Required hosted code-quality validation was kept separate from dependency auditing.
- The independent dependency audit still reported the known NLTK condition tracked in
  historical issue #54. It was not suppressed or dismissed.
- Legacy helper code remained compatibility material rather than a supported primary product.
- Deferred maintenance/refactor/product issues are closed because this repository is no longer
  an active work queue, not because those proposals were completed.
- Historical security controls and passing tests are evidence about tested commits, not a
  promise of ongoing safety or compatibility.

## Use of this repository

Treat the repository as source material and a reference implementation. If you fork or reuse
it, independently review dependencies, licenses, security posture, platform behavior, and tests,
and own all future maintenance.

Do not infer current support from old roadmap, beta, validation, or release documents. Where
historical documents say "current," their dates and recorded commit identities control.
