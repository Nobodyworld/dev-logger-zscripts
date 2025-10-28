# Zscripts – Django File Compiler

The toolkit automates collecting, consolidating, and analysing Django-style project files. It builds structured logs for Python, HTML, CSS, and JavaScript sources so you can review application code from a single location. The codebase targets **Python 3.11 or newer** to take advantage of modern typing features and the standard `tomllib` parser.

## Highlights
- Unified CLI entry point (`python cli.py`) orchestrating collection, parsing, reporting, diagnostics, and extensions.
- Typed configuration system (`ToolkitConfig`) with TOML overrides and inline `--set` coercion.
- Telemetry-aware observability pipeline with Prometheus metrics and diagnostics snapshots.
- Central `operations` module with reusable helpers for logging, consolidation, and analysis.
- Pytest-based regression suite covering the core workflows.
- `pyproject.toml` for reproducible tooling (install `.[dev]` to get the optional test extra).

## Quickstart
Run commands from the repository root (the `cli.py` shim simply executes `zscripts.cli.main()`):

```sh
# Inspect guardrail settings derived from configuration
python cli.py guardrails

# Parse a log file using a specific adapter
python cli.py --adapter python parse --input examples/python/sample.log

# Generate a report in Markdown and write it to disk
python cli.py report --input examples/python/sample.log --format markdown --output report.md

# Emit diagnostics (with Prometheus metrics when telemetry is enabled)
python cli.py --enable-telemetry diagnostics --format text

# List loaded extensions and scaffold a new one
python cli.py extensions --output-format json
python cli.py extensions scaffold demo_extension --directory my_extensions

# Execute an extension-provided command (after enabling it via configuration)
python cli.py --config settings.toml echo "hello world"
```

Legacy scripts inside `zscripts/all`, `zscripts/all_single`, `zscripts/make`, and `zscripts/create` remain as thin wrappers but now delegate to the shared operations module and CLI.

## Project Structure

- `pyproject.toml` – packaging metadata and dev dependencies.
- `zscripts/__init__.py` – package initialiser exposing core modules.
- `zscripts/config.py` – houses `ToolkitConfig`, default presets, and legacy directory constants.
- `zscripts/configuration.py` – loads configuration files, applies CLI overrides, and returns `ToolkitConfig` instances.
- `zscripts/utils.py` – low-level filesystem helpers (gitignore handling, aggregation).
- `zscripts/operations.py` – high-level orchestration utilities used by the CLI and legacy scripts.
- `zscripts/cli.py` – argparse-based CLI frontend.
- `tests/test_operations.py` – regression coverage for the operations workflows.
- Remaining subdirectories (`all`, `all_single`, `make`, `create`, `by_file`, `todo`, `zreadme`) retain their original purpose but now benefit from the refactored helpers.

## Development Notes

Install the optional dev dependencies and run the full quality gate:

```sh
pip install .[dev]
make check  # fmt + lint + mypy + bandit + pytest
```

Useful follow-up commands:

- `make coverage` – generate a JSON coverage report under `reports/`.
- `make fmt` / `make lint` – run Ruff format and lint passes independently.
- `make type` – execute the strict mypy suite (`pyproject.toml` defines the targets).
- `make security` – invoke Bandit over `zscripts` and the sample project assets.

All CLI commands automatically create required log directories. Outputs live under `zscripts/logs/`, mirroring the preset names (`logs_apps_pyth`, `logs_single_files`, `logs_tree`, etc.).

Configuration tips:

- Use `python cli.py --config settings.toml ...` to load TOML overrides (see `examples/config/` for inspiration).
- Apply ad-hoc overrides with `--set key=value` (e.g., `--set report_fail_on=errors`).
- Enable telemetry metrics via `--enable-telemetry` (optional `--telemetry-host`/`--telemetry-port`).
- Extensions and services can now publish custom health checks via the shared
  registry. Use `context.health_checks.register(...)` inside an extension or the
  `scripts/scaffold_module.py health <name>` helper to generate a reusable
  provider skeleton. The diagnostics command (`python cli.py diagnostics
  --include-metrics`) surfaces each registered check alongside the core HTTP
  probe, making it easy to trace degraded states back to individual modules.

### Scaffolding shortcuts

- `python scripts/scaffold_module.py extension demo_probe` – create an
  extension skeleton instrumented with telemetry and a ready-to-use health
  snapshot.
- `python scripts/scaffold_module.py health ingestion_queue` – generate a
  standalone health check provider that can be imported from schedulers or
  background workers and registered against the telemetry registry.
- Reference implementations live under
  `zscripts/extensions/examples/`, including
  `plugin_health.py` (registry integration) and `plugin_metrics.py` (hook
  instrumentation).
