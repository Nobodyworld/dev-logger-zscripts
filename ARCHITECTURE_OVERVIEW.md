# Architecture Overview

zscripts is organised as a layered toolkit with explicit seams for configuration,
observability, and extensions. This document summarises the major components and
how they interact at runtime.

## Package Topology

```
+--------------------+        +----------------------+        +------------------+
|      CLI Layer     | -----> |  Application Services| -----> |   Domain Protocols|
| `cli.py`, subcommands|      | `ToolkitService`     |        | Interfaces & models|
+--------------------+        +----------------------+        +------------------+
         |                                                            |
         v                                                            v
+--------------------+        +----------------------+        +------------------+
| Observability Hub  |        | Infrastructure Adapters |     |  Extensions       |
| Metrics, tracing,  | <----> | Sandbox, schema, etc.   | <--> | CLI & service hooks|
| telemetry server   |        |                        |      | `zscripts/extensions`|
+--------------------+        +----------------------+        +------------------+
```

- **CLI Layer** parses global options (configuration, telemetry flags) before
  loading extensions. Extensions may register additional subcommands and are
  listed via `python cli.py extensions`.
- **Application Services** coordinate adapters, sandbox execution, schema
  validation, and now route every public method through telemetry spans. The
  service receives a `TelemetryManager` so instrumentation remains opt-in and
  reusable.
- **Domain Protocols** remain pure contracts that infrastructure components
  implement. They are unchanged by the new observability layer.
- **Observability Hub** (`zscripts/observability/`) provides structured logging,
  a Prometheus-compatible metrics registry, tracing spans, and an optional HTTP
  health server (`/healthz` and `/metrics`). The CLI activates the server when
  `telemetry_enabled` is true or `--enable-telemetry` is passed.
- **Extensions** live under `zscripts/extensions`. `ExtensionContext` exposes
  the active configuration, adapter registry, and telemetry handle so plugins
  can register CLI commands or react after the service is ready.

## Runtime Flow

1. `cli.py` parses global flags and loads configuration (defaults → file →
   `--set` overrides → global toggles like `--log-level`).
2. A `TelemetryManager` is constructed and started. When enabled it binds an
   HTTP server on the requested host/port and configures structured logging.
3. Extensions listed under `config.extensions` are imported via
   `load_extensions`, receive the current `ExtensionContext`, and may register
   new CLI commands.
4. The CLI executes the requested command. Each public method on
   `ToolkitService` runs inside a telemetry span which records counters,
   histograms, and structured logs.
5. After completion, `TelemetryManager` can be queried by automation agents via
   `/healthz` and `/metrics` to verify liveness and scrape metrics.

## Key Modules

- `zscripts/observability/metrics.py` — thread-safe counters and histograms with
  Prometheus exposition.
- `zscripts/observability/tracing.py` — context manager for spans that update
  metrics and logging in lockstep.
- `zscripts/observability/health.py` — background HTTP server exposing health
  and metrics.
- `zscripts/extensions/base.py` — defines `ExtensionContext` and the
  `ToolkitExtension` contract.
- `scripts/dev_start.py` — runs lint/type/security/tests/coverage checks and
  enforces an 85% coverage threshold.

Refer to `EXTENSION_GUIDE.md` for hands-on steps to create a new extension using
`scaffold_extension.py`, and `AUTOMATION.md` for guidance on operating the
telemetry endpoints and quality gates in automated environments.
