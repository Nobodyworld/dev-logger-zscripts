# zscripts — Universal Build Log & LLM Ops Toolkit

zscripts is a framework-agnostic toolkit for collecting build, compile, and test
logs, normalizing them into a shared JSON schema, and generating summaries for
LLM-driven workflows. The project ships with adapters for Python, JavaScript,
Java, Go, Rust, .NET, Docker, and CI ecosystems.

## Features

- **Unified CLI**: `python cli.py` exposes subcommands to collect, parse,
  summarize, explain, redact, and inspect guardrails.
- **Application Service Layer**: `zscripts.application.services.ToolkitService` provides the same orchestration for programmatic integrations.
- **Structured Schema**: Normalize logs into a JSON schema (`schemas/normalized_log.json`)
  backed by typed dataclasses.
- **Safety Guardrails**: Sandboxed subprocess execution, path allowlists, and
  default secret redaction.
- **Adapter Library**: Reusable parser modules under `adapters/` for common
  ecosystems.
- **Observability**: Structured logging, Prometheus-style metrics, tracing spans,
  and an optional health server activated via `--enable-telemetry`.
- **Examples & Docs**: Bundled sample logs and quickstart guides for each
  adapter.
- **Configurable Runtime**: Load configuration from TOML or JSON files and
  override settings with `--set KEY=VALUE` on the CLI.

## Architecture

The codebase follows a clean-architecture layout to keep adapters, I/O, and
policy decisions isolated:

- **Domain protocols** under `zscripts.domain` describe the behaviors adapters,
  redactors, repositories, and sandbox runners must implement.
- **Application services** in `zscripts.application` coordinate those
  protocols. The `ToolkitService` used by the CLI is also safe to reuse inside
  other tooling or tests.
- **Infrastructure adapters** located in `zscripts.infrastructure` bridge the
  domain contracts to the existing modules in `adapters/` and `scripts/` while
  wiring configuration from `zscripts.config`.

Each layer depends only on the one below it so that domain rules remain
testable and independent of concrete infrastructure details.

## Setup

1. **Clone the repository** and create a virtual environment:

   ```bash
   git clone https://github.com/zscripts/zscripts.git
   cd zscripts
   python -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies** (runtime + developer tooling):

   ```bash
   python -m pip install -e .[dev]
   ```

3. **Sanity-check the environment** using the aggregated make target:

   ```bash
   make check
   ```

## Quick Start

```bash
python -m pip install -e .[dev]
python cli.py parse --adapter python --input examples/python/sample.log
python cli.py summarize --adapter docker --input examples/docker/sample.log
```

See `docs/INDEX.md` for full documentation.

## Configuration

Create a `settings.toml` file to customize sandbox guardrails, default
adapters, and redaction rules:

```toml
timeout_seconds = 60
dangerous_mode = false
allowed_paths = ["examples", "~/workspace/logs"]
default_adapter = "python"
redact_patterns = ["(?i)password=([A-Za-z0-9]+)"]
examples_path = "./custom_examples"
```

Apply the configuration when invoking the CLI and layer additional overrides
using `--set` arguments:

```bash
python cli.py --config settings.toml --set timeout_seconds=30 guardrails
```

Refer to `docs/configuration.md` for a complete description of supported keys,
file formats, and precedence rules.

## Usage Examples

### Collect logs from a sandboxed command

```bash
python cli.py collect --command pytest --redact --output logs.txt
```

The CLI now validates that `--command` includes an executable token and surfaces
actionable error messages (exit code 2) instead of raw tracebacks when a log
source is missing.

### Parse and summarize existing logs

```bash
python cli.py parse --input examples/python/sample.log --output normalized.json
python cli.py summarize --input examples/python/sample.log
```

### Inspect guardrails and available examples

```bash
python cli.py guardrails
python cli.py examples --adapter python
```

## Telemetry & Health

Enable telemetry when running commands that should expose liveness and metrics. Every
CLI command now binds a correlation ID and emits Prometheus metrics that capture
command outcome and duration, making it easy to trace automation runs end-to-end:

```bash
python cli.py --enable-telemetry --telemetry-port 9100 guardrails
```

- `/healthz` returns a JSON payload with status and version information.
- `/metrics` exposes Prometheus-formatted counters and histograms (e.g.
  `zscripts_requests_total`, `zscripts_cli_invocations_total`, and
  `zscripts_cli_duration_seconds`).
- Use `--log-format json` and `--log-level DEBUG` to tune structured logging for
  automated ingestion.
- Logs generated outside of adapter spans inherit the per-invocation correlation ID,
  so cross-component traces can be stitched together from log aggregation systems.

## CLI Reference

| Command | Description |
| --- | --- |
| `collect` | Read logs from a file, STDIN, or sandboxed command execution. |
| `parse` | Convert raw logs into normalized JSON. |
| `summarize` | Emit a compact summary of parsed logs. |
| `explain` | Produce a richer explanation for LLM prompts. |
| `guardrails` | Display sandbox configuration and whether `--dangerous` is set. |
| `redact` | Mask secrets using configurable regex patterns. |
| `examples` | List bundled example log files per adapter. |
| `extensions` | Display active extensions and their descriptions. |

## Package Layout

```
/adapters        # Adapter implementations per ecosystem
/scripts         # Sandbox and redaction utilities
/schemas         # JSON schema files
/examples        # Sample logs used for smoke tests and docs
/docs            # Documentation index, schema spec, adapter quickstarts
/tests           # Pytest smoke tests for adapters and CLI
zscripts/        # Python package providing CLI helpers and config
cli.py           # CLI entry point
```

## Development

```bash
python -m pip install -e .[dev]
ruff check .
mypy zscripts/configuration.py zscripts/config.py zscripts/__init__.py
pytest
python scripts/dev_start.py  # runs lint/type/security/tests with coverage ≥85%
python -m trace --count --summary --coverdir=coverage_reports scripts/run_pytest_with_trace.py
# Offline fallback when coverage plugins are unavailable
python -m trace --count --coverdir trace_cov --module pytest
```

CI runs linting, type checks, and tests automatically.

The trace invocation emits per-module coverage statistics and the curated subset is persisted to `reports/coverage_summary.txt`.

## Further Reading

- [Architecture overview](ARCHITECTURE_OVERVIEW.md)
- [Extension guide](EXTENSION_GUIDE.md)
- [Automation playbook](AUTOMATION.md)
- [Architecture deep-dive](docs/architecture.md)
- [ToolkitService API surface](docs/api.md)
- [End-to-end workflows](docs/workflows.md)
- [Dependency audit & policy](docs/DEPENDENCIES.md)
- [Final refinement report](docs/final_report.md)
