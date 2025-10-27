# Zscripts AI Coding Agent Instructions

## Overview
Zscripts is a framework-agnostic CLI utility for aggregating source files into navigable logs across multi-stack projects (Python, JS, CSS, HTML, YAML). It helps teams audit and document codebases by generating per-directory logs and consolidated files.

## Architecture
- **Core Components**: CLI (`zscripts/cli.py`) handles commands; config loader (`zscripts/config.py`) manages JSON-based settings; utils (`zscripts/utils.py`) perform file scanning and aggregation.
- **Data Flow**: Scans project root → filters by extensions/skip patterns → categorizes files via `file_types` mappings → writes logs to configured directories under `zscripts/logs/`.
- **Structural Decisions**: Modular design with legacy script dirs (`all/`, `single/`, etc.) for backwards compatibility; paths resolved relative to `zscripts/` package for portability.

## Key Workflows
- **Generate Logs**: `python -m zscripts collect --types python,js --project-root .` - Creates per-app logs in `logs_apps_pyth/` and `logs_apps_js/`.
- **Consolidate Sources**: `python -m zscripts consolidate --types python --output /tmp/all-python.txt` - Merges all Python files into a single artifact.
- **Snapshot Tree**: `python -m zscripts tree --project-root .` - Outputs filtered project structure with inlined content to `logs_single_files/tree.txt`.
- **Custom Config**: Use `--config path/to/custom.json` to override defaults from `zscripts.config.json`.

## Conventions & Patterns
- **Configuration**: JSON schema in `zscripts.config.json`; skip dirs like `["node_modules", "venv"]`; file type mappings e.g., `"models.py": "models_files"`.
- **File Filtering**: Combines `.gitignore` patterns with config `skip` list; extensions mapped to types (`.py` → python, `.js` → js).
- **Output Structure**: Logs organized by type in subdirs; single files use names like `capture_all_pyth.txt`.
- **No External Deps**: Pure Python standard library; run as module (`python -m zscripts`).

## Examples
- Categorize Django files: Set `"views.py": "views_files"` in `file_types` for separation in logs.
- Cross-stack audit: Run `collect --types all` on `sample_project/` to see Python (`backend/service.py`), JSX (`frontend/App.jsx`), YAML (`infra/pipeline.yaml`).
- CI Integration: Invoke CLI in GitHub Actions as shown in `sample_project/infra/pipeline.yaml`.