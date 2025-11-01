# Clean architecture alignment for zscripts CLI and services

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

The current CLI module mixes presentation concerns (argument parsing and printing) with application logic (collecting logs, invoking adapters, redacting, and schema validation). This blurs boundaries, makes testing difficult, and conflicts with the README promise of a reusable toolkit. After this change, contributors should be able to import an application service that orchestrates adapters, redaction, sandboxing, and schema validation without going through the CLI. They will run the CLI to exercise the same service layer, ensuring consistent behavior and dependency direction.

## Progress

- [x] (2025-10-24 01:20Z) Drafted initial ExecPlan with orientation and plan of work.
- [x] (2025-10-24 01:22Z) Implemented domain interfaces and shared models under `zscripts/domain/`.
- [x] (2025-10-24 01:30Z) Added application service orchestrating use cases under `zscripts/application/` with unit-testable methods.
- [x] (2025-10-24 01:38Z) Introduced infrastructure adapters that satisfy the new interfaces while wrapping existing modules.
- [x] (2025-10-24 01:48Z) Refactored `cli.py` to use the application service and restrict itself to presentation concerns.
- [x] (2025-10-24 01:55Z) Added tests covering the new application service and ensured CLI behavior is preserved.
- [x] (2025-10-24 02:05Z) Ran `pytest` to confirm the stack remains stable and captured results.
- [x] (2025-10-24 02:07Z) Documented the new application service in `README.md`.

## Surprises & Discoveries

- Observation: Initial pytest run failed because the repository lacked the documented `examples/` tree, leaving adapters without fixtures.
  Evidence: pytest reported missing `examples/<adapter>/sample.log` files during the first run (chunk `351159†L5-L109`).

## Decision Log

- Decision: Generate structured sample logs under `examples/<adapter>/sample.log` for every registered adapter.
  Rationale: Align the project with README expectations and restore adapter/CLI tests after discovering the fixtures were missing.
  Date/Author: 2025-10-24 / gpt-5-codex.

## Outcomes & Retrospective

Refactor completed: the CLI now instantiates a reusable `ToolkitService`, infrastructure modules enforce dependency direction, and adapters/tests rely on explicit interfaces. New unit tests cover the service while end-to-end CLI tests continue to pass, confirming we preserved behavior and improved testability.

## Context and Orientation

The CLI entry point lives in `zscripts/cli.py`, and it currently imports adapters from `adapters/`, sandbox utilities from `scripts/`, and configuration helpers from `zscripts/__init__.py`. The adapters expose parsing and summarization logic, while `scripts/sandbox.py` defines `SandboxSettings` and `SandboxRunner` for guardrailed subprocess execution. Configuration defaults reside in `zscripts/config.py` and are surfaced through `get_default_config()` in `zscripts/__init__.py`. Tests in `tests/test_cli.py` execute the CLI as a subprocess to validate the parse and guardrails commands. There is no reusable application layer; the CLI directly coordinates dependencies, making unit testing and extension difficult.

## Plan of Work

1. Introduce `zscripts/domain/interfaces.py` to define Protocols (structural interfaces) for adapters, adapter registries, sandbox runners, redactors, configuration providers, example repositories, and schema validators. Move lightweight dataclasses such as `SandboxResult` into this layer so the application service can speak only in terms of domain abstractions.
2. Create `zscripts/application/services.py` with a `ToolkitService` class that encapsulates the use cases currently implemented in free functions (`_handle_*`). Each public method should operate on plain data (strings, paths, command sequences) and return values that the presentation layer can print or write. Internal helper functions like explanation builders should move here or into a dedicated domain utility module.
3. Under `zscripts/infrastructure/`, add thin adapters that implement the domain interfaces by delegating to existing modules: wrap `adapters.available_adapters` and `adapters.get_adapter`, instantiate `SandboxRunner`, call `redact_text`, load schemas via `zscripts.schemas`, and read example files from disk. These wrappers keep infrastructure dependencies out of the application layer while preserving existing functionality.
4. Refactor `zscripts/cli.py` so it becomes a presentation layer: it should build dependencies by composing the infrastructure implementations, instantiate `ToolkitService`, parse CLI arguments, and call service methods. All direct imports from `adapters` or `scripts` inside the CLI should move into infrastructure factories.
5. Add targeted unit tests in `tests/` for the new application service (e.g., verifying that summarization delegates to adapters and that guardrails info is formatted correctly). Update existing CLI tests if argument handling changes; ensure they still run end-to-end by invoking the CLI script.
6. Update documentation if necessary (README or docs) to mention the new service layer, especially if it affects how contributors integrate the toolkit.

## Concrete Steps

1. Create new package directories `zscripts/domain`, `zscripts/application`, and `zscripts/infrastructure` with `__init__.py` files.
2. Implement the domain interfaces and shared dataclasses. Ensure they have no dependencies on infrastructure modules.
3. Write the `ToolkitService` class with methods corresponding to the CLI subcommands: `collect_logs`, `parse_logs`, `summarize_logs`, `explain_logs`, `guardrails_snapshot`, `redact_text`, and `list_examples`. Keep methods pure (no printing or filesystem writes) aside from reading input that is explicitly passed in.
4. Build infrastructure adapters that satisfy the new interfaces, including factories for adapters, sandbox execution, redaction, schema validation, and example discovery.
5. Rewrite `zscripts/cli.py` to instantiate infrastructure components, adapt CLI arguments into service method calls, and handle input/output streams. Remove inline helper functions that duplicate service logic.
6. Add or update tests: unit tests for `ToolkitService` mocking dependencies, and existing CLI tests to ensure behavior remains consistent.
7. Run `pytest` from the repository root. Capture results for validation.
8. Record surprises, decisions, and progress updates throughout implementation, then summarize outcomes once complete.

## Validation and Acceptance

- Running `pytest` from the repository root should pass, confirming both unit tests and CLI integration continue to succeed.
- Invoking `python cli.py parse --adapter python --input examples/python/sample.log` should produce the same JSON payload as before, demonstrating functional parity.
- The new application service should be directly importable (e.g., `from zscripts.application.services import ToolkitService`) and usable in tests without spinning up the CLI.

## Idempotence and Recovery

The refactor is source-level and does not modify persistent state. If a step fails, re-run the failing command after fixing the issue. Because new packages are additive before refactoring the CLI, git history can be used to roll back to a clean state if necessary.

## Artifacts and Notes

- Pytest run after refactor: `pytest` (chunk `43234c†L1-L10`).

## Interfaces and Dependencies

- `zscripts/domain/interfaces.py` will define Protocols: `LogAdapterProtocol`, `AdapterRegistryProtocol`, `SandboxRunnerProtocol`, `RedactorProtocol`, `ConfigProviderProtocol`, `SchemaValidatorProtocol`, and `ExampleRepositoryProtocol`.
- `zscripts/application/services.ToolkitService` will depend exclusively on those protocols and on `ToolkitConfig`/`SandboxSettings` dataclasses defined in the domain layer.
- `zscripts/infrastructure/adapters` module will implement the adapter and registry protocols by wrapping `adapters.get_adapter` and `adapters.available_adapters`.
- `zscripts/infrastructure/sandbox` will adapt `scripts.sandbox.SandboxRunner` to the `SandboxRunnerProtocol` and translate subprocess results into the domain `SandboxResult`.
- `zscripts/infrastructure/redaction` will wrap `scripts.redaction.Redactor` or `redact_text` to satisfy `RedactorProtocol`.
- `zscripts/infrastructure/schema` will validate `NormalizedLog` instances against the JSON schema using `jsonschema` when available.
- `zscripts/infrastructure/examples` will read from the `examples/` directory to implement `ExampleRepositoryProtocol`.
- The CLI will assemble these dependencies, instantiate `ToolkitService`, and call its methods based on parsed arguments.
