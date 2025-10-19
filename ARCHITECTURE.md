# System Architecture Overview

## High-Level Components

- **zscripts/cli.py** – Entry point for the CLI. Parses arguments, orchestrates
  collection/consolidation/tree workflows, and now relies on the shared preset
  registry (`zscripts/presets.py`) to avoid duplicated metadata.
- **zscripts/config.py** – Loads and validates the JSON configuration file,
  normalising data into immutable dataclasses and resolving filesystem paths.
- **zscripts/utils.py** – Filesystem traversal helpers for collecting logs,
  building trees, and respecting ignore patterns.
- **zscripts/presets.py** – Central registry that defines stack presets
  (extensions, default log directories, and filenames). Shared across the CLI
  and agent adapters.
- **agents/cli_adapter.py** – Provides structured command metadata for agent
  frameworks; returns serialisable payloads that describe CLI parameters.
- **tests/** – Pytest suite covering CLI behaviour, security checks, presets, and
  agent metadata.

## Data Flow

1. The CLI loads configuration via `zscripts.config.load_config()`.
2. Preset metadata is sourced from `zscripts.presets`, ensuring consistent
   extension sets and default paths.
3. Commands call `zscripts.utils` helpers to read the filesystem, respecting the
   ignore patterns derived from configuration and gitignore files.
4. The agent adapter consumes `zscripts.presets` to mirror CLI capabilities in a
   declarative format for orchestration tools.

## Key Guarantees

- **Immutability:** Preset mappings and configuration snapshots use
  `MappingProxyType` or frozen dataclasses to avoid accidental mutation.
- **Validation:** CLI output paths are validated for writability before any file
  I/O occurs, producing actionable errors for automation systems.
- **Type Safety:** Strict mypy configuration ensures new modules maintain typing
  guarantees (e.g., agent payloads and preset registries).

