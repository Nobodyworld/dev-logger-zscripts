# Experimental Repository Review Workspace

Status: **PUBLIC BETA — ACTIVE DEVELOPMENT**

The repository review workspace is an experimental, local-first way to scan an
ordinary Python repository, store deterministic metadata snapshots, and explore
an Overview, searchable Symbols table, focused relationship graphs, and a
reviewable deterministic Findings queue. It does not require an LLM, a cloud
account, Docker, or an external database.

The MVP flow is:

```text
Local repository → bounded static scan → deterministic relationships
                                                   ↓
                                      atomic SQLite snapshot
                                                   ↓
                                  localhost API → React workspace
```

The existing log-normalization CLI remains supported. New repository-review
commands and routes are explicitly experimental.

## Install and start

For an editable checkout:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,workspace]"
pnpm --dir workspace-ui install --frozen-lockfile
pnpm --dir workspace-ui build
python scripts/build_workspace_assets.py
zscripts workspace
```

On macOS or Linux, activate with `source .venv/bin/activate`. The workspace
binds only to `127.0.0.1`; the default URL is
`http://127.0.0.1:8765`. It does not open a browser automatically.

The wheel build includes the generated frontend assets. A wheel consumer only
needs the workspace extra:

```sh
python -m pip install "zscripts[workspace]"
zscripts workspace
```

Run a scan without the UI:

```sh
zscripts experimental analyze /path/to/repository --json
zscripts experimental repositories --json
zscripts experimental snapshots REPOSITORY_ID --json
```

The JSON result uses the same canonical evidence contract as the UI and API.
Absolute repository paths and scan timing are absent from that canonical
representation.

## What the MVP shows

The Overview includes repository and Git state, completed snapshot identity,
analyzer/schema/rule-set versions, files analyzed and excluded, package/module
counts, class/function/method counts, parse gaps, and truncation state.

The Symbols view supports:

- search across qualified names and signatures;
- kind, module, and visibility filters;
- allowlisted column sorting and bounded pagination;
- classes, nested classes, functions, async functions, methods, and nested
  functions;
- signatures, annotations, decorators, docstring presence, bases, visibility,
  containment, and exact source ranges;
- an on-demand, bounded source drawer.

The Relationships view supports:

- module-import, derived package-dependency, containment, inheritance, and
  bounded type-reference modes;
- focused node search, depth `1`–`3`, allowlisted evidence filters, and cycle
  selection;
- deterministic SVG neighborhoods with a keyboard-selectable textual
  equivalent;
- incoming and outgoing evidence lists, exact repository-relative source
  locations, and an on-demand source panel;
- explicit loading, unsupported, error, empty, and truncation states.

The Findings view supports bounded server-side search, family/severity/
confidence/lifecycle/review filters, allowlisted sorting, pagination, source
evidence, and explicit review decisions. Review states are `new`, `reviewed`,
`accepted`, and `dismissed`; an optional allowlisted reason and a local note of
at most 2,000 characters are saved only after **Save review** is selected.
Optimistic review versions prevent one workspace from silently overwriting a
newer decision.

The Findings workspace shows the repository's current lifecycle. Selecting an
older supported snapshot establishes repository and evidence compatibility but
does not rewind review decisions or active/resolved state. Summary, queue, and
detail queries therefore use one current occurrence per stable finding from its
`last_seen_snapshot_id`.

Finding families cover dependency and inheritance cycles, exact duplicate-name
candidates, size, complexity, nesting, parameter count, coupling, inheritance
depth, public-documentation absence, complexity without nearby recognized test
evidence, and orphan-looking candidates. Candidate wording is intentional:
static evidence cannot establish a defect, dead code, runtime coverage, or
architectural intent.

Default thresholds are 80 function/method lines, 400 class lines, 1,000 module
lines, cyclomatic complexity 15, nesting depth 5, 8 parameters, fan-in/fan-out
12, and inheritance depth 5. Complexity starts at one and counts static branch
points (`if`, loops, conditional expressions, exception handlers, non-default
match cases, additional boolean operands, and comprehension conditions), while
excluding nested function/class bodies from the enclosing symbol. Nearby test
evidence requires both a recognized test path and a resolved or probable static
import of the source module.

Recent repositories and prior completed snapshots can be reopened. Failed and
cancelled attempts are tracked as attempts but never promoted as completed
snapshots.

## Static-analysis scope

The analyzer uses the Python standard-library `ast` module. It reads syntax; it
never imports analyzed modules or invokes framework setup.

It can establish:

- Python packages and modules from file layout;
- imports, aliases, relative-import levels, and explicit `__all__` exports;
- class/function/method containment and source ranges;
- class base expressions as written;
- signatures, annotations, decorators, async state, visibility, and docstring
  presence.
- unique internal import and class-base targets, conservative internal type
  references, containment, strongly connected components, fan-in/fan-out, and
  cycle-safe inheritance depth.

Relationship records use these types:

- `contains`: package-to-module, module-to-top-level-symbol, and lexical
  symbol-to-nested-symbol containment;
- `imports`: module imports resolved from absolute or relative syntax;
- `inherits`: one class-base candidate per written base expression;
- `references-type`: bounded names found in parameter/return annotations and
  statically declared class or attribute annotations.

Resolution status is never inferred from convenience:

- `resolved-static`: exactly one supported internal target;
- `probable-static`: one strongly evidenced internal target with incomplete
  export context;
- `ambiguous`: multiple supported targets remain;
- `unresolved-dynamic`: external, built-in, dynamic, or unsupported evidence
  has no internal edge.

It cannot prove:

- runtime call targets, dynamic imports, monkey-patched behavior, or generated
  objects;
- whether an unresolved import is installed or reachable at runtime;
- semantic equivalence, dead code, architectural intent, or security;
- framework behavior that requires imports, application setup, database access,
  migrations, plugins, or execution.

Malformed files produce bounded diagnostics and do not stop other files from
being analyzed. Strings and forward references are parsed only as bounded
textual names; annotations are never evaluated. Ordinary calls and assignments
do not imply composition, and this slice does not build a function-level call
graph. Resolved static evidence remains a source-level claim, not proof of
runtime behavior. Architecture scoring, comparisons, and handoffs remain later
roadmap phases.

## Determinism and persistence

Analyzer version `3`, evidence schema version `3`, and rule-set version `4`
produce content-based repository, file, module, symbol, diagnostic, graph-node,
relationship, cycle, metric, finding, and snapshot identifiers. Analyzer
version 3 requires a proven
same-module, import, alias, or supported static-export binding before resolving
a qualified symbol name. It also excludes `Literal` values and all but the
first type argument of `Annotated` from type-reference evidence. These
corrections intentionally change snapshot identity without changing the stored
evidence shape or database schema.
Canonical JSON uses sorted keys/records and LF termination. For unchanged source,
configuration, and analyzer versions, core evidence is byte-identical; wall-clock
timestamps and duration are deliberately outside the canonical payload.

Relationship identifiers hash the sorted semantic record, including type,
source, optional target or unresolved target text, resolution status, location,
analyzer version, and bounded textual evidence. Cycle identifiers hash sorted
node and edge membership. Snapshot identity includes both sets.

SQLite writes use foreign keys, explicit transactions, and atomic promotion.
Only a fully written evidence set can become a completed snapshot. Repeating an
unchanged scan reuses the same snapshot identity instead of creating duplicate
evidence rows.

Database schema v3 adds immutable metric/finding occurrences and
repository-scoped finding lifecycle, review, and append-only event records.
Database schema v4 adds repository-local analysis generations and reconciliation
status to mutable storage. Migration from v1–v3 is versioned, transactional,
idempotent, and does not reset existing local data. Older snapshots retain
their identity; unsupported finding routes return explicit empty data instead
of reinterpreting old evidence. Analyzer version `3`, evidence schema version
`3`, and rule-set version `4` are unchanged because generation and
reconciliation authority are excluded from canonical evidence.

Finding IDs hash the repository ID, rule ID/version, subject type, and sorted
stable subject keys. They deliberately exclude snapshot IDs, metric values,
paths, timestamps, lifecycle state, and review text. Completed scans reconcile
first-seen, evidence-updated, resolved, and reactivated events transactionally;
failed or cancelled scans cannot resolve findings. A completed scan resolves
missing findings only when it is the latest-started analysis for its repository,
is not truncated, and has no parse gaps. Authoritative incomplete scans retain
new, updated, and reactivated observations but report `truncated-scan` or
`parse-gaps` and create no absence-based resolution events. Late completions
still persist immutable snapshots but report
`superseded-by-newer-analysis` and cannot mutate lifecycle state. `dismissed`
is a human review decision and is distinct from automatic `resolved` evidence state.
Canonical snapshot evidence includes metrics and finding occurrences but never
review state, notes, or timestamps.

The Relationships workspace discovers focus nodes through a bounded server-side
query rather than only the summary sample. Search is case-insensitive over
qualified names, returns at most 100 deterministic results at a time, and
reports total matches and truncation. Cycle selection uses bounded exact node
lookup, so an omitted cycle member remains focusable. Neighborhood results and
source evidence are keyed to the complete snapshot, focus, mode, depth,
relationship filter, resolution filter, and node/edge-limit request.

The application database lives outside analyzed repositories:

| Platform | Default database |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Zscripts\repository-review.sqlite3` |
| macOS | `~/Library/Application Support/Zscripts/repository-review.sqlite3` |
| Linux | `${XDG_DATA_HOME:-~/.local/share}/zscripts/repository-review.sqlite3` |

Set `ZCRIPTS_DATA_DIR` or pass `--app-data-dir PATH` to use another directory.
Stop the workspace and delete `repository-review.sqlite3` to remove all saved
repository-review history. The MVP does not yet provide per-repository deletion.

## Read-only and privacy contract

Repository discovery is bounded before parsing:

- at most 5,000 included files;
- at most 1,000,000 bytes per file;
- at most 100,000,000 included bytes in total;
- at most 200 lines and 16,384 bytes in one source-evidence response.

The CLI exposes `--max-files`, `--max-file-size`, `--max-total-bytes`, and
repeatable `--exclude GLOB` overrides. A resource limit produces explicit
exclusion/truncation evidence rather than a silent partial result.

Default exclusions include Git internals, virtual environments, dependency and
build caches, generated output, binaries, `.gitignore` matches, `.env*`, key
files, and common credential/secret filenames. Sensitive filenames are replaced
by deterministic surrogates before persistence or export. Symlinks are not
followed; links outside the repository boundary are excluded.

The store contains local repository identity/path, Git metadata, relative file
paths, content hashes, symbol metadata, parse diagnostics, and versioned
evidence. It does **not** persist complete source files or source excerpts.
String and byte literal values in stored signature/default and decorator
displays are normalized to placeholders. Explicit `__all__` names and Python
identifiers remain metadata.
Finding notes are local user data and may contain sensitive text; they are not
canonical evidence or export data. Delete the SQLite database while the
workspace is stopped to remove snapshots, lifecycle history, decisions, and
notes.

The source drawer rereads only the selected repository-relative file, verifies
its current SHA-256 hash against the snapshot, rejects traversal and symlinks,
bounds the response, and does not persist the excerpt. Its response can contain
raw source because the user explicitly requested that local view.

Ordinary analysis makes no network request. The only subprocess use is a fixed,
no-shell allowlist of read-only Git metadata commands with hooks and optional
locks disabled. Repository contents never become command arguments. The server
uses same-origin routes, no CORS grant, a restrictive Content Security Policy,
and a loopback-only binding. Repository-derived text is rendered through React
escaping.

Relationship exploration is deliberately focused: neighborhood responses allow
depth `1`–`3`, at most 100 nodes and 200 edges, and explicit truncation.
Summary node lists are capped at 500 and cycle responses at 100 groups.
Traversal sorts nodes and edges before deterministic SCC and breadth-first
algorithms. A cycle group is a strongly connected component of resolved
internal imports or inheritance edges (including a resolved self-edge), not a
severity or finding.

Static analysis is not a malware or secret scanner. Review local evidence before
sharing it. Report suspected vulnerabilities through the private process in
[SECURITY.md](../SECURITY.md).

## Local API

The same process serves the SPA and these experimental routes:

- `GET /api/health`
- `GET /api/repositories`
- `POST /api/repositories/analyze`
- `GET /api/analyses/{analysis_id}`
- `POST /api/analyses/{analysis_id}/cancel`
- `GET /api/repositories/{repository_id}/snapshots`
- `GET /api/snapshots/{snapshot_id}`
- `GET /api/snapshots/{snapshot_id}/overview`
- `GET /api/snapshots/{snapshot_id}/symbols`
- `GET /api/snapshots/{snapshot_id}/source`
- `GET /api/snapshots/{snapshot_id}/relationships/summary`
- `GET /api/snapshots/{snapshot_id}/relationships`
- `GET /api/snapshots/{snapshot_id}/relationships/neighborhood`
- `GET /api/snapshots/{snapshot_id}/cycles`

Request models reject unknown fields. Validation responses are generic and do
not reflect user-supplied local paths. Symbol sort fields and SQL identifiers
are allowlisted; user values remain bound parameters.

Automatic Swagger and ReDoc interfaces are disabled so the strict CSP never
depends on hosted assets. Machine-readable OpenAPI remains available at
`/api/openapi.json`.

## Development and validation

The frontend is a private pnpm workspace with exact Node, pnpm, React, Vite,
TypeScript, test, lint, and format pins. Generated Vite output is ignored in the
checkout, copied into `zscripts/workspace_static` by
`scripts/build_workspace_assets.py`, and included as wheel package data.
Zipapp behavior remains CLI-only; the richer workspace is verified through the
wheel and localhost smoke tests.

Useful focused gates:

```sh
python scripts/quality_gate.py frontend-tests
python scripts/quality_gate.py repository-safety
python scripts/quality_gate.py snapshot-store
python scripts/quality_gate.py workspace-api
python scripts/quality_gate.py packaged-workspace
python scripts/quality_gate.py quality
```

Focused relationship tests live in `tests/repository_review` and cover stable
identities, resolution, SCCs, graph metrics, bounds, migrations, rollback, old
snapshots, API validation, frontend interaction, stale requests, and generated
medium/large performance fixtures.

See [Dependency Audit](DEPENDENCIES.md) for dependency/license rationale and
[Repository Review Workspace Roadmap](product/REPOSITORY_INTELLIGENCE_ROADMAP.md)
for the deliberately deferred phases.
