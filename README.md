# Zscripts – Django File Compiler

The toolkit automates collecting, consolidating, and analysing Django-style project files. It builds structured logs for Python, HTML, CSS, and JavaScript sources so you can review application code from a single location.

## Highlights
- Unified CLI entry point (`python -m zscripts.cli`) that replaces many ad-hoc scripts.
- Central `operations` module with reusable helpers for logging, consolidation, and analysis.
- Pytest-based regression suite covering the core workflows.
- `pyproject.toml` for reproducible tooling (install `.[dev]` to get the optional test extra).

## Quickstart
Run any command from the repository root:

```sh
# Inspect available presets
python -m zscripts.cli list-presets

# Generate per-app logs for Python and HTML files
python -m zscripts.cli log-apps --preset python --preset html

# Create consolidated single-file logs (defaults to Python)
python -m zscripts.cli log-single

# Snapshot the project tree with a timestamped log
python -m zscripts.cli tree

# Utilities for converting, analysing, and consolidating build artefacts
python -m zscripts.cli build convert
python -m zscripts.cli build analyse
python -m zscripts.cli build consolidate
```

Legacy scripts inside `zscripts/all`, `zscripts/all_single`, `zscripts/make`, and `zscripts/create` remain as thin wrappers but now delegate to the shared operations module and CLI.

## Project Structure

- `pyproject.toml` – packaging metadata and dev dependencies.
- `zscripts/__init__.py` – package initialiser exposing core modules.
- `zscripts/config.py` – centralises directory configuration and file-type presets.
- `zscripts/utils.py` – low-level filesystem helpers (gitignore handling, aggregation).
- `zscripts/operations.py` – high-level orchestration utilities used by the CLI and legacy scripts.
- `zscripts/cli.py` – argparse-based CLI frontend.
- `tests/test_operations.py` – regression coverage for the operations workflows.
- Remaining subdirectories (`all`, `all_single`, `make`, `create`, `by_file`, `todo`, `zreadme`) retain their original purpose but now benefit from the refactored helpers.

## Development Notes

Install optional dev dependencies and run the tests (requires `pytest`):

```sh
pip install .[dev]
python -m pytest
```

All CLI commands automatically create required log directories. Outputs live under `zscripts/logs/`, mirroring the preset names (`logs_apps_pyth`, `logs_single_files`, `logs_tree`, etc.).
