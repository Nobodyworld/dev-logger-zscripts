# Stage 1 Full-Scale Enhancements ExecPlan

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

Refer to `.agent/PLANS.md` for the required structure and maintenance rules. This document complies with those requirements and must remain self-contained.

## Purpose / Big Picture

The current toolkit already parses and summarizes build logs, but teams need richer "one-shot" reports they can feed directly into downstream automation or compliance workflows. Stage 1 will deliver a production-ready reporting pipeline that ingests raw logs, emits structured JSON/Markdown reports, tightens configuration and telemetry defaults, and refreshes dependency pins. After this change a user can run `python cli.py report --input <log>` (optionally choosing `--format json|markdown`) to receive a validated report combining normalization, summarization, explanations, and guardrail metadata. The command should stream metrics and structured logs just like existing commands. Documentation, tests, and developer workflows must reflect the new capability.

## Progress

- [x] (2025-02-14 13:20Z) Drafted initial ExecPlan with scope, acceptance criteria, and repo orientation.
- [x] (2025-02-14 15:00Z) Implemented reporting service layer, CLI command, and supporting utilities.
- [x] (2025-02-14 15:05Z) Added service, CLI, and formatter tests covering JSON/Markdown output and redaction toggles.
- [x] (2025-02-14 15:20Z) Updated configuration schema, defaults, and documentation for reporting settings.
- [x] (2025-02-14 15:35Z) Bumped runtime/dev dependencies in `pyproject.toml` to latest compatible baselines.
- [x] (2025-02-14 15:30Z) Updated README and documentation index with reporting workflow and new configuration keys.
- [x] (2025-02-14 15:45Z) Ran pytest and ruff; recorded existing mypy limitations for legacy modules.
- [x] (2025-02-14 15:50Z) Captured pytest (`f17043`) and ruff (`233179`) results; documented mypy limitations (`30e1cd`).
- [x] (2025-02-14 15:55Z) Documented outcomes and follow-ups in the retrospective section.

## Surprises & Discoveries

- Observation: `argparse.BooleanOptionalAction` provides the `--no-redact` toggle automatically, simplifying config overrides.
  Evidence: Covered by `tests/test_cli.py::test_cli_report_respects_redact_toggle`.
- Observation: Repository-wide `mypy` runs still fail because legacy modules lack type annotations and rely on dynamic APIs.
  Evidence: `mypy zscripts/...` output (chunk `30e1cd`) showing pre-existing errors outside the touched modules.

## Decision Log

- Decision: Stage 1 will focus on introducing a `report` command that orchestrates parse/summarize/explain outputs and optional Markdown/JSON export.
  Rationale: Provides high-value user-visible feature fulfilling "full-scale" directive without destabilizing existing adapters.
  Date/Author: 2025-02-14 / Assistant
- Decision: Apply redaction to report summaries, explanations, and raw text when requested to avoid leaking sensitive data in artifacts.
  Rationale: The report command emits outputs that may be stored or shared; reusing the existing redactor ensures consistent sanitization.
  Date/Author: 2025-02-14 / Assistant

## Outcomes & Retrospective

The new `report` workflow ships with service orchestration, JSON/Markdown
formatters, CLI integration, documentation, and regression tests. Configuration
defaults (`report_format`, `report_redact`) allow teams to tune outputs without
per-invocation flags. Runtime validation covers pytest and ruff; repository-wide
mypy remains blocked by legacy dynamic modules outside the touched code path.
Future work could introduce typed facades for observability helpers to unlock
stricter mypy enforcement.

## Context and Orientation

The repository is a Python package providing a CLI (`cli.py` entrypoint forwarding to `zscripts/cli.py`) that builds an `AdapterRegistry` from modules under `adapters/`. The CLI delegates all operations to `ToolkitService` (`zscripts/application/services.py`) which wraps domain interfaces for parsing logs, executing sandboxed commands, and redacting secrets. Normalized log data structures live in `zscripts/schemas/normalized.py`; telemetry helpers are in `zscripts/observability/`. Configuration defaults and parsing live in `zscripts/config.py` and `zscripts/configuration.py`. Tests under `tests/` cover CLI behavior, service logic, observability, and configuration.

A reporting workflow must therefore:
1. Accept raw log input (from `--input`, `--command`, or STDIN) and choose an adapter (default from configuration, override via CLI).
2. Produce a normalized log (`ToolkitService.parse_logs`), textual summary, richer explanation, redacted output (if requested), and guardrail metadata.
3. Emit the combined payload in JSON (structured) or Markdown (human-readable) form.
4. Keep metrics/logging consistent with existing CLI subcommands.

We will add supporting abstractions where needed while maintaining compatibility with adapter protocols.

## Plan of Work

1. **Service layer enhancements**: Introduce a new `ReportBundle` dataclass under `zscripts/application/reporting.py` containing normalized log data, summary, explanation, guardrail snapshot, and timestamps. Extend `ToolkitService` with `generate_report(...)` that orchestrates parsing, summarization, explanation, and guardrail capture. Ensure telemetry spans wrap each stage for observability.
2. **Formatting utilities**: Create `zscripts/application/report_formatters.py` with pluggable formatters (JSON, Markdown). JSON formatter should call `ReportBundle.to_dict()` ensuring ISO timestamps; Markdown formatter should produce sections (Summary, Explanation, Guardrails, Issues, Tests) with bullet lists. Provide tests for deterministic output.
3. **Configuration updates**: Update `ToolkitConfig` (likely defined in `zscripts/config.py`) to include defaults for `report_format` ("json") and `report_redact` boolean. Extend configuration parser to accept these keys and document them. Ensure CLI `--report-format` and `--report-redact` flags override config.
4. **CLI command**: In `zscripts/cli.py`, register a `report` subparser with `--format`, `--output`, and `--redact` toggles. Handler should call `ToolkitService.generate_report` (passing `redact` flag to optionally run redaction on the textual explanation/summary). Output dispatch uses formatter module and respects `--output`. Bind telemetry span `cli.report` and record metrics automatically via existing helper.
5. **Dependency refresh**: Review `pyproject.toml` and bump `jsonschema`, `pytest`, `ruff`, `mypy`, and `coverage` to latest known stable major/minor versions compatible with Python ≥3.10. Ensure `requirements.txt` stays in sync (still `-e .[dev]`). Update documentation referencing tool versions if necessary.
6. **Documentation**: Update `README.md`, `docs/INDEX.md` (or relevant doc), and add a focused guide `docs/reporting.md` describing usage, CLI options, and sample output. Mention telemetry integration and configuration keys.
7. **Testing**: Add tests in `tests/test_services.py` for `ToolkitService.generate_report` using fakes to ensure summary/explanation pipelines run and Markdown formatting. Extend `tests/test_cli.py` to cover `report` command (JSON + Markdown + STDIN). Ensure new config keys validated in `tests/test_configuration.py`.
8. **Validation**: Run `pytest`, `ruff check .`, and `mypy` on core modules touched. Capture outputs for final report.
9. **Finalize**: Update this ExecPlan sections (Progress, Surprises, Decision Log if new decisions arise, Outcomes) before concluding work.

## Concrete Steps

1. Create `zscripts/application/reporting.py` with `ReportBundle` dataclass and helper `ReportBundle.to_dict()` converting nested dataclasses and timestamps.
2. Extend `ToolkitService` to add `generate_report()` method. Reuse existing private helpers for parsing and guardrail retrieval; add optional redaction of raw text and explanation/summary when requested.
3. Implement formatter module `zscripts/application/report_formatters.py` with registry mapping format name to callable. Provide JSON + Markdown. Include simple factory `get_report_formatter` raising `ValueError` for unsupported formats.
4. Update CLI to register `report` command and integrate with formatters. Ensure CLI-supplied `--format` overrides config default and invalid formats raise user-friendly errors via `_fail`.
5. Adjust `ToolkitConfig` dataclass/defaults to include `report_format` and `report_redact`. Update configuration parser to coerce new keys, and default `report_redact` to `False`. Document them in config docs.
6. Update docs (README, new `docs/reporting.md`, update index) with usage instructions and sample outputs captured from tests or deterministic seeds.
7. Update `pyproject.toml` dependencies to latest stable versions (documented in Decision Log). Ensure `requirements.txt` remains `-e .[dev]` (already future-proof).
8. Add new tests for service and CLI plus configuration coverage. Provide fixtures for Markdown output to keep deterministic.
9. Run lint/type/test commands. Update ExecPlan sections accordingly and capture output logs for the final report.

## Validation and Acceptance

- Running `python cli.py report --input examples/python/sample.log --format json` should print a JSON document containing normalized log fields, summary text, explanation text, guardrails, and metadata, passing schema validation.
- Running `python cli.py report --input examples/python/sample.log --format markdown` should produce human-readable Markdown sections summarizing the log and guardrails.
- `ToolkitService.generate_report` unit tests should pass, confirming the method redacts when requested and formats guardrails correctly.
- All automated checks (`pytest`, `ruff check .`, `mypy zscripts`) must succeed.

## Idempotence and Recovery

Code changes are additive; rerunning commands is safe. Configuration parser raises explicit errors for invalid keys, so misconfiguration can be corrected by editing config files. The CLI `report` command reads inputs without mutation and writes outputs deterministically; re-running simply overwrites target files if specified.

## Artifacts and Notes

To be populated with key command outputs, Markdown/JSON snippets, and test transcripts during implementation.

## Interfaces and Dependencies

- `zscripts/application/reporting.py` will define:
    - `@dataclass class ReportBundle` with fields `normalized: NormalizedLog`, `summary: str`, `explanation: str`, `guardrails: dict[str, object]`, `collected_text: str`, `redacted_text: str | None`, `generated_at: datetime`.
    - Method `to_dict(self) -> dict[str, Any]` returning JSON-friendly payload (normalized via `.to_dict()`).
- `zscripts/application/report_formatters.py` will expose:
    - `class ReportFormatter(Protocol)` with `__call__(bundle: ReportBundle) -> str`.
    - `def get_report_formatter(name: str) -> ReportFormatter` supporting `"json"` and `"markdown"`.
- `ToolkitService.generate_report` signature: `def generate_report(self, *, adapter_key: str | None, raw_text: str, redact: bool, format: str) -> ReportBundle` (formatter selection may occur at CLI level; service returns bundle only).
- CLI `report` handler will call `ToolkitService.generate_report` then pass bundle to formatter.
- Configuration: `ToolkitConfig` adds `report_format: str` and `report_redact: bool` with validation in `zscripts/configuration.py`.

