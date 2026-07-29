# Repository Review Dogfood Report

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
