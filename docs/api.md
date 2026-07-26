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

- `GET /api/snapshots/{snapshot_id}/relationships/summary`
- `GET /api/snapshots/{snapshot_id}/relationships`
- `GET /api/snapshots/{snapshot_id}/relationships/nodes`
- `GET /api/snapshots/{snapshot_id}/relationships/neighborhood`
- `GET /api/snapshots/{snapshot_id}/cycles`

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
