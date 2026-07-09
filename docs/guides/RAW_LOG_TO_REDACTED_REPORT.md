# Raw Log to Normalized and Redacted Report

This guide shows a full pipeline from raw CI-style log text to:

- normalized JSON output
- redacted markdown report

## Example Files

- Raw input: `examples/raw_to_report/raw.log`
- Example normalized output: `examples/raw_to_report/normalized.json`
- Example redacted report: `examples/raw_to_report/redacted_report.md`

`examples/raw_to_report/normalized.json` is an intentionally maintained,
deterministic example fixture used by documentation and contract tests.

## CLI Walkthrough

```sh
# 1) Normalize a raw log
python cli.py --adapter ci parse --input examples/raw_to_report/raw.log > normalized.json

# 2) Produce a redacted markdown report
python cli.py --adapter ci report --input examples/raw_to_report/raw.log --format markdown --redact --output redacted_report.md

# 3) Optionally emit only redacted raw content
python cli.py redact --input examples/raw_to_report/raw.log > redacted_raw.log
```

## What to Expect

- `parse` emits a `NormalizedLog` document matching `schemas/normalized_log.json`.
- `report` includes summary, findings, and diagnostics suitable for release notes.
- `--redact` masks configured sensitive values (keys, tokens, and credentials).
