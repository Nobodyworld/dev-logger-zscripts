# System Architecture Overview

## High-Level Components

- **`zscripts/cli.py`** – Parses CLI arguments, performs path validation, and
  orchestrates the `collect`, `consolidate`, and `tree` commands. It delegates
  extension lookups to the preset registry and emits structured logs with stable
  error identifiers.
- **`zscripts/config.py`** – Loads JSON configuration files, normalises the
  values into immutable dataclasses, resolves filesystem paths relative to the
  package root, and exposes compatibility accessors for legacy constants.
- **`zscripts/utils.py`** – Provides traversal and transformation helpers used by
  every CLI command. Responsibilities include ignore pattern compilation,
  grouping of source files, consolidation of outputs, and generation of tree
  snapshots.
- **`zscripts/presets.py`** – Maintains the authoritative list of language
  presets. Each preset defines extensions, log directory names, and single-file
  targets. Both the CLI and agent adapter rely on this registry to stay in
  sync.
- **`agents/cli_adapter.py`** – Publishes a machine-readable description of the
  CLI surface. The adapter mirrors default values and preset names so that MCP
  manifests, AgentKit profiles, or other orchestration layers can remain
  correct without manual updates.
- **`examples/sample_project/`** – Demonstrates how a multi-language repository behaves
  under the CLI and provides fixtures for tests.
- **`tests/`** – Exercises CLI flows, preset behaviour, and serialization
  guarantees to prevent regressions.

## Execution Walkthrough

1. The CLI entry point (`python -m zscripts`) parses arguments and resolves the
   project root, defaulting to the nearest Git repository or `pyproject.toml`.
2. `zscripts.config.load_config()` reads configuration JSON (optionally merged
   with overrides) and produces immutable `Config` and `ResolvedPaths`
   structures.
3. Based on the requested subcommand, the CLI retrieves preset metadata from
   `zscripts.presets` helpers to build extension filters and default output
   locations.
4. `zscripts.utils` orchestrates filesystem traversal, ensuring ignore patterns
   from both configuration and `.gitignore` files are respected. File contents
   are streamed and summarised into the desired artefacts (per-app logs,
   consolidated bundles, or tree snapshots).
5. The CLI emits structured summaries and exit codes that automation systems can
   consume.
6. Separately, orchestration frameworks call `agents.cli_adapter.export_cli_metadata()`
   to retrieve an aligned description of commands and presets.

## Data Flow

- Configuration is read once, cached via `_get_default_config()`, and reused
  across modules to avoid repeated disk access.
- Preset definitions live in memory as frozen dataclasses; extension maps and
  directories are exposed through read-only `MappingProxyType` instances to
  prevent mutation.
- CLI commands stream filesystem content via generators, keeping memory usage
  predictable for large repositories.
- Agent payloads serialise to plain dictionaries so they can be stored in MCP
  manifests, JSON files, or API payloads without further adaptation.

## Key Guarantees

- **Immutability:** Preset mappings and configuration snapshots use
  `MappingProxyType` or frozen dataclasses to avoid accidental mutation.
- **Validation:** CLI output paths are validated for writability before any file
  I/O occurs, producing actionable errors for automation systems.
- **Type Safety:** Strict mypy configuration ensures new modules maintain typing
  guarantees (e.g., agent payloads and preset registries).

## Extensibility

- **Adding new stacks:** Extend `_PRESETS` in `zscripts/presets.py`. The CLI and
  agent adapter automatically pick up the new preset, and defaults can be
  overridden via `configs/zscripts.config.json`.
- **Customising ignore rules:** Update `configs/zscripts.config.json` to amend `skip`
  directories or `user_ignore_patterns`. `zscripts.utils.load_gitignore_patterns`
  merges configuration with `.gitignore` contents and caches the result.
- **Integrating automation:** Consume `export_cli_metadata()` to render rich
  prompts or UI. The payload includes example commands and parameter metadata to
  keep interactive shells and AI copilots aligned with the CLI.

