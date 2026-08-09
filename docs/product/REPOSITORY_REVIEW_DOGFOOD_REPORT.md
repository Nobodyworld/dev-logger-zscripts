# Repository Review Dogfood Report

## Post-polish rerun

### Decision

**FOCUSED POLISH CONFIRMED**

The complete sanitized `Scan → Explore → Review → Compare → Handoff` workflow
was rerun after #100–#104 merged. The five changes are observable end to end:
Handoff budgets are exact, the default Findings queue is materially smaller,
evidence limitations persist across views, snapshot choices are
distinguishable, and nested Git scope requires confirmation before analysis.

The workflow is clearer and more trustworthy than the historical measured
build. No product-code correction was needed in this evaluation branch. The
original report below remains the historical baseline and was not rewritten.

### Evaluated build and contracts

| Build or contract | Post-polish value |
| --- | --- |
| Exact polished `main` and evaluation starting SHA | `741a86c4a62fceb9e6e4c28584ffebfa32080d9d` |
| Prepared branch | `chore/repository-review-post-polish-dogfood` |
| Evaluation-branch final SHA | Recorded in the draft PR and final handoff after the commit exists; a commit cannot truthfully contain its own resulting SHA |
| Analyzer version | `3` |
| Evidence schema version | `4` |
| Rule-set version | `4` |
| SQLite schema version | `6` |
| Comparison format version | `2` |
| Handoff format version | `2` |
| Evaluation-harness output format | `1` |
| Evidence-status presentation contract | `1` |
| Snapshot-label presentation contract | `1` |
| Repository-scope presentation contract | `1` |
| Exact-main push run | `31293287366` |
| Exact-main `quality` job | `93194128205` |

The exact-main run used event `push`, workflow `CI`, and exact head
`741a86c4a62fceb9e6e4c28584ffebfa32080d9d`. Every substantive step completed
successfully before evaluation began. Exact-final-head hosted evidence is
recorded in the draft PR because it does not exist until this report is
committed and pushed.

### Environment, subjects, and sanitization

| Environment fact | Post-polish value |
| --- | --- |
| Operating system | Windows 11 Home, build 10.0.26200 |
| Python | 3.14.0 in an external disposable virtual environment |
| Python executable | External disposable environment; absolute path omitted |
| Node | 24.12.0 |
| pnpm | 10.18.1 |
| Git | 2.51.2.windows.1 |
| Logical processors | 12 |
| Visible memory | 15.8 GiB |
| Free memory before evaluation | 2.0 GiB |

The same ten public subject classes were evaluated: a clean exact-SHA clone of
Zscripts, the ordinary, relationship, and finding fixtures, generated medium,
large, and multipackage repositories, parse-gap and file-count-limited
subjects, and the generated cycle/repeated-name repository. A clean external
clone was used for the Zscripts subject because the harness integrity digest
intentionally walks every non-`.git` byte; running it against the developer
checkout spent unbounded time hashing ignored owner-local environments that
the analyzer itself excludes. The clean clone preserved the exact tracked
source, branch, Git SHA, configuration, scan limits, and application-service
path while removing owner-local ignored bytes from the public subject.

All raw JSON, SQLite data, fixture copies, browser images, and logs remained
under an external temporary evidence root. The committed evidence contains no
absolute path, username, machine name, private repository name, private SHA,
source excerpt, secret, or raw local output. Both result files independently
reported `sanitized: true`; neither contained a Windows absolute-path marker or
the local username. The public Zscripts SHA and public logical finding keys are
intentional reproducibility evidence.

The effective harness commands were:

```powershell
$run = Join-Path $env:TEMP 'zscripts-post-polish-dogfood\run-20260808-issue112'
$py = Join-Path $run 'venv\Scripts\python.exe'

& $py scripts/evaluate_repository_review.py generate `
  --root (Join-Path $run 'generated-fixtures')

& $py scripts/evaluate_repository_review.py evaluate `
  --subject "zscripts-public=$(Join-Path $run 'subjects\zscripts-public')" `
  --subject "existing-ordinary=$(Join-Path $run 'existing-fixtures\ordinary')" `
  --subject "existing-relationships=$(Join-Path $run 'existing-fixtures\relationships')" `
  --subject "existing-findings=$(Join-Path $run 'existing-fixtures\findings')" `
  --subject "public-medium=$(Join-Path $run 'generated-fixtures\public-medium')" `
  --subject "public-large=$(Join-Path $run 'generated-fixtures\public-large')" `
  --subject "public-multipackage=$(Join-Path $run 'generated-fixtures\public-multipackage')" `
  --subject "public-partial-parse-gap=$(Join-Path $run 'generated-fixtures\public-partial')" `
  --subject "public-cycles-repeated=$(Join-Path $run 'generated-fixtures\public-cycles-repeated')" `
  --output (Join-Path $run 'results\clean-default-subjects.json') `
  --data-directory (Join-Path $run 'data\clean-default-subjects') `
  --repeat 2 --max-files 5000 `
  --max-file-size-bytes 1000000 --max-total-bytes 100000000

& $py scripts/evaluate_repository_review.py evaluate `
  --subject "public-partial-truncated=$(Join-Path $run 'generated-fixtures\public-partial')" `
  --output (Join-Path $run 'results\truncated-subject.json') `
  --data-directory (Join-Path $run 'data\truncated-subject') `
  --repeat 2 --max-files 3 `
  --max-file-size-bytes 1000000 --max-total-bytes 100000000
```

### Determinism and repository integrity

All ten subjects passed all four harness invariants:

- repeated unchanged scans reused one snapshot identity;
- repeated canonical evidence was byte-identical;
- repository byte digests before and after analysis were equal; and
- saved Handoffs reopened with exact Markdown, normalized JSON, and digest.

Every scan emitted the stable phase sequence
`discovery → analysis → relationships → findings → storage → completed`.
Complete subjects reconciled finding lifecycle state. The Zscripts and
parse-gap subjects reported `parse-gaps`; the file-count-limited subject
reported `truncated-scan`; neither used incomplete absence as evidence of
resolution.

### Scan performance before and after

Each post-polish subject was scanned twice with Python `tracemalloc`. The
reported peak is Python allocation tracking only, not total process or native
memory. The historical run used Python 3.13.7; this run used Python 3.14.0 and
shared a host with other test workloads. Wall-clock values are therefore an
observed regression signal, not an attributable product benchmark.

| Subject | Before median ms | After median ms | Change | Before / after `tracemalloc` MiB | After files analyzed / discovered |
| --- | ---: | ---: | ---: | ---: | ---: |
| `zscripts-public` | 27,297 | 88,012 | +222.4% | 19.80 / 19.75 | 332 / 551 |
| `existing-ordinary` | 156 | 291 | +86.8% | 0.12 / 0.11 | 2 / 2 |
| `existing-relationships` | 247 | 513 | +107.9% | 0.61 / 0.15 | 8 / 8 |
| `existing-findings` | 277 | 554 | +100.0% | 0.17 / 0.17 | 9 / 9 |
| `public-medium` | 2,785 | 4,411 | +58.4% | 2.51 / 2.50 | 31 / 31 |
| `public-large` | 9,052 | 20,766 | +129.4% | 9.92 / 9.86 | 121 / 322 |
| `public-multipackage` | 2,868 | 3,370 | +17.5% | 1.67 / 1.63 | 39 / 39 |
| `public-partial-parse-gap` | 949 | 602 | -36.6% | 0.14 / 0.14 | 13 / 13 |
| `public-cycles-repeated` | 319 | 359 | +12.4% | 0.07 / 0.07 | 6 / 6 |
| `public-partial-truncated` | 250 | 273 | +9.3% | 0.04 / 0.04 | 3 / 13 |

The generated-subject evidence counts remained stable. Zscripts grew from 330
to 331 modules, 1,973 to 2,032 symbols, 9,710 to 9,969 relationships, and 996
to 1,036 findings as the focused-polish implementation and its regressions
entered the evaluated tree. Python allocation peaks stayed close to the
historical run. A quiet Python 3.13 rerun is needed before assigning the
wall-clock change to product code.

### Relationship resolution before and after

| Subject | Before resolved / unresolved-or-ambiguous | After resolved / probable / ambiguous / unresolved | Before / after unresolved ratio |
| --- | ---: | ---: | ---: |
| `zscripts-public` | 3,805 / 5,905 | 3,909 / 0 / 0 / 6,060 | 60.8% / 60.788% |
| `public-large` | 1,441 / 2,400 | 1,441 / 0 / 0 / 2,400 | 62.5% / 62.484% |
| `public-medium` | 781 / 0 | 781 / 0 / 0 / 0 | 0% / 0% |
| `public-multipackage` | 507 / 0 | 507 / 0 / 0 / 0 | 0% / 0% |

Across all post-polish subjects there were 6,754 resolved-static, zero
probable-static, one ambiguous, and 8,480 unresolved-dynamic relationships.
Zscripts' largest dependency cycle contained 11 modules. The largest sampled
bounded graph payload was 9,680 bytes with 19 relationships; its contended
query latency was 559 ms. The resolution ratio is effectively unchanged, as
expected because no analyzer contract changed.

### Finding families and high-signal queue

| Family | Before observed | After observed | Current sample | Useful / actionable | Valid low priority | Intentional design | False positive | Unsupported / ambiguous |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dependency cycle | 26 | 26 | 5 | 5 | 0 | 0 | 0 | 0 |
| Inheritance cycle | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Duplicate-name candidate | 90 | 90 | 5 | 3 | 1 | 1 | 0 | 0 |
| Oversized | 28 | 32 | 5 | 3 | 2 | 0 | 0 | 0 |
| Complexity | 13 | 13 | 5 | 4 | 1 | 0 | 0 | 0 |
| Nesting | 7 | 7 | 5 | 4 | 1 | 0 | 0 | 0 |
| Parameters | 14 | 14 | 5 | 2 | 3 | 0 | 0 | 0 |
| Coupling | 29 | 30 | 5 | 1 | 1 | 3 | 0 | 0 |
| Inheritance depth | 2 | 2 | 1 | 0 | 0 | 1 | 0 | 0 |
| Documentation | 2,351 | 2,384 | 5 | 0 | 2 | 3 | 0 | 0 |
| Test-evidence candidate | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 4 |
| Orphan candidate | 1,532 | 1,534 | 5 | 0 | 0 | 0 | 0 | 5 |

The post-polish deterministic sample contains 50 entries: 22 useful or
actionable, 11 valid low priority, 8 intentional design, zero false positives,
and 9 unsupported or ambiguous. Rule IDs and rule versions are unchanged, but
the historical first-five selection cannot be reused as exact parity evidence:
47 of 50 historical logical keys remain, only 17 are also in the current
first-five selection, and three old logical structures no longer exist. The
historical manifest remains untouched. The separate sanitized
[post-polish finding manifest](REPOSITORY_REVIEW_POST_POLISH_FINDING_SAMPLE.json)
uses the validated format-1 finding-sample contract: its effective scan limits
are machine-readable, stored occurrence subject types are retained for
auditability, and the post-polish classification table and aggregate statement
are regression-checked against its 50 entries. Its
`historical_sample_compatibility` block is additive audit metadata; it records
the current selection and compatibility result without rewriting the
historical sample.

For Zscripts, **Focused showed 70 of 1,036 findings**, a reduction of 966 or
**93.243%** relative to All. The complete summary still showed all 12 families,
including 570 documentation, 299 orphan, 60 duplicate-name, and 4 test-evidence
candidates. Browser acceptance proved one-action **Show all findings** and
**Restore focused queue**, explicit family/severity/confidence filters, and
review saves under both presets. Focused Python and frontend tests covered
optimistic conflict refresh under both policies without changing finding IDs,
rules, thresholds, lifecycle, or review state.

### #100 — Exact Handoff JSON budget

The selected public regression fixture produced these exact results:

- the mandatory Unicode envelope was 3,838 UTF-8 bytes and larger than its
  character count;
- a 3,838-byte cap succeeded exactly and a 3,837-byte cap returned the bounded
  mandatory-envelope error;
- the requested 4,000-byte constrained selection returned
  `The Handoff JSON budget is too small for required metadata.` rather than an
  oversized success;
- a 5,000-byte constrained selection rendered 4,035 bytes, deterministically
  omitted 96 JSON-budget items and 6 metrics, and produced digest
  `b27604e9cde1e51a6e67b16fcb0bafc91a352e12c038488c5ebc3178850dea39`;
- the default selected fixture rendered 66,229 JSON bytes and 14,805 Markdown
  characters; its truncation reflected selection-count limits, not a budget
  overflow; and
- two renders were equal and the digest covered the exact final Markdown and
  normalized JSON.

The packaged browser saved a 1,397-character Markdown / 5,004-byte JSON
Handoff. Reopen returned immutable output. Clipboard text was exactly 1,397
characters. Direct same-origin Markdown and JSON downloads were 1,397 and
5,004 bytes and matched the reopened strings byte for byte.

### #101 — High-signal Findings queue

Focused is now the understandable default: high/medium measured findings and
cycles are prominent, while the four conservative candidate families remain
counted and one action away. The queue banner explains the policy, active
constraints expose it, explicit filters clear it, and Restore Focused returns
to the same policy. The 93.243% reduction materially improves scan-to-review
flow without deleting or relabeling evidence.

### #102 — Persistent evidence status

The exact selected Zscripts snapshot had one parse gap. Overview, Symbols,
Relationships, Findings, Compare, and Handoff all displayed the limitation and
the lifecycle consequence. Compare and Handoff separately identified baseline
and target limitations and retained section compatibility wording.

Focused service/API regressions also covered complete evidence, truncation,
parse gaps, combined truncation plus gaps, superseded analysis, historical
observation unknown, unsupported historical schema, surface-specific support,
baseline-only limitations, target-only limitations, and per-section
compatibility. No partial absence was presented as proof of removal or
nonexistence.

### #103 — Distinguishable snapshot labels

Presentation version 1 remained consistent in the current-snapshot, Compare,
Handoff, and saved-Handoff contexts. The rendered label included UTC seconds,
branch, short Git SHA, snapshot suffix, parse-gap state, and clean worktree
state. Frontend regressions covered same-minute and equal-second snapshots,
same content on different branches, clean/dirty/staged/untracked observations,
historical observation unknown, truncation, parse gaps, and reopening a saved
B→C Handoff while A→B was active.

### #104 — Resolved Git-root confirmation

Rendered acceptance used whitespace-padded nested input and a deeply nested
directory. Before work began, the modal truthfully showed entered path,
canonical directory, and resolved Git root. Cancelling the modal created no
analysis. Confirming started one analysis of the root. A second confirmed scan
was cancelled after work began and was recorded as cancelled without a new
snapshot.

The final external browser database contained one repository identity, one
snapshot, three completed attempts (the two harness repeats plus one confirmed
browser scan), and one cancelled attempt. Root and nested scans therefore
deduplicated to one recent repository and one snapshot. Focused regressions
also covered direct root, relative and `..` input, non-Git directories, linked
worktree `.git` files, directory symlinks when supported, cancellation before
confirmation, and unchanged one-action API/CLI semantics.

### Workflow observations by view

- **Scan and Overview:** nested scope is explicit before work, cancellation is
  announced, the resolved repository is deduplicated, and partial evidence is
  now prominent rather than one metric cell.
- **Symbols:** the persistent banner remained visible; search returned bounded
  rows and the source drawer showed repository-relative, hash-verified evidence
  with line numbers and symbol metadata.
- **Relationships:** the banner, bounded SVG, keyboard-addressable node list,
  incoming/outgoing evidence, resolution statuses, and cycle selector remained
  mutually consistent. The textual equivalent carried exact evidence.
- **Findings:** Focused made measured findings reviewable without hiding the
  full family counts. Show All, Restore Focused, filters, source evidence, save,
  and review history were understandable.
- **Compare:** equal-snapshot behavior said no changes were expected, returned
  zero changes, and still preserved baseline/target parse-gap wording and all
  six section compatibility states.
- **Handoff:** limitations were visible before preview and carried into the
  output. Preview, save, reopen, clipboard, and exact same-origin download bytes
  worked. Follow-up context is still required for intent, ownership, runtime
  behavior, and priority.

### Persistence, Compare, and Handoff measurements

Review-decision reuse, optimistic conflicts, resolution/reactivation,
partial-scan resolution suppression, concurrent-analysis authority, and
migration/startup against disposable databases passed focused regressions.
The browser saved reviews from Focused and All and observed the same current
lifecycle summary.

The harness equal-snapshot comparison produced zero deltas for all subjects.
Zscripts' contended summary latency was 5,495.7 ms and response size 2,344
bytes; the largest generated-subject summary latency was 3,138.6 ms. These
latencies track the same non-equivalent environment slowdown as scan time and
should not be compared directly with the historical 19–27 ms focused
two-snapshot section queries.

The default harness Handoffs selected three sections and up to five findings.
Zscripts rendered 2,295 Markdown characters and 8,117 JSON bytes; save/reopen
integrity passed. The packaged browser's curated Handoff rendered in format 2,
kept all partial-evidence warnings, and reopened with exact digest and labels.

### Accessibility, responsive layout, and browser acceptance

The packaged application was exercised in the Codex in-app browser at desktop,
375 px, and a 200%-equivalent 640 px CSS viewport. Desktop document width was
1,265/1,265 px. The 375 px layout was 360/360 px and the 200%-equivalent layout
was 625/625 px: no horizontal page overflow occurred. The open mobile Handoff
was long (4,370 px), but usable. A 137-character nested path used
`overflow-wrap: anywhere`; all three scope values fit a 320 px dialog without
page overflow.

Rendered headings, labels, tab roles, status regions, alerts, graph text
equivalents, and selected/pressed states were present. App-authored inline
style attributes were zero. No animated or transitioning app element was
observed, and the reduced-motion-safe state therefore had no motion to remove.
Focus styling was a visible 2.4 px solid outline.

Two delivery checks are explicitly **inconclusive**, not passed. The in-app
browser's synthetic Tab command did not advance the active element, so a full
rendered keyboard traversal could not be proven. Its blob-download event also
did not surface even though exact same-origin download bytes passed through the
HTTP/API path. Frontend interaction tests cover both implementations, but this
report does not substitute those tests for rendered delivery evidence.

Page identity, nonblank content, framework-overlay absence, screenshot checks,
and target-flow interactions passed. The browser console had no warning or
error. Scripts and styles loaded only from the loopback origin. The packaged
CSP was `default-src 'self'; script-src 'self'; style-src 'self'; ...`;
`/api/docs` and `/redoc` returned 404, and `/api/openapi.json` returned 200.

### Local validation

The standalone focused Repository Review selection passed with **109 passed,
2 skipped**. The standalone full Python suite passed with **368 passed,
2 skipped, 13 warnings**. The `quality` profile passed all 26 operations in
315.769 seconds with **90.8015%** measured coverage against the 85% gate. It
also passed Ruff format and lint, mypy, Bandit, dependency audit, frozen
frontend install, frontend format/lint/typecheck, **88 frontend tests**, the
production build, repository-safety, snapshot-store and workspace-API tests,
packaged-workspace CSP smoke, helper boundaries, editable install, isolated
wheel/workspace smoke, zipapp, binary, documentation, and diagnostics checks.
The redaction check separately confirmed both removal of the fixture secret
and presence of the redaction marker.

Documentation validation passed **101 links across 110 Markdown files** (82
internal and 19 external), and `git diff --check` passed. Both explicit
Gitleaks commands passed with no leaks after scanning 144 commits.

Both required `pre-commit run --all-files` executions exited 1. In each pass,
every hook except `detect-secrets` passed; the only findings were the unchanged
fixture false positives at
`workspace-ui/src/test/RepositoryHeader.test.tsx:16` and
`workspace-ui/src/test/snapshotLabels.test.ts:18`, which remain tracked by
#111. Neither pass is represented as successful, and no fixture or scanner
configuration was changed.

The exact starting-main push gate was CI run `31293287366`, quality job
`93194128205`, for exact head
`741a86c4a62fceb9e6e4c28584ffebfa32080d9d`; every substantive step completed
successfully. The evaluation branch's exact-final-head hosted run and artifact
are necessarily recorded in the draft PR and handoff after this report commit
defines that final SHA.

### Safety and privacy

Repository bytes were unchanged for all ten subjects. Analysis remained
static and did not import target code. Output and SQLite writes were external.
The server bound only to `127.0.0.1`; rendered runtime assets were same-origin;
the console contained no CSP error; app-authored inline styles were absent; and
saved/downloaded output remained inert Markdown and JSON.

No private evidence, raw screenshot, raw harness result, absolute local path,
owner-local identifier, dependency change, advanced heuristic, architecture
classification, generic export, second language, desktop package, cloud/LLM
behavior, helper/Torch change, release, tag, publication, or repository-setting
change is part of this branch.

### Regressions, remaining defects, and proposed work

No focused-polish product regression was confirmed. The historical 4,087-byte
Handoff overflow is fixed. The two unchanged `detect-secrets` fixture findings
remain separately tracked by #111 and were not modified or folded into this
evaluation.

One evaluation-tooling proposal is warranted but does not block #81:

- **Title:** Document or bound public-clone integrity evaluation
- **Priority:** P2
- **Affected surface:** `scripts/evaluate_repository_review.py`
- **Evidence:** integrity hashing against a developer checkout traversed ignored
  owner-local environments after analysis, while a clean exact-SHA public clone
  completed reproducibly and retained all analyzer evidence counts.
- **Acceptance:** either require/document a clean public clone for repository
  subjects or bound integrity hashing to an explicit public manifest while
  retaining before/after byte equality and path sanitization.
- **Sequence:** evaluation tooling only; do not mix with product heuristics.

A quiet Python 3.13 performance confirmation is also recommended before using
the observed timing change as a release benchmark. It is measurement follow-up,
not evidence that one of #100–#104 failed.

### Product recommendations

- **#81:** close as completed after exact-final-head hosted quality succeeds.
  The focused-polish gate is satisfied.
- **#83 proposed confirmation:** “Post-polish dogfood is complete on the exact
  polished build. Focused polish is confirmed: Handoff budgets are exact,
  Focused reduces the default Zscripts queue by 93.243%, evidence status and
  snapshot labels persist across the workflow, and nested Git scope is
  confirmed before analysis. No new product regression was confirmed; #111
  remains separate.”
- **#94:** keep deferred. The existing factual workflow is now clearer, but
  unresolved evidence remains about 60.8% on Zscripts and another heuristic
  layer would add interpretation before a comparable performance baseline and
  stronger intent context exist.
- **#96:** keep generic exports deferred. Exact bounded Markdown/JSON already
  support preview, save, reopen, clipboard, and byte-identical download. Add a
  format only for a named downstream consumer.
- **Desktop packaging:** keep deferred. The packaged localhost application is
  functional, local-only, responsive, and CSP-clean; packaging would not solve
  the remaining evidence/intent and measurement questions.
- **#98:** keep a second language deferred from implementation. The completed
  Python harness can now be used to scope an acceptance template, but language
  expansion should begin only after a comparable quiet performance run and an
  explicit next-language decision.

### Final product decision

**FOCUSED POLISH CONFIRMED**

The polished product is materially clearer, more trustworthy, and more useful
than the original measured build. #81 may close after hosted validation. The
result does not justify silently starting #94, #96, desktop packaging, #98, or
any other deferred expansion.

## Executive Decision

**PROCEED TO FOCUSED POLISH**

The current Python Repository Review workflow is useful today for a bounded,
evidence-first review. Symbols with on-demand source, focused Relationships,
partial-aware Compare, and immutable Handoff outputs form a coherent
`Scan → Explore → Review → Compare → Handoff` path. The product should not add
another heuristic layer, generic exports, desktop packaging, or another
language yet.

The next work should improve trust and prioritization inside the existing
workflow:

1. make partial and truncated evidence impossible to overlook;
2. make snapshot choices distinguishable;
3. reduce the default Findings queue's low-signal volume;
4. enforce Handoff byte budgets exactly; and
5. show the resolved Git root before a nested path is scanned.

These are focused polish tasks for issue #81. They do not require an
architecture redesign.

## Evaluated Build

The public Zscripts commit is reproducibility evidence and is recorded
explicitly. Measurements in this report were collected against exact build
`678356bf4e23730886abaffd84186d0c5d3627f7`. Private or anonymized evaluated
repository SHAs remain excluded. The correction commit that adds this
provenance and the finding-sample audit changes report/audit material, not the
measured product behavior; it must not be interpreted as the measured build
without a complete evaluation rerun.

| Build or contract | Evaluated value |
| --- | --- |
| Pre-work main SHA | `03fe7f7dad3b0f36c5bc6ea000541cc58e8e6d08` |
| Exact measured dogfood build SHA | `678356bf4e23730886abaffd84186d0c5d3627f7` |
| Analyzer version | `3` |
| Evidence schema version | `4` |
| Rule-set version | `4` |
| SQLite schema version | `6` |
| Comparison format version | `2` |
| Handoff format version | `2` |
| Evaluation-harness output format | `1` |
| Hosted run | `30485231630` |
| Quality job | `90689123447` |
| Artifact | `8737415845` |
| Artifact digest | `sha256:a1173f96e1fdd158b02438baeafa3e4d02651a2df4413a753d622bcfbe1283ba` |

| Environment fact | Evaluated value |
| --- | --- |
| Operating system | Windows 11 Home, build 10.0.26200 |
| Python | 3.13.7 in a disposable virtual environment |
| Node | 24.12.0 |
| pnpm | 10.18.1 |
| Git | 2.51.2.windows.1 |
| Logical processors | 12 |
| Visible memory | 15.8 GiB |
| Free memory during evaluation | varied from about 1.1 to 4.5 GiB |

The pre-work push-triggered `quality` job passed every substantive Python,
frontend, helper, security, documentation, packaging, diagnostics, and
artifact step before evaluation began.

## Methodology

The evaluation combined:

- repeated scans through `RepositoryReviewService`;
- purpose-built public fixtures generated outside the repository;
- bounded API/service queries;
- a disposable SQLite database;
- focused lifecycle, comparison, and handoff scenarios;
- existing regression suites for destructive and hostile cases; and
- rendered packaged-workspace QA in installed Chrome at desktop, 375 px, and a
  200% zoom-equivalent viewport.

Each timed public subject was scanned twice with Python `tracemalloc` enabled.
Reported time is therefore instrumented wall-clock time on a memory-constrained
developer machine, not a production benchmark. `tracemalloc` records Python
allocations only; it is not complete process or native memory.

The managed browser-control surfaces rejected loopback navigation before the
page loaded. Rendered QA therefore used the installed Chrome browser through
its local DevTools protocol, with no installed dependency or repository
change. The exact managed-browser failure is retained in the local raw record.

Quantitative results are tables rather than charts because the sample consists
of ten discrete fixtures and exact audit values are more useful than a visual
trend. No statistical significance is claimed.

## Evaluation Subjects

Only public, reproducible subjects were used. No private or owner-local
repository was needed.

| Anonymous label | Purpose |
| --- | --- |
| `zscripts-public` | Zscripts itself, including its public test fixtures |
| `existing-ordinary` | Existing ordinary Repository Review fixture |
| `existing-relationships` | Existing relationship-resolution fixture |
| `existing-findings` | Existing finding-rule fixture |
| `public-medium` | 31-module, 360-symbol generated repository |
| `public-large` | 121 analyzed modules, 1,200 symbols, and 201 ignored/generated files |
| `public-multipackage` | Three-package generated repository |
| `public-partial-parse-gap` | Valid modules plus one malformed Python file |
| `public-partial-truncated` | File-count-limited scan of the partial fixture |
| `public-cycles-repeated` | Intentional cycles and repeated public names |

One methodology correction was important: selecting a path inside a Git
worktree correctly resolves to the Git root. Standalone fixture measurements
therefore used copies outside the Zscripts worktree. The initial root-resolved
measurements were discarded.

## Sanitization Policy

The committed evidence contains:

- anonymous labels;
- aggregate counts and bounded timings;
- generalized observations; and
- public fixture descriptions.

It contains no absolute path, username, organization name, private repository
name, source excerpt, private or anonymized repository SHA, secret, screenshot,
or raw generated report. The exact public Zscripts SHA above is intentionally
included as reproducibility evidence. Machine-readable raw output and browser
screenshots remained in an ignored temporary directory outside Git history.

The evaluator independently rejects output or SQLite locations inside any
analyzed repository. It emits neither source text nor absolute subject paths,
and it hashes repository bytes before and after a scan to report only equality.

## Reproducible Evaluation Harness

`scripts/evaluate_repository_review.py` adds two dependency-free commands:

- `generate`, which creates deterministic public fixtures at an explicit empty
  external root; and
- `evaluate`, which accepts anonymous `label=path` subjects and explicit
  external output and data locations.

The harness calls existing application services. It does not reproduce
analysis logic. It bounds repeat count, finding samples, graph focuses, nodes,
and edges; records scan, relationship, finding, persistence, comparison, and
handoff aggregates; and verifies repeated canonical identity and repository
byte equality.

Regression coverage proves sanitization, deterministic fixture generation,
repeated scan identity, scan limits, graph/sample bounds, output-path safety,
saved-handoff integrity, and the command-line contract.

## Product Workflow Results

### Scan and Overview

Repository entry is understandable, recent repositories reopen successfully,
and the progress phases are stable:

`discovery → analysis → relationships → findings → storage → completed`

Cancellation preserved the previously committed finding state. A truncated
scan stored observed evidence without resolving omitted findings. A parse-gap
scan likewise skipped absence-based reconciliation.

Overview is a useful first inventory, but partial state is not prominent
enough. In rendered QA, a truncated snapshot appeared primarily as
`Truncated: Yes` inside a wide metric grid. Findings and Compare provided
stronger warning banners for the same uncertainty.

Selecting a nested path in a Git worktree resolving to the worktree root is
correct, but the pre-scan UI does not make that scope change obvious enough.

### Symbols

Search, kind/module/visibility filters, sorting, and pagination remained
bounded. The selected symbol and source drawer matched:

- qualified symbol: the selected public class;
- repository-relative path only;
- exact line range; and
- two bounded source lines.

The drawer closed cleanly and showed annotations, decorators, docstring state,
and async state. Existing deferred-response regressions cover stale success,
stale rejection, drawer close, and unmount behavior.

Symbols is one of the highest-value views because it answers “where is this
thing and what is its bounded evidence?” without persisting source.

### Relationships

Module, package, inheritance, containment, and type modes loaded as bounded
queries. Node focus, depth, resolution filtering, incoming/outgoing lists, and
the textual node equivalent were usable.

The rendered inheritance case correctly represented an unavailable target from
a partial snapshot as `unresolved-dynamic`; it did not invent a resolved edge.
The textual list was more informative than the sparse SVG for a one-node
neighborhood. This is acceptable: the SVG provides orientation while the
lists carry exact evidence.

Cycle-first exploration was useful on the intentional-cycle fixtures.
Neighborhood latency remained small after analysis; the largest measured
bounded query was 126 ms on Zscripts.

### Findings

Review decisions, notes, optimistic conflicts, resolution, and reactivation
worked as designed:

- an accepted decision advanced to review version 1;
- a stale version produced a conflict;
- the finding resolved after complete contrary evidence;
- the accepted decision remained attached while resolved;
- the finding reactivated when its evidence returned; and
- the accepted decision remained attached after reactivation.

Cancellation preserved prior state. Truncation set
`reconciliation_complete=false` with `truncated-scan` and preserved findings
that were not observed.

The queue's default signal hierarchy is the largest product problem. Across
the ten subject observations, documentation and orphan candidates accounted
for 3,883 of 4,096 family-classified findings (94.8%). They are conservative
candidates rather than false claims, but they obscure the smaller cycle,
complexity, coupling, and oversized sets.

### Compare

Compare was factual and useful. A public baseline-to-target scenario reported
one added file, one changed file, one added and one changed symbol, four added
relationships, 27 metric deltas, and five finding-occurrence deltas.

The partial target scenario visibly said:

`Files evidence is partial: target-truncated.`

It used `not observed in target` for absent symbols, relationships, cycles,
metrics, and findings rather than claiming removals. Existing regressions cover
partial baseline, partial target, both partial, parse gaps, unsupported
versions, complete additions, and complete removals.

Section requests took 19–27 ms in the focused public scenario. The largest
section payload was 12.7 KiB for 27 metric deltas.

Snapshot selectors were hard to distinguish when four scans completed within
the same displayed minute. Observation facts are present in Compare, but the
top-level current-snapshot selector used identical display labels.

### Handoff

A multi-section handoff selected ten deltas and two findings across all eight
allowed sections. Rendering took 29 ms and produced 2,632 Markdown characters
and 12,762 JSON bytes without truncation.

Save/reopen returned the exact Markdown, normalized JSON, and digest. Markdown
and JSON service downloads matched the exact digested UTF-8 bytes. The rendered
saved preview remained marked immutable, and clipboard QA announced
`Markdown copied to the clipboard.`

Forced truncation proved that Markdown is capped exactly at the configured
character budget and that omitted counts are recorded. It also exposed one
confirmed defect: with a deliberately small 4,000-byte JSON budget, the final
metadata-only JSON was 4,087 bytes after selected evidence had been omitted.
The renderer performs only one post-omission size check. It should either
enforce the exact final cap or reject a budget too small for mandatory
metadata.

The existing Markdown/JSON handoff is concise enough for a new reviewer when
the selector is curated. Follow-up questions are still required for intent,
runtime behavior, ownership, and priority; the static handoff correctly does
not pretend to answer them.

## Finding-Family Review

Counts are per subject observation and intentionally not deduplicated across a
fixture embedded in Zscripts and the same fixture evaluated standalone. The
bounded manual sample used the `zscripts-public` snapshot
`d283a1622b361e0ff44844550525b05da2e04683524dd3bb8d017e2b116e14d6`
from exact build `678356bf4e23730886abaffd84186d0c5d3627f7`, under the scan
limits recorded in the evaluation output.

Selection is deterministic: sort all stored findings by `(family, finding_id)`,
then select the first five per family, or every finding when fewer than five
exist. The sanitized
[finding-sample manifest](REPOSITORY_REVIEW_DOGFOOD_FINDING_SAMPLE.json)
records all 50 selected entries using stable public logical finding keys and
their selection rank from the finding-ID ordering, plus rule and subject types,
manual classifications, and bounded generalized rationale codes. The SHA
fields use fixed-size components that concatenate to the exact public
identifiers, avoiding false secret-scanner positives without an allowlist. The
manifest contains neither paths nor source excerpts. Categories below sum
exactly to that manifest. The judgments are directional manual product
evidence, not statistical estimates.

| Family | Observed | Reviewed | Useful/actionable | Valid, low priority | Intentional design | False positive | Unsupported/ambiguous | Assessment |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Dependency cycle | 26 | 5 | 3 | 1 | 1 | 0 | 0 | Strong evidence; keep prominent |
| Inheritance cycle | 0 | 0 | 0 | 0 | 0 | 0 | 0 | No evaluated occurrence |
| Duplicate name candidate | 90 | 5 | 2 | 1 | 2 | 0 | 0 | Useful only after intent-aware triage |
| Oversized | 28 | 5 | 4 | 1 | 0 | 0 | 0 | High-value factual threshold |
| Complexity | 13 | 5 | 4 | 1 | 0 | 0 | 0 | Useful review starting point |
| Nesting | 7 | 5 | 3 | 1 | 1 | 0 | 0 | Useful but should not dominate |
| Parameters | 14 | 5 | 1 | 3 | 1 | 0 | 0 | Mostly context-dependent |
| Coupling | 29 | 5 | 4 | 1 | 0 | 0 | 0 | Useful with Relationships evidence |
| Inheritance depth | 2 | 1 | 0 | 0 | 1 | 0 | 0 | Evaluated item was an intentional fixture |
| Documentation | 2,351 | 5 | 0 | 2 | 3 | 0 | 0 | Too noisy for the default queue |
| Test-evidence candidate | 4 | 4 | 0 | 0 | 0 | 0 | 4 | Candidate language is necessary |
| Orphan candidate | 1,532 | 5 | 0 | 0 | 0 | 0 | 5 | Too noisy without call/export context |

The rules behaved conservatively. The product problem is ranking and default
visibility, not unsupported severity claims.

## Performance

| Subject | Median scan ms | `tracemalloc` MiB | Files analyzed / discovered | Modules | Symbols | Relationships | Cycles | Findings | Gaps | Truncated |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `zscripts-public` | 27,297 | 19.80 | 331 / 540 | 330 | 1,973 | 9,710 | 8 | 996 | 1 | No |
| `public-medium` | 2,785 | 2.51 | 31 / 31 | 31 | 360 | 781 | 1 | 373 | 0 | No |
| `public-large` | 9,052 | 9.92 | 121 / 322 | 121 | 1,200 | 3,841 | 1 | 2,411 | 0 | No |
| `public-multipackage` | 2,868 | 1.67 | 39 / 39 | 39 | 216 | 507 | 12 | 234 | 0 | No |
| `public-partial-parse-gap` | 949 | 0.14 | 13 / 13 | 12 | 12 | 12 | 0 | 24 | 1 | No |
| `public-cycles-repeated` | 319 | 0.07 | 6 / 6 | 6 | 4 | 20 | 2 | 11 | 0 | No |
| `existing-ordinary` | 156 | 0.12 | 2 / 2 | 2 | 5 | 25 | 0 | 3 | 0 | No |
| `existing-relationships` | 247 | 0.61 | 8 / 8 | 8 | 13 | 42 | 1 | 19 | 0 | No |
| `existing-findings` | 277 | 0.17 | 9 / 9 | 9 | 16 | 36 | 1 | 21 | 0 | No |
| `public-partial-truncated` | 250 | 0.04 | 3 / 13 | 2 | 2 | 2 | 0 | 4 | 1 | Yes |

Relationship resolution was deterministic. Zscripts produced 3,805
`resolved-static` and 5,905 `unresolved-dynamic` relationships, an unresolved
or ambiguous ratio of 60.8%. The generated large repository produced 1,441
resolved and 2,400 unresolved relationships, a 62.5% ratio. The generated
medium and multipackage subjects resolved every relationship because their
imports and types were deliberately explicit.

High unresolved ratios are not automatically defects: containment is resolved,
while many external imports, annotations, and unsupported dynamic references
must remain unresolved. The UI's status filters and evidence panel made that
distinction inspectable.

All repeated scans reused the same snapshot identity and canonical bytes. All
ten before/after repository byte digests were equal.

## Accessibility and Layout

Rendered QA found:

- semantic H1/H2/H3 structure in each view;
- labels on repository, search, filter, snapshot, and handoff controls;
- tablist/tab/selected semantics on comparison and handoff section selectors;
- `role=status` and `role=alert` messages for partial, selection, copy, and
  failure states;
- keyboard-selectable rows and graph-node text equivalents;
- no keyboard trap across an 80-step Handoff traversal: the first control
  repeated at steps 33 and 66;
- a visible 3 px solid focus outline on every interactive element traversed;
- reduced-motion media matching with zero visible animated elements;
- no horizontal document overflow at desktop, 375 px, or the 200%-zoom
  equivalent; and
- no inline application styles in any inspected state.

The 375 px Handoff remained usable but long: its content height exceeded 3,400
px when an immutable preview was open. This is a density cost, not an overflow
or keyboard blocker.

## Safety and Privacy

The following checks passed:

- analyzed repository bytes were unchanged;
- discovery and analysis used static file/AST evidence and did not import or
  execute target code;
- output and SQLite writes were outside analyzed repositories;
- symlink escape and excluded-source requests are rejected by existing safety
  regressions;
- canonical/public evidence contained no absolute subject path;
- the committed tree contains no raw local evaluation output;
- all 25 rendered runtime requests stayed on the loopback origin;
- the browser console had no warning, error, or CSP entry;
- the packaged CSP remained
  `default-src 'self'; script-src 'self'; style-src 'self'; ...`;
- the application bound only to `127.0.0.1`;
- `/api/docs` and `/redoc` returned 404;
- `/api/openapi.json` returned 200;
- saved-handoff corruption is rejected by persistence tests;
- exact Markdown/JSON remained inert downloads; and
- rendered pages contained no inline `style` attributes.

## Confirmed Defects

### Fixed in this evaluation PR

**Repeated file-count diagnostics could collide during snapshot persistence.**
When several omitted files produced the same content-derived resource-limit
diagnostic, the second truncated scan could violate the SQLite diagnostic
primary key. The application service now deduplicates identical diagnostics by
stable diagnostic ID before canonical ordering and persistence. The repeated
limited-scan harness regression proves deterministic reuse.

This was the only product-code correction. Evaluation could not measure
repeated truncated scans reproducibly without it.

### Proposed follow-up work

The proposals were reviewed and are now tracked under the focused-polish
umbrella #81. The approved sequence is:

1. [#100](https://github.com/Nobodyworld/dev-logger-zscripts/issues/100);
2. [#101](https://github.com/Nobodyworld/dev-logger-zscripts/issues/101) and
   [#102](https://github.com/Nobodyworld/dev-logger-zscripts/issues/102) in
   parallel;
3. [#103](https://github.com/Nobodyworld/dev-logger-zscripts/issues/103); and
4. [#104](https://github.com/Nobodyworld/dev-logger-zscripts/issues/104).

#### 1. [#100 — Enforce the exact final Handoff JSON byte budget](https://github.com/Nobodyworld/dev-logger-zscripts/issues/100)

- **Priority:** P1
- **View:** Handoff
- **Evidence:** a 4,000-byte forced budget produced 4,087 final bytes after
  evidence omission because mandatory metadata and new warnings were not
  checked again.
- **Acceptance:** final normalized JSON is at or below the configured budget,
  or the request fails with a bounded message that the mandatory envelope
  cannot fit; digest, saved record, and download bytes cover that exact output.
- **Sequence:** first.

#### 2. [#101 — Add a high-signal default Findings queue](https://github.com/Nobodyworld/dev-logger-zscripts/issues/101)

- **Priority:** P1
- **View:** Findings
- **Evidence:** documentation and orphan candidates were 94.8% of
  family-classified observations; bounded samples were overwhelmingly
  intentional, low priority, or ambiguous.
- **Acceptance:** default queue emphasizes cycles, high/medium severities, and
  higher-confidence metric findings; documentation and orphan families remain
  one action away with preserved counts; no rule or lifecycle semantics change.
- **Sequence:** second.

#### 3. [#102 — Show persistent partial-evidence status across repository views](https://github.com/Nobodyworld/dev-logger-zscripts/issues/102)

- **Priority:** P1
- **Views:** Overview, Symbols, Relationships, Compare, Handoff
- **Evidence:** the truncated Overview showed the state mainly as one metric
  cell, while Findings and Compare used clear warning banners.
- **Acceptance:** every evidence view shows a consistent banner with
  truncation/parse-gap reason and resolution-suppression semantics; colors are
  not the only signal.
- **Sequence:** second, parallel with Findings triage.

#### 4. [#103 — Make repository snapshots distinguishable in selectors](https://github.com/Nobodyworld/dev-logger-zscripts/issues/103)

- **Priority:** P1
- **Views:** Overview, Compare, Handoff
- **Evidence:** four snapshot choices completed within one minute and rendered
  identical labels in the current-snapshot selector.
- **Acceptance:** labels include seconds plus a short observation fact or
  non-sensitive snapshot suffix, and visibly mark partial/unknown state;
  accessible names contain the same distinction.
- **Sequence:** third.

#### 5. [#104 — Confirm the resolved Git root before scanning a nested path](https://github.com/Nobodyworld/dev-logger-zscripts/issues/104)

- **Priority:** P2
- **View:** Repository entry
- **Evidence:** an initial fixture measurement selected a nested path and
  correctly scanned the surrounding Git worktree, changing a two-file subject
  into a 540-file scan.
- **Acceptance:** before work starts, show the resolved root when it differs
  from the entered path; require one explicit confirmation; retain
  read-only/local behavior and recent-repository semantics.
- **Sequence:** fourth.

## High-Value Polish

Issue #81 should be limited to the five proposals above plus regression-driven
accessibility fixes if new manual testing finds them. It should not become a
visual redesign.

The useful product hierarchy is:

1. source-backed symbol inspection;
2. cycle and focused relationship exploration;
3. factual comparison with uncertainty;
4. curated handoff output; and
5. findings after signal-oriented filtering.

Polish should reinforce that sequence.

## Deferred or Rejected Work

- Architecture and paradigm scoring are deferred because current factual
  evidence is useful and the queue first needs better prioritization.
- Generic CSV/XLSX/GraphML/SVG/PNG export is not justified by this evaluation.
  The bounded Markdown and JSON handoff already covers the reviewer use case.
- Desktop packaging is not justified yet. Loopback startup is functional and
  the main friction is product-state clarity, not browser chrome.
- A second language is not justified until the Python workflow completes one
  focused polish cycle and the same dogfood harness defines its acceptance
  baseline.
- LLM, cloud, repository mutation, helper cleanup, Torch changes, releases, and
  publication remain outside this product decision.

## Recommendation for #81

Use #81 as the focused-polish umbrella for #100–#104, in the approved sequence
above. Preserve the existing architecture and information design. Rerun the
dogfood harness after those issues close before reconsidering deferred product
expansion.

## Recommendation for #94

Defer at medium priority. Advanced heuristics and architecture classification
would add more candidate volume before the product has solved evidence
ranking. Reconsider after #100–#104 close and the dogfood harness confirms that
users can reliably separate high-signal facts from conservative candidates.

## Recommendation for #96

Defer generic exports. Markdown and normalized JSON were deterministic,
bounded, saved, reopened, copied, and downloaded. Add a format only when a
specific downstream consumer cannot use those contracts. Reconsider after
#100–#104 close and the dogfood harness is rerun.

## Recommendation for Desktop Packaging

Defer. The packaged localhost workspace passed layout, keyboard, CSP,
no-outbound, and console checks. Desktop packaging would not address the
identified product bottlenecks. Reconsider after #100–#104 close and the
dogfood harness is rerun.

## Recommendation for #98 Next Language

Defer until after focused Python polish. The evaluator and report structure
should become the acceptance template for any future language, including
determinism, partial evidence, unresolved ratios, finding noise, and bounded
rendered QA. Reconsider after #100–#104 close and the dogfood harness is rerun.

## Exit Decision

**PROCEED TO FOCUSED POLISH**

The product is useful, bounded, deterministic, and safe enough to improve in
place. The next release of effort should increase trust and reduce review
friction, not broaden analysis scope.
