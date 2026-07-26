# Experimental Repository Review Workspace

Status: **PUBLIC BETA — ACTIVE DEVELOPMENT**

The repository review workspace is an experimental, local-first way to scan an
ordinary Python repository, store deterministic metadata snapshots, and explore
an Overview, searchable Symbols table, and focused relationship graphs. It does
not require an LLM, a cloud account, Docker, or an external database.

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
runtime behavior. Findings, scoring, comparisons, and handoffs remain later
roadmap phases.

## Determinism and persistence

Version `2` of the analyzer, evidence schema, and rule set produces content-based
repository, file, module, symbol, diagnostic, graph-node, relationship, cycle,
and snapshot identifiers.
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

Database schema v2 adds normalized graph, relationship, and cycle tables plus
import source locations. Migration is versioned, transactional, idempotent, and
does not reset existing local data. Snapshots created by analyzer/schema v1
remain openable and retain their original identity; relationship routes report
`supported: false` with empty data instead of reinterpreting them.

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
