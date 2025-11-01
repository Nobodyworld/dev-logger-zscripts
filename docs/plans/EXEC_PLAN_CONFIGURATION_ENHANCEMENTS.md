# Strengthen configuration loading and CLI overrides

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan must be maintained in accordance with `.agent/PLANS.md`.

## Purpose / Big Picture

After implementing this plan, zscripts users will be able to point the CLI at a configuration file, override select settings on the command line, and understand the effective runtime configuration. The change introduces structured parsing, validation, and helpful error messages so teams can safely customize sandbox guardrails, adapter defaults, and redaction patterns without modifying source code. Successful completion lets a user run `python cli.py --config custom.toml collect --command pytest` and know that the sandbox honors the customized paths, timeouts, and redactors described in the file.

## Progress

- [x] (2025-10-25 00:44Z) Draft plan and collect repository context.
- [x] (2025-10-25 00:48Z) Implement configuration loading helpers under `zscripts/configuration.py`.
- [x] (2025-10-25 00:48Z) Update CLI argument parsing to accept `--config` and `--set` overrides.
- [x] (2025-10-25 00:48Z) Extend infrastructure wiring to honor configurable example directories and sandbox options.
- [x] (2025-10-25 00:48Z) Add comprehensive tests covering configuration parsing, CLI wiring, and error handling.
- [x] (2025-10-25 00:48Z) Refresh documentation to explain configuration files and overrides.
- [x] (2025-10-25 00:51Z) Run quality gates (`ruff`, `mypy`, `pytest`) and finalize retrospective (mypy still reports existing Any-heavy modules outside the new configuration stack).

## Surprises & Discoveries

- Observation: `argparse`'s `store_true` action overwrote configuration values
  even when the flag was omitted.
  Evidence: Guardrails CLI tests showed the dangerous flag reverting to
  `False` despite a `dangerous_mode = true` entry in a temporary TOML file.
- Observation: Running `mypy` across the repository still produces extensive
  `Any`-driven diagnostics in pre-existing adapters and scripts.
  Evidence: `mypy zscripts` enumerated errors in modules unrelated to the new
  configuration loader; the CLI and configuration modules rely on those
  adapters, so addressing them is out of scope for this iteration.

## Decision Log

- Decision: Restrict configuration files to TOML and JSON parsed with stdlib
  modules.
  Rationale: Keeps the dependency surface minimal while supporting the formats
  already shipped in the repository.
  Date/Author: 2025-10-25 / assistant
- Decision: Treat `--dangerous` as an opt-in override only when explicitly
  provided.
  Rationale: Preserves values loaded from configuration files and prevents
  accidental downgrades to a safer mode when users expect their config to win.
  Date/Author: 2025-10-25 / assistant

## Outcomes & Retrospective

The CLI now respects layered configuration: defaults → file → `--set` →
top-level flags. A new `zscripts.configuration` module centralizes parsing,
validation, and normalization, while `ToolkitConfig` gained an `examples_path`
field that is consumed by infrastructure wiring. CLI smoke tests, new
configuration unit tests, and existing service tests confirm the feature works
end to end. Documentation in `README.md` and `docs/configuration.md` guides
users through authoring TOML/JSON files and inline overrides. Static analysis
(`ruff`) passes; `mypy` continues to highlight historic `Any` usage outside the
new modules and will require a broader clean-up in a future effort.

## Context and Orientation

The CLI currently constructs `ToolkitConfig` objects using `zscripts.get_default_config()` and immediately mutates the instance based on `--adapter` and `--dangerous`. There is no reusable loader for configuration files. The dataclass in `zscripts/config.py` defines keys such as `allowed_paths`, `timeout_seconds`, `dangerous_mode`, `default_adapter`, and `redact_patterns`. Infrastructure wiring in `zscripts/infrastructure/__init__.py` converts that dataclass into `SandboxOptions`, a `RegexRedactor`, and a `FileSystemExampleRepository` rooted at `examples/`. Tests live in `tests/` and exercise CLI parsing (`tests/test_cli.py`), service orchestration (`tests/test_services.py`), and adapter parsing (`tests/test_adapters.py`). Documentation in `README.md` and `docs/` does not explain how to customize configuration.

## Plan of Work

First, design a configuration loading module that can parse TOML or JSON files, coerce data into Python types, validate fields, and merge overrides. Expose a `ConfigurationError` exception for user-friendly failures and a function `load_toolkit_config` that accepts an optional path and a mapping of overrides, returning a `ToolkitConfig` instance. The loader should support keys for all dataclass attributes plus a new `examples_path` pointing to a directory.

Next, update `ToolkitConfig` to include the `examples_path` attribute with an appropriate default. Ensure `build_toolkit_service` consumes that attribute instead of hardcoding `Path("examples")`. Revisit docstrings to clarify semantics and guarantee immutability where appropriate (e.g., using tuples internally but returning sequences).

Modify `cli.py` so the top-level parser accepts `--config PATH` and `--set KEY=VALUE` options before subcommands. Implement parsing logic that splits `KEY=VALUE` pairs, converts values based on key metadata (e.g., `timeout_seconds` to `int`, `allowed_paths` using the OS path separator, `redact_patterns` using newline or semicolon delimiters, `dangerous_mode` to boolean). Delegate to `load_toolkit_config`, catching `ConfigurationError` and reporting via `_fail` with actionable messaging. Update help text to document the new options and mention how to list available keys.

Add tests that cover three dimensions: pure configuration parsing in a new `tests/test_configuration.py`; CLI integration verifying that `--config` pulls values from a temporary TOML file and that conflicting overrides raise errors; and service wiring confirming `examples_path` is respected by `FileSystemExampleRepository`. Tests should also check that invalid keys or value types produce `ConfigurationError` with descriptive text. Where feasible, simulate CLI invocations using subprocess similar to existing CLI tests.

Enhance documentation by adding `docs/configuration.md` explaining file formats (TOML and JSON examples), supported keys, CLI overrides, and troubleshooting tips. Update `README.md` to link to the new doc and provide a quick-start snippet. Mention environment variable support if implemented or explicitly note its absence.

## Concrete Steps

1. Create `zscripts/configuration.py` and implement the loading, validation, and override functions described above. Include docstrings, type hints, and unit tests in `tests/test_configuration.py`.
2. Extend `ToolkitConfig` with the `examples_path` field and ensure defaults remain sensible. Update any code relying on the dataclass, including `get_default_config` and `build_toolkit_service`.
3. Modify `build_toolkit_service` to use the configurable examples directory and to pass the updated sandbox options. Provide docstrings clarifying expectations.
4. Update `cli.py` to accept the new CLI options, parse overrides, and call the configuration loader. Ensure `_fail` messaging covers configuration errors. Extend help text accordingly.
5. Document the new behavior in `README.md` and create `docs/configuration.md` with detailed guidance and examples.
6. Add or update tests covering configuration parsing, CLI behavior, and infrastructure changes.
7. Run `ruff check .`, `mypy .`, and `pytest` to confirm the project remains healthy.

## Validation and Acceptance

Successful completion allows:

- Running `python cli.py --config path/to/settings.toml guardrails` uses guardrails from the file and prints updated settings.
- Executing `python cli.py --set timeout_seconds=30 --set dangerous_mode=true guardrails` shows the overridden timeout and dangerous flag.
- `pytest` includes new tests that fail before the change (missing features) and pass afterward.
- Documentation clearly instructs how to craft configuration files and apply overrides.

## Idempotence and Recovery

The loader should tolerate repeated invocations and treat missing configuration files as errors with recovery instructions. CLI override parsing must not mutate shared state, and tests should clean up temporary files using `tmp_path`. Rerunning `make check` after partial completion should succeed once code matches the plan.

## Artifacts and Notes

- Include representative TOML and JSON snippets in the new documentation.
- Capture example CLI output for guardrails using overridden values to demonstrate acceptance.

## Interfaces and Dependencies

- In `zscripts/configuration.py`, define:

        class ConfigurationError(Exception):
            """Raised when configuration parsing or validation fails."""

        def load_toolkit_config(
            *,
            path: Path | None,
            overrides: Mapping[str, str],
            base: ToolkitConfig | None = None,
        ) -> ToolkitConfig:
            """Return a ToolkitConfig composed from defaults, optional file, and overrides."""

        def parse_overrides(raw: Sequence[str]) -> dict[str, str]:
            """Validate KEY=VALUE entries and return a normalized mapping."""

- Update `ToolkitConfig` in `zscripts/config.py` to include:

        examples_path: Path = field(default_factory=lambda: Path("examples"))

- Adjust `build_toolkit_service` to receive `config: ToolkitConfig` with the new field and initialize `FileSystemExampleRepository(config.examples_path)`.

