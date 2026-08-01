# ToolkitService API Reference

`zscripts.application.services.ToolkitService` orchestrates adapters, sandbox
execution, schema validation, and guardrails. The methods below represent the
primary integration surface for automation.

## Construction

```python
from zscripts.infrastructure import build_toolkit_service
from zscripts.infrastructure.adapters import AdapterRegistry
from zscripts import get_default_config

registry = AdapterRegistry()
config = get_default_config()
service = build_toolkit_service(config, adapter_registry=registry)
```

## Methods

### `collect_logs(*, adapter_key, input_path, command, stdin_fallback, redact)`
- Resolves the requested adapter and captures raw logs from either a sandboxed
  command, an input path, or STDIN.
- Rejects empty STDIN payloads and ensures command sequences include an
  executable token before invoking the sandbox.
- When `redact=True`, the configured redactor masks sensitive substrings before
  returning the payload.

### `parse_logs(*, adapter_key, raw_text)`
- Delegates parsing to the resolved adapter and validates the resulting
  `NormalizedLog` document via the configured schema validator.

### `summarize_logs(*, adapter_key, raw_text)` and `explain_logs(...)`
- Parse logs as above and invoke adapter-specific summary/explanation helpers to
  produce CLI-friendly prose.

### `guardrails_snapshot()`
- Returns a JSON-serialisable mapping describing sandbox allow-listed paths,
  timeout, and whether dangerous mode is active.

### `redact_text(text)`
- Applies the configured redaction pipeline to arbitrary text, enabling manual
  scrubbing of logs before sharing with third parties.

### `list_examples(adapter_filter=None)`
- Lists bundled example log paths as strings, optionally filtered to a single
  adapter.

## Error Handling

- Raises `ValueError` when no log source is provided or when STDIN is empty.
- Raises `ValueError` when `command` lacks an executable token; callers should
  surface the message to end users (the CLI handles this automatically).

## Usage Tips

- Cache the constructed service for the lifetime of your process so sandbox
  runners can be reused efficiently.
- Consider applying your own redactors by wrapping the configured one if custom
  patterns are needed for organisation-specific secrets.
- Always validate adapter identifiers against `AdapterRegistry.available()` to
  provide meaningful feedback in user interfaces.

## Experimental Repository Review API

The loopback-only workspace also exposes versioned snapshot evidence:

- `GET /api/snapshots/{snapshot_id}/evidence-status?surface={surface}`
- `GET /api/snapshots/{snapshot_id}/relationships/summary`
- `GET /api/snapshots/{snapshot_id}/relationships`
- `GET /api/snapshots/{snapshot_id}/relationships/nodes`
- `GET /api/snapshots/{snapshot_id}/relationships/neighborhood`
- `GET /api/snapshots/{snapshot_id}/cycles`

The evidence-status response is strict, bounded, and presentation-only. The
allowlisted `surface` values are `generic`, `overview`, `symbols`,
`relationships`, and `findings`; omission defaults to `generic`, and invalid
values receive the generic validation response. The payload has
`presentation_version: "1"`, the applied `surface`, exact `snapshot_id`, `evidence_complete`,
`observation_state_known`, `lifecycle_reconciled`, the bounded
`reconciliation_skip_reason`, and deterministically ordered `limitations`.
Each limitation has `code`, `category`, `consequence`, and nullable `count`.
Codes are `snapshot-truncated`, `snapshot-parse-gaps`,
`snapshot-schema-unsupported`, `observation-state-unknown`,
`lifecycle-truncated-scan`, `lifecycle-parse-gaps`, `lifecycle-superseded`, and
`lifecycle-analysis-status-unavailable`. Complete supported snapshots return an
empty limitation list. Missing snapshots return a generic `404`; responses do
not include paths or source.

The service reads the immutable observations and completed analysis associated
with that exact snapshot. It does not use the newest repository scan. Generic
status stays neutral for readable schema versions 1–4. Overview and Symbols
support schema v1+, Relationships v2+, and Findings v3+; only a surface below
its minimum receives `snapshot-schema-unsupported`. Malformed, non-positive,
and newer schemas are unsupported for every surface. Compare and Handoff use
generic status for truncation, parse gaps, observation state, and lifecycle
authority while their per-section compatibility records remain authoritative
for schema/version support. Migrated observation-unknown snapshots remain
selectable with an explicit limitation. Snapshot truncation is distinct from
the `truncated` flag on a bounded relationship/node/neighborhood response.

Graph modes are `modules`, `packages`, `inheritance`, `containment`, and
`types`. Relationship filters are allowlisted to `contains`, `imports`,
`inherits`, and `references-type`; resolution filters are `resolved-static`,
`probable-static`, `ambiguous`, and `unresolved-dynamic`.

The node route applies graph-mode filtering and case-insensitive qualified-name
search on the server. Results are ordered deterministically and paginated to at
most 100 nodes. Repeated `node_ids` parameters provide bounded exact lookup for
cycle members omitted from the summary's initial node sample. The response
includes the total match count and an explicit `truncated` flag.

Neighborhood depth is limited to 3, with maximum response bounds of 100 nodes
and 200 edges. Cycle responses are limited to 100 groups. Responses include an
explicit `truncated` flag and source evidence as repository-relative path,
line, and column only. Analyzer/schema v1 snapshots return `supported: false`
with empty relationship data. Automatic Swagger and ReDoc pages remain
disabled; machine-readable OpenAPI is available at `/api/openapi.json`.

Deterministic findings and local review state use:

- `GET /api/snapshots/{snapshot_id}/findings/summary`
- `GET /api/snapshots/{snapshot_id}/findings`
- `GET /api/findings/{finding_id}`
- `GET /api/findings/{finding_id}/history`
- `PATCH /api/findings/{finding_id}/review`
- `GET /api/finding-rules`

Finding lists use bounded search, allowlisted family/severity/confidence/
evidence/review filters, allowlisted sort tokens, and pages of at most 100.
Responses include total matches and explicit support/truncation metadata.
The allowlisted `preset` query is `all` (the API and CLI-compatible default) or
`high-signal-v1`; the applied preset is returned in each page. Preset version
`1` includes all dependency/inheritance cycles and medium-or-higher severity
and confidence findings from the size, complexity, nesting, parameter,
coupling, and inheritance families. Summary `families` counts always describe
the complete current repository lifecycle and are independent of list filters.
Review updates require the current integer `version`; stale writes return `409`
with a generic conflict message and the current safe record. Notes are limited
to 2,000 characters and reason codes are allowlisted. Older schema snapshots
return `supported: false` rather than synthesizing findings.

Snapshot comparison and local handoffs use:

- `GET /api/repositories/{repository_id}/comparison-snapshots`
- `GET /api/comparisons/summary?baseline_snapshot_id=&target_snapshot_id=`
- `GET /api/comparisons/items?baseline_snapshot_id=&target_snapshot_id=&section=`
- `POST /api/handoffs/preview`
- `POST /api/handoffs`
- `GET /api/handoffs?repository_id=`
- `GET /api/handoffs/{handoff_id}`
- `GET /api/handoffs/{handoff_id}/markdown`
- `GET /api/handoffs/{handoff_id}/json`

Comparison sections are `files`, `symbols`, `relationships`, `cycles`,
`metrics`, and `findings`. Change, sort, direction, search, and pagination
tokens are allowlisted; searches are at most 200 characters and pages at most
100 records. Both snapshots must exist in the same repository:
cross-repository requests return `400`, missing snapshots return `404`, and
validation errors remain generic. Responses carry per-section compatibility/
reason codes and use repository-relative evidence only. Partial absence is
side-specific: `not-observed-in-baseline` and `not-observed-in-target` never
masquerade as confirmed additions or removals. Migrated snapshots expose
`observed_state_known: false` and null observation fields.

Handoff request arrays and the objective are bounded by typed models. Preview
does not create a comparison or saved record. Saved records remain local and
immutable. Markdown downloads use `text/markdown`; JSON downloads use
`application/json`; filenames are server-selected and cannot contain request
paths or header control characters. Every selected ID is validated against the
exact comparison and repository; unknown, stale, disabled-section, mismatched,
or cross-repository selections return `400`. Notes are absent unless their
finding IDs are selected and included in the explicit note-selection field.
Format-v2 digests cover the exact final Markdown and normalized JSON strings;
the default JSON limit is an exact 500,000-byte UTF-8 limit. Optional selected
evidence may be omitted deterministically, and a required metadata envelope
that cannot fit returns `400` with
`The Handoff JSON budget is too small for required metadata.` Preview and save
apply the same contract. Corrupted or over-budget saved output returns a
controlled integrity error instead of content, and downloads return the exact
digested Markdown or JSON bytes.
