# Normalized Log Schema

The normalized log schema captures essential metadata from build, compile,
and test executions. It is defined formally in `schemas/normalized_log.json`
and mirrored by the `NormalizedLog` dataclass in `zscripts.schemas.normalized`.

## Top-Level Fields

| Field | Type | Description |
| --- | --- | --- |
| `tool` | string | Name of the build or test tool that produced the log. |
| `ecosystem` | string | Programming ecosystem associated with the log. |
| `command` | string | Command that triggered the log. |
| `status` | string | Final status such as `passed`, `failed`, or `unknown`. |
| `summary` | string | Human-readable summary sentence. |
| `timestamp` | RFC3339 string | Time when the log was generated. |
| `errors` | array of `LogIssue` | Compiler or runtime errors. |
| `warnings` | array of `LogIssue` | Non-fatal warnings. |
| `tests` | `TestSummary` or `null` | Aggregated test results. |
| `artifacts` | array of strings | Produced artifact paths. |
| `metadata` | object | Additional key-value metadata captured by adapters. |

## Issue Records

Each error or warning is represented by a `LogIssue` object:

- `message`: Detailed message.
- `file`: Optional source file path.
- `line`: Optional line number.
- `column`: Optional column number.
- `code`: Optional machine-readable identifier (error code, rule id, etc.).

## Test Summaries

The optional `tests` field aggregates test execution details:

- `passed`, `failed`, `skipped`: Integer counts.
- `duration`: Optional duration in seconds.
- `cases`: Optional list of individual `TestCaseResult` entries with per-case
  status, duration, and message.

Adapters may include additional metadata relevant to their ecosystem, such as
toolchain versions or CI run identifiers. Consumers should tolerate unknown
metadata keys.
