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
- **Comprehensive Reports**: Generate ready-to-share JSON or Markdown reports that combine parsing,
  summarization, explanations, and guardrail metadata via a single command.
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
python cli.py report --input examples/python/sample.log --format markdown
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
report_format = "json"
report_redact = false
report_fail_on = "never"
```

Set `report_format` to `"markdown"` to change the default renderer and toggle `report_redact`
when reports should automatically mask textual fields. Use `report_fail_on` to control
when the `report` command exits non-zero (`"never"`, `"warnings"`, or `"errors"`).

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

All commands that accept `--output` automatically create parent directories and
perform atomic writes. When the destination cannot be written (for example,
the directory is read-only or the path points to an existing directory) the CLI
aborts immediately with descriptive messages such as
`error: destination '<path>' is a directory` or
`error: parent directory '<path>' is not writable`, ensuring partial files are
never left behind.

### Parse and summarize existing logs

```bash
python cli.py parse --input examples/python/sample.log --output normalized.json
python cli.py summarize --input examples/python/sample.log
```

### Generate a comprehensive report

```bash
python cli.py report --input examples/python/sample.log --format json --output report.json
python cli.py report --input examples/python/sample.log --format markdown
python cli.py report --input examples/python/sample.log --fail-on errors
```

Reports include normalized log data, summaries, explanations, guardrail metadata, and an
overall severity flag. Use `--redact/--no-redact` to control redaction per invocation,
`--format` to choose JSON or Markdown, and `--fail-on` to enforce CI-friendly exit codes.

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

- `/healthz` returns a JSON payload with status, version, readiness, and liveness details.
- `/healthz/ready` and `/healthz/live` surface readiness and liveness checks with HTTP
  200/503 semantics suitable for probes.
- `/metrics` exposes Prometheus-formatted counters, histograms, and gauges (e.g.
  `zscripts_operations_total`, `zscripts_cli_invocations_total`,
  `zscripts_cli_duration_seconds`, `zscripts_extensions_active`, and
  `zscripts_health_http_requests_total`).
- Use `--log-format json` and `--log-level DEBUG` to tune structured logging for
  automated ingestion.
- Logs generated outside of adapter spans inherit the per-invocation correlation ID,
  so cross-component traces can be stitched together from log aggregation systems.
- For automation, `python scripts/ops_status.py --url http://127.0.0.1:9464` probes
  the health endpoint and writes a JSON summary alongside meaningful exit codes.
- Capture end-to-end diagnostics (health, hooks, manifest metadata, metrics) with
  `python cli.py diagnostics --include-metrics` or automate it via
  `python scripts/diagnostics_probe.py --output reports/diagnostics.json`; the
  helper exits non-zero when the telemetry status degrades so CI can fail fast.

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
| `extensions` | Manage extensions (list active modules, `--output-format json` for manifests, `extensions scaffold <name>` to generate templates). |
| `diagnostics` | Emit runtime diagnostics including telemetry status, hook counts, and optional Prometheus text. |
| `report` | Generate JSON or Markdown reports combining normalized data and guardrails. |

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
python scripts/collect_quality_metrics.py --output reports/metrics.json
# Offline fallback when coverage plugins are unavailable
python -m trace --count --coverdir trace_cov --module pytest
```

CI runs linting, type checks, and tests automatically.

`scripts/collect_quality_metrics.py` summarises coverage, complexity, dependency ratios, build footprint, and a measured latency
for `python cli.py guardrails` into `reports/metrics.json`. When network proxies block the `coverage` wheel, fall back to the
built-in trace invocation, which emits per-module coverage statistics and persists the curated subset to
`reports/coverage_summary.txt`.

## Further Reading

- [Architecture overview](ARCHITECTURE_OVERVIEW.md)
- [Extension guide](EXTENSION_GUIDE.md)
- [Automation playbook](AUTOMATION.md)
- [Architecture deep-dive](docs/architecture.md)
- [ToolkitService API surface](docs/api.md)
- [End-to-end workflows](docs/workflows.md)
- [Dependency audit & policy](docs/DEPENDENCIES.md)
- [Final refinement report](docs/final_report.md)
