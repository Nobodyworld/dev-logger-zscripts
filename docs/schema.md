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

## ETL Mapping Example

The toolkit ETL flow is intentionally linear:

1. Extract raw log text from `--input`, `--command`, or STDIN.
2. Transform text into a `NormalizedLog` through the selected adapter.
3. Load the transformed payload by validating against `schemas/normalized_log.json`.

Example fragment from a Python run:

```text
META tool=pytest ecosystem=python command="pytest -q" status=failed summary="1 failed"
ERROR message="AssertionError" file="tests/test_api.py" line=42
TESTS passed=19 failed=1 skipped=0 duration=7.53
```

Maps to this normalized structure:

```json
{
  "tool": "pytest",
  "ecosystem": "python",
  "command": "pytest -q",
  "status": "failed",
  "summary": "1 failed",
  "errors": [
    {
      "message": "AssertionError",
      "file": "tests/test_api.py",
      "line": 42
    }
  ],
  "tests": {
    "passed": 19,
    "failed": 1,
    "skipped": 0,
    "duration": 7.53
  }
}
```
