# Redacted Diagnostic Report

## Summary

CI run failed because one test failed in `tests/test_services.py`.

## Findings

- Failure: `tests/test_services.py::test_generate_report_applies_redaction`
- Error type: `AssertionError`
- Sensitive values were masked in this report.

## Redaction Proof

Original token-like value (`API_KEY=...`) is redacted below:

- `API_KEY=[REDACTED]`

## Suggested Follow-up

- Verify redaction patterns in configuration.
- Re-run the failing test in isolation.
- Confirm report generation with `--redact` enabled in CI.
