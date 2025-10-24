# zscripts — Universal Build Log & LLM Ops Toolkit

zscripts is a framework-agnostic toolkit for collecting build, compile, and test
logs, normalizing them into a shared JSON schema, and generating summaries for
LLM-driven workflows. The project ships with adapters for Python, JavaScript,
Java, Go, Rust, .NET, Docker, and CI ecosystems.

## Features

- **Unified CLI**: `python cli.py` exposes subcommands to collect, parse,
  summarize, explain, redact, and inspect guardrails.
- **Structured Schema**: Normalize logs into a JSON schema (`schemas/normalized_log.json`)
  backed by typed dataclasses.
- **Safety Guardrails**: Sandboxed subprocess execution, path allowlists, and
  default secret redaction.
- **Adapter Library**: Reusable parser modules under `adapters/` for common
  ecosystems.
- **Examples & Docs**: Bundled sample logs and quickstart guides for each
  adapter.

## Quick Start

```bash
python -m pip install -e .[dev]
python cli.py parse --adapter python --input examples/python/sample.log
python cli.py summarize --adapter docker --input examples/docker/sample.log
```

See `docs/INDEX.md` for full documentation.

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
mypy zscripts
pytest
```

CI runs linting, type checks, and tests automatically.
