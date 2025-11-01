```md
# Stage 1 Report Severity & Failure Policy Enhancements

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with `.agent/PLANS.md` and remains fully self-contained for future contributors.

## Purpose / Big Picture

Teams integrating zscripts into CI pipelines need a reliable way to gate builds on the quality of generated reports. Today the `report` command always exits successfully even when the normalized log records failures or warnings, forcing downstream scripts to re-parse JSON output. This plan introduces first-class severity evaluation, configuration-driven failure policies, and CLI ergonomics so that operators can declare whether warnings or errors should cause a non-zero exit code. The generated report will surface severity metadata in both JSON and Markdown outputs, giving humans and automation the same signal.

## Progress

- [x] (2025-10-26 05:05Z) Drafted ExecPlan describing severity evaluation, configuration, CLI overrides, and documentation/test updates.
- [x] (2025-10-26 05:18Z) Implemented severity computation in `ReportBundle`, helper utility, and `ToolkitService.generate_report`.
- [x] (2025-10-26 05:27Z) Extended configuration schema and parser with `report_fail_on` handling.
- [x] (2025-10-26 05:36Z) Updated CLI with `--fail-on` flag, configuration propagation, and exit-code enforcement.
- [x] (2025-10-26 05:41Z) Updated report formatters to surface severity metadata in JSON and Markdown outputs.
- [x] (2025-10-26 05:56Z) Expanded service, CLI, configuration, and formatter tests covering severity evaluation and failure policies.
- [x] (2025-10-26 05:50Z) Refreshed README and reporting/configuration docs with severity and `--fail-on` guidance.
- [x] (2025-10-26 05:58Z) Ran pytest and ruff to confirm regressions are avoided; captured output references (`e2469e`, `3f69ac`).
- [x] (2025-10-26 06:00Z) Finalized plan with discoveries, decision log updates, and retrospective summary.

## Surprises & Discoveries

- Observation: Existing sample logs already normalize to an `error` severity, which provided immediate coverage for fail-on
  policies without crafting new fixtures.
  Evidence: `tests/test_cli.py::test_cli_report_fail_on_errors_exits_nonzero`.

## Decision Log

- Decision: Default the `report_fail_on` configuration to `never` so existing automation keeps succeeding until teams opt in.
  Rationale: Preserves backward compatibility while enabling stricter gating for users that want it.
  Date/Author: 2025-10-26 / Assistant
- Decision: Treat adapter statuses of `failed`, `error`, `failure`, and `fatal` as error severity regardless of warning counts.
  Rationale: Ensures explicit failure statuses always trigger CI failures even if adapters omit error lists.
  Date/Author: 2025-10-26 / Assistant

## Outcomes & Retrospective

Implemented severity awareness across the reporting stack, introduced a configurable
`report_fail_on` policy, and exposed CLI overrides that enforce CI-friendly exit codes.
JSON/Markdown outputs now surface severity metadata for humans and automation alike.
Regression tests and documentation updates codify the new behavior and validated that
existing workflows remain unaffected unless teams opt in to stricter policies.

## Context and Orientation

The CLI entrypoint resides in `zscripts/cli.py`, delegating operations to `zscripts.application.services.ToolkitService`. The service already assembles a `ReportBundle` (defined in `zscripts/application/reporting.py`) and returns it to the CLI, which chooses a formatter from `zscripts/application/report_formatters.py`. Runtime configuration is represented by `zscripts.config.ToolkitConfig`; parsing and validation logic lives in `zscripts/configuration.py`. Tests cover CLI behavior in `tests/test_cli.py`, service logic in `tests/test_services.py`, and reporting output in `tests/test_reporting.py`. Documentation for end users is maintained in `README.md`, `docs/reporting.md`, and `docs/configuration.md`.

We will extend these components to compute a severity flag from normalized logs, persist the setting in configuration, and update CLI behavior accordingly. The severity metadata must be included in formatted output so that both automation and humans see a consistent value. Tests will ensure the evaluation is deterministic and configuration errors surface clearly.

## Plan of Work

1. **Severity evaluation**: Implement a helper (either a new private method on `ToolkitService` or a utility in `zscripts/application/reporting.py`) that inspects `NormalizedLog` instances. Severity should be `"error"` when the normalized status equals `failed`/`error` (case-insensitive), when errors are present, or when test summaries report failures. Severity should be `"warning"` when warnings exist but no error conditions trigger. Otherwise report `"ok"`. Persist the result on `ReportBundle` as a new field, expose it via `to_dict()`, and update Markdown formatting to show it near the header.
2. **Configuration updates**: Add a `report_fail_on` field to `ToolkitConfig` and `DEFAULT_CONFIG` defaulting to `"never"`. Update `_KNOWN_KEYS` and `_apply_config_values` in `zscripts/configuration.py` to coerce this field, only allowing the values `never`, `warnings`, and `errors`. Document helpful error messages for invalid inputs. Tests in `tests/test_configuration.py` should verify parsing and override precedence.
3. **CLI integration**: Extend `_build_parser` to add a `--fail-on` option for the `report` subcommand with the same choices. Update `_prepare_and_execute` so the resolved value is stored on the args namespace (mirroring the existing format/redact handling) and persists to `ToolkitConfig`. Within `_handle_report`, evaluate whether the generated `ReportBundle.severity` meets the failure policy and raise `SystemExit(1)` when severity is equal to or exceeds the threshold. Ensure `_execute_command` metrics still record the final status correctly.
4. **Formatter updates**: Update `format_report_json` to include the severity field via `ReportBundle.to_dict()` and update the Markdown formatter to render the severity prominently (e.g., `- **Severity:** error`). Add unit tests asserting the presence of severity metadata in both formats.
5. **Testing**: Create or extend service-level tests to cover severity computation (e.g., injecting normalized logs with warnings/errors). Augment CLI tests to assert exit codes for different `--fail-on` settings and configuration defaults. Update reporting tests to check Markdown/JSON outputs. Ensure tests capture redaction interactions remain unaffected.
6. **Documentation**: Revise README usage examples to mention `--fail-on`, and update `docs/reporting.md` and `docs/configuration.md` with explanation of severity semantics, configuration keys, and exit code behavior. Note the default is `never` to avoid breaking existing users.
7. **Validation**: Run `pytest` and `ruff check .` from the repository root. Record outputs for future readers and mention in the ExecPlan.

## Concrete Steps

1. Modify `zscripts/application/reporting.py` to add severity evaluation helper and new field on `ReportBundle`; update `ToolkitService.generate_report` to compute it.
2. Update `zscripts/application/report_formatters.py` to display severity in Markdown and ensure JSON includes the field.
3. Adjust `zscripts/config.py` and `DEFAULT_CONFIG` to include `report_fail_on`, then update `zscripts/configuration.py` coercion logic and associated tests.
4. Enhance CLI parsing in `zscripts/cli.py` to wire `--fail-on` and enforce exit codes in `_handle_report`.
5. Write or expand tests under `tests/test_services.py`, `tests/test_reporting.py`, `tests/test_configuration.py`, and `tests/test_cli.py` for severity behavior and failure policy.
6. Update documentation files with new instructions and examples.
7. Execute test and lint commands, updating this plan with results and any surprises.

## Validation and Acceptance

- Running `python cli.py report --input examples/python/sample.log --fail-on errors` should exit with code `1` when the normalized log contains failures; `--fail-on never` should exit `0` for the same input.
- Generated JSON reports include a top-level `severity` field matching the computed status, and Markdown reports list the severity in the header.
- Configuration tests confirm `report_fail_on` accepts only valid values and that CLI overrides take precedence.
- `pytest` and `ruff check .` both succeed without regressions.

## Idempotence and Recovery

Changes are additive and configuration-driven. Re-running the CLI with different `--fail-on` values simply changes the exit code; configuration parsing continues to validate inputs and emit explicit errors. Documentation updates are static. Test commands can be repeated safely.

## Artifacts and Notes

(To be populated with command transcripts and snippets after execution.)

## Interfaces and Dependencies

- `ReportBundle` gains a `severity: str` field populated during construction. Method `to_dict()` returns this field.
- `ToolkitService.generate_report(...)` computes severity using a new helper (either `_evaluate_severity` private method or utility) and populates the bundle accordingly.
- Configuration additions in `ToolkitConfig` and parser enforce allowed values for `report_fail_on`.
- CLI `--fail-on` flag writes to `args.resolved_report_fail_on` and `ToolkitConfig.report_fail_on` before invoking `_handle_report`.
- `_handle_report` will raise `SystemExit(1)` when severity meets/exceeds the requested threshold.
```
