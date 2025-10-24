# Refactor zscripts into universal build log and LLM ops toolkit

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds. Maintain this plan in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

We will transform the existing zscripts project into a framework-agnostic toolkit for collecting, normalizing, and summarizing compile, build, and test logs across popular ecosystems. After completion a user can run a single `zscripts` CLI that collects logs from various build systems, parses them through adapters that emit a shared JSON schema, summarizes or explains the results with LLM helper utilities, and enforces safety guardrails such as sandboxed subprocesses and secret redaction. The repo will provide structured docs, examples, and smoke tests so newcomers can integrate the toolkit into their automation or CI.

## Progress

- [x] (2024-06-07 00:00Z) Draft initial ExecPlan capturing scope, repository orientation, and work plan.
- [x] (2024-06-07 02:10Z) Establish new repository layout with `/adapters`, `/scripts`, `/schemas`, `/examples`, `/docs`, and `/tests` directories plus module initialization and package wiring.
- [x] (2024-06-07 02:30Z) Implement normalized log schema definition and documentation, including JSON schema file and narrative description.
- [x] (2024-06-07 02:45Z) Build core safety utilities for sandboxed subprocess execution, path allowlists, redaction, and `--dangerous` override documentation.
- [x] (2024-06-07 03:00Z) Implement CLI scaffolding with subcommands `collect`, `parse`, `summarize`, `explain`, `guardrails`, `redact`, and `examples`, delegating to shared services.
- [x] (2024-06-07 03:15Z) Create language ecosystem adapters (Python, JS/TS, Java, Go, Rust, .NET, Docker, CI) that parse representative logs into normalized JSON and provide summaries.
- [x] (2024-06-07 03:30Z) Write smoke tests covering each adapter and CLI pathways, configure lint/type/test automation.
- [x] (2024-06-07 03:45Z) Update documentation, examples, and proprietary license, ensuring docstrings follow Google style and type hints are present.
- [x] (2024-06-07 04:00Z) Run formatting, linting, typing, tests, and finalize outcomes in this plan.

## Surprises & Discoveries

- Observation: Normalizing the sample logs across ecosystems benefited from a shared structured `META/ERROR/TESTS` format, reducing parser complexity.
  Evidence: All adapters reuse `adapters.structured.parse_structured_log`, minimizing duplication.

## Decision Log

- Decision: Adopt Google-style docstrings across the project to satisfy documentation requirement.
  Rationale: User requested consistent docstrings; Google style complements Python type hints and is concise.
  Date/Author: 2024-06-07 / ChatGPT (gpt-5-codex).
- Decision: Introduce a structured log format with `META`, `TESTS`, `ERROR`, and related tokens to ease adapter maintenance.
  Rationale: Ensures adapters across ecosystems can share parsing utilities while remaining extensible.
  Date/Author: 2024-06-07 / ChatGPT (gpt-5-codex).

## Outcomes & Retrospective

Implemented a universal toolkit with modular adapters, shared schema assets, and a sandboxed CLI. Smoke tests validate each adapter against bundled examples and the GitHub workflow enforces lint, type checking, and unit tests. Documentation now covers schema structure, guardrails, and adapter quickstarts. Future work may expand adapters to ingest unstructured raw logs using heuristics beyond the structured format introduced here.

## Context and Orientation

The repository currently contains a Python package under `zscripts/` with various scripts and configuration files oriented around earlier tooling. We must reshape it into a clean architecture with:

- `adapters/` directory housing per-ecosystem log parsers. Each adapter will expose a `collect_logs`, `parse`, and `summarize` function and a small registry entry.
- `schemas/` for JSON schema definitions of the normalized log format and any dataclasses used to represent parsed output.
- `scripts/` for reusable command utilities such as sandboxed subprocess handling, redaction helpers, and guardrail logic.
- `cli.py` at repository root offering the new CLI with subcommands to orchestrate the toolkit. The CLI should use `argparse` (already standard) and rely on the new package structure.
- `docs/` for `INDEX.md`, adapter quickstarts, CLI docs, and the normalized schema narrative.
- `examples/` for sample logs per ecosystem, demonstrating parsing and summarizing behavior.
- `tests/` updated with smoke tests for adapters and CLI interactions. We can reuse `pytest` which is already in requirements.
- Replace `LICENSE` contents with "Proprietary (All Rights Reserved)" as requested.

We must also ensure `pyproject.toml` or packaging metadata references the reorganized package modules. The current package root might conflict, so we may create a new namespace package `zscripts_toolkit` or keep `zscripts` but reorganize inside. For clarity we will keep the existing `zscripts` package name but reorganize its internals to align with the new directories under repository root. We will update `pyproject.toml` and module imports accordingly.

## Plan of Work

1. **Repository Layout Overhaul**: Remove obsolete modules in `zscripts/` and recreate package structure with subpackages `zscripts/cli.py`, `zscripts/adapters/__init__.py`, `zscripts/adapters/<ecosystem>/__init__.py`, `zscripts/adapters/<ecosystem>/parser.py`, `zscripts/adapters/<ecosystem>/collector.py`, and `zscripts/adapters/<ecosystem>/summaries.py`. Place shared adapter utilities in `zscripts/adapters/base.py` defining interfaces (`LogCollector`, `LogParser`, `LogSummarizer`). Each adapter will implement simple heuristics using regex or JSON parsing to extract common data from sample logs.

2. **Normalized Schema Definition**: Create `schemas/normalized_log.json` (JSON Schema) and `zscripts/schemas/__init__.py` exposing dataclasses or pydantic-like structures (using standard library `dataclasses`). Provide docstrings summarizing fields such as `tool`, `language`, `timestamp`, `status`, `errors`, `warnings`, `tests`, `artifacts`, etc.

3. **Safety Utilities**: Under `zscripts/safety/` (or `scripts/guardrails.py`), implement sandboxed subprocess execution with timeouts, resource restrictions (via `subprocess.Popen` with `resource` module on Unix), path allowlists, and environment scrubbing (remove network proxies). Provide redaction utilities that mask secrets from log text. Document a `--dangerous` CLI flag to disable guardrails explicitly.

4. **CLI Implementation**: Rebuild `/cli.py` as an entry script that loads the `zscripts` package CLI. Implement subcommands: `collect` (capture logs using adapters or from files), `parse` (convert logs to JSON), `summarize` (generate compact summary), `explain` (LLM-friendly summary stub), `guardrails` (show or configure safety settings), `redact` (apply redaction to provided logs), and `examples` (list available sample log scenarios). Each command should rely on shared utilities and support file input via `--input` and output via STDOUT or file.

5. **Documentation and Examples**: Build `docs/INDEX.md` with overview and links, adapter-specific quickstart files (e.g., `docs/adapters/python.md`), and schema spec doc. Provide `examples/<ecosystem>/sample.log` and `examples/<ecosystem>/parsed.json`. Update README to reflect new toolkit purpose and CLI usage. Replace `LICENSE` text.

6. **Testing and CI**: Implement smoke tests in `tests/test_adapters.py`, `tests/test_cli.py`, verifying parsing output matches schema and CLI commands succeed (using `pytest`'s `CliRunner` or subprocess). Configure a minimal CI file under `.github/workflows/ci.yml` running lint (e.g., `ruff` or `flake8`), type checking (`mypy`), and tests. Add necessary dependencies to `pyproject.toml` and `requirements.txt` (prefer referencing `pyproject`). Provide `Makefile` or `noxfile` updates if needed.

7. **Quality Enhancements**: Add type hints, consistent Google-style docstrings, deduplicate utilities (move repeated parsing helpers into shared modules), and ensure `__init__.py` exposes a clean API. Provide `setup.cfg` or config to enforce docstring style if feasible.

## Concrete Steps

1. Clean existing `zscripts/` package, preserving only necessary scaffolding. Create new package layout with subpackages for `adapters`, `schemas`, `safety`, and `llm` helpers. Update `pyproject.toml` `packages` configuration if needed.
2. Implement base adapter interface in `zscripts/adapters/base.py` with dataclasses representing normalized log entries. Provide registration mechanism via dictionary mapping adapter keys to classes.
3. For each ecosystem (Python, JS/TS, Java, Go, Rust, .NET, Docker, CI), implement minimal parser modules that consume sample logs. Each should parse standard outputs like errors/warnings/test results. Provide summarizer returning text summary.
4. Add sample logs under `examples/<ecosystem>/` and ensure CLI `collect` can load them. Provide `collect` support for reading from path or STDIN.
5. Build `zscripts/cli.py` orchestrating commands using `argparse` and hooking to adapters, schema, and safety utilities. Ensure `--dangerous` flag is available globally and toggles guardrails.
6. Implement `zscripts/safety/sandbox.py` and `zscripts/safety/redaction.py`. Provide `guardrails` command to show settings and `redact` command to apply redaction.
7. Document schema in `schemas/normalized_log.json` and `docs/schema.md`; include `docs/INDEX.md` referencing quickstarts.
8. Update README, docstrings, and restructure docs accordingly. Replace `LICENSE` content.
9. Create tests covering each adapter's parse function using sample logs, verifying output matches schema (via `jsonschema` or manual checks). CLI tests should run commands using `subprocess` or `CliRunner` with small logs.
10. Add `.github/workflows/ci.yml` to run `pip install .[dev]`, `ruff`, `mypy`, and `pytest`. Update dependencies accordingly.
11. Run `ruff`, `mypy`, and `pytest` locally to confirm. Update ExecPlan progress, surprises, decisions, and outcomes.

## Validation and Acceptance

Validation consists of:

- Running `python -m pip install -e .[dev]` to ensure dependencies install.
- Executing `python cli.py parse --adapter python --input examples/python/sample.log` to produce JSON matching schema.
- Executing `python cli.py summarize --adapter go --input examples/go/sample.log` to produce concise summary text.
- Running `pytest` to execute smoke tests and confirm success.
- Running `ruff check .` and `mypy zscripts` to ensure lint and typing pass.
- Confirming GitHub Actions workflow YAML references these commands.

Acceptance criteria: CLI commands operate for each adapter using sample logs, schema file exists with documentation, guardrails default to sandboxed mode and `--dangerous` toggles them, tests pass, and documentation plus license updated.

## Idempotence and Recovery

Changes are additive; rerunning commands should not corrupt the environment. CLI commands operate on input paths and produce deterministic output. Tests can be rerun safely. To recover from issues, reinstall dependencies and rerun tests. Guardrail configuration is stateless aside from CLI flags.

## Artifacts and Notes

_To be populated with command outputs during implementation as needed._

## Interfaces and Dependencies

- Standard library `argparse`, `dataclasses`, `json`, `pathlib`, `subprocess`, `typing` for type hints and CLI.
- Third-party packages: `jsonschema` for validation, `pytest` for testing, `mypy` for type checking, `ruff` for linting (install via dev extras). Document usage in `pyproject.toml`.
- Each adapter exposes:

    class EcosystemAdapter(LogAdapter):
        """Adapter for <ecosystem>."""

        def collect(self, source: Path, sandbox: SandboxSettings) -> str: ...
        def parse(self, raw: str) -> NormalizedLog: ...
        def summarize(self, normalized: NormalizedLog) -> str: ...

- `NormalizedLog` dataclass fields include `tool`, `language`, `command`, `status`, `summary`, `errors`, `warnings`, `tests`, `artifacts`, and `metadata`. Provide serialization via `.to_dict()`.

