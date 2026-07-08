# Log ETL Case Study

This case study shows how zscripts handles a failed test run from collection to
reporting while preserving a stable normalized schema.

## Scenario

A CI job runs `pytest -q` and emits one failing test plus a warning. The goal is
to generate a deterministic normalized payload and a report that can be consumed
by dashboards and release checks.

## Pipeline Walkthrough

1. Extract

- Command: `zscripts collect --command pytest -q`
- Output: raw stdout/stderr combined into one payload.

1. Transform

- Command: `zscripts --adapter python parse --input examples/python/sample.log`
- Adapter: `adapters/python` parses structured lines into `NormalizedLog`.

1. Load

- The parsed payload is validated against `schemas/normalized_log.json`.
- Downstream commands (`summarize`, `explain`, `report`) consume validated data.

## Why The Shape Matters

A stable schema lets multiple ecosystems (python, javascript, java, go, rust,
dotnet, docker, ci) emit data that can be queried consistently.

- Error density: `len(errors) / (tests.failed + tests.passed)`
- Failure trend: compare `status` and `tests.failed` across runs
- Artifact tracing: use `artifacts[]` to link coverage or build outputs

## Command Sequence

```sh
zscripts --adapter python parse --input examples/python/sample.log
zscripts --adapter python summarize --input examples/python/sample.log
zscripts --adapter python report --input examples/python/sample.log --format markdown
```

## Expected Outcome

- Parse output validates against schema.
- Summary and explanation remain human-readable.
- Report severity tracks failures (`error`), warnings (`warning`), or clean runs (`ok`).
