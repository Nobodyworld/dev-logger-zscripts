# System Architecture

## Product identity

Zscripts' primary product is Repository Review: a local-first, read-only Python repository
workspace built around `Scan → Explore → Review → Compare → Handoff`.

The repository also maintains a log-toolkit CLI for collection, normalization, redaction,
reporting, diagnostics, adapters, observability, and extensions. Legacy helpers under
`zscripts/helpers/` are compatibility-only and governed separately by #73.

## Repository Review flow

```text
repository path
    ↓
RepositoryDiscovery ── bounded files / Git metadata
    ↓
PythonAnalyzer ─────── symbols / imports / static evidence
    ↓
RelationshipAnalyzer + FindingAnalyzer
    ↓
RepositoryReviewService
    ↓
SnapshotStore ─────── atomic SQLite snapshots / lifecycle / reviews / handoffs
    ↓
workspace_api (127.0.0.1 only)
    ↓
React workspace
Overview → Symbols → Relationships → Findings → Compare → Handoff
```

### Core modules

- `zscripts/infrastructure/repository_discovery.py` — bounded repository/file discovery and fixed allowlisted Git metadata queries.
- `zscripts/infrastructure/python_analyzer.py` — Python AST evidence without importing analyzed code.
- `zscripts/infrastructure/relationship_analysis.py` — bounded static relationship and graph evidence.
- `zscripts/infrastructure/finding_analysis.py` — deterministic metrics/finding candidates.
- `zscripts/infrastructure/comparison_analysis.py` — conservative immutable snapshot comparison.
- `zscripts/infrastructure/handoff_rendering.py` — bounded non-executable Markdown/JSON handoffs.
- `zscripts/infrastructure/snapshot_store.py` — SQLite persistence, migrations, finding lifecycle/reviews, and saved handoff integrity.
- `zscripts/application/repository_review.py` — application orchestration and public evidence shaping.
- `zscripts/interfaces/workspace_api.py` — strict localhost-only FastAPI surface and packaged frontend serving.
- `workspace-ui/src/` — React presentation consuming the same evidence model.

## Repository Review safety boundary

Analyzed repositories are hostile input. Repository Review reads bounded source bytes and
uses AST/static evidence; it does not import target modules or execute target project commands.
Symlinks are excluded. Source excerpts are explicit, bounded, hash-verified, and not persisted.
Failed/cancelled attempts do not become completed snapshots. Static evidence is conservative:
ambiguity, truncation, parse gaps, unsupported versions, and unknown state are surfaced rather
than guessed.

The workspace binds to `127.0.0.1` and uses restrictive browser headers. Ordinary Repository
Review does not require outbound runtime requests.

## Maintained log-toolkit flow

```text
file / stdin / explicitly selected command
    ↓
adapter
    ↓
normalized schema
    ↓
redaction / summary / explanation / report / diagnostics
```

`zscripts/application/services.py` coordinates adapters, schema validation, redaction and
command collection. Command collection uses `scripts/sandbox.py` process guardrails, which
are **not OS-level isolation**: they constrain working directory, environment, timeout and,
where supported, resource limits. A child process otherwise retains the launching account's
OS permissions.

Observability and extension infrastructure under `zscripts/observability/` and
`zscripts/extensions/` supports this maintained CLI surface.

## Dependency direction

Domain contracts do not depend on presentation. Infrastructure implements evidence/persistence
mechanics; application services orchestrate them; CLI/API/UI consume application contracts.
Repository Review writes its local state outside analyzed repositories.

## Current structural constraint

The product is well covered but several maintained modules are concentrated
(`snapshot_store.py`, RepositoryReviewService, workspace API route construction, and large
frontend views/styles). Issue #156 owns bounded behavior-preserving decomposition before #94
adds another persisted evidence layer.
