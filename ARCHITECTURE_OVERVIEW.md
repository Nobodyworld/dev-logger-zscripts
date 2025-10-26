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
  loading extensions. An `InstrumentationManager` wraps every command, binding
  correlation IDs and emitting CLI/operation metrics. Extensions may register
  additional subcommands and are managed via `python cli.py extensions` (which
  now includes a `scaffold` helper for generating new modules).
- **Application Services** coordinate adapters, sandbox execution, schema
  validation, and now route every public method through telemetry spans. The
  service receives a `TelemetryManager` so instrumentation remains opt-in and
  reusable.
- **Domain Protocols** remain pure contracts that infrastructure components
  implement. They are unchanged by the new observability layer.
- **Observability Hub** (`zscripts/observability/`) provides structured logging,
  a Prometheus-compatible metrics registry, tracing spans, and an optional HTTP
  health server (`/healthz`, `/healthz/ready`, `/healthz/live`, `/metrics`). The
  CLI activates the server when `telemetry_enabled` is true or
  `--enable-telemetry` is passed, and records dedicated metrics
  (`zscripts_cli_invocations_total`, `zscripts_cli_duration_seconds`,
  `zscripts_operations_total`, `zscripts_operation_duration_seconds`,
  `zscripts_extensions_active`).
- **Extensions** live under `zscripts/extensions`. `ExtensionContext` exposes
  the active configuration, adapter registry, telemetry manager, and
  instrumentation manager so plugins can register CLI commands or react after
  the service is ready with full observability.

## Runtime Flow

1. `cli.py` parses global flags and loads configuration (defaults → file →
   `--set` overrides → global toggles like `--log-level`).
2. A `TelemetryManager` is constructed and started. When enabled it binds an
   HTTP server on the requested host/port and configures structured logging.
3. Extensions listed under `config.extensions` are imported via
   `load_extensions`, receive the current `ExtensionContext`, and may register
   new CLI commands. The loader itself is instrumented so extension imports and
   instantiation are counted and timed.
4. The CLI executes the requested command inside an instrumentation operation
   that applies a per-invocation correlation ID, records CLI/operation metrics,
   and then delegates into `ToolkitService`, whose public methods also
   instrument spans.
5. After completion, `TelemetryManager` can be queried by automation agents via
   `/healthz` and `/metrics` to verify liveness and scrape service-level and
   CLI-level metrics.

## Key Modules

- `zscripts/observability/instrumentation.py` — unified spans, metrics, and
  correlation ID binding for CLI and extensions.
- `zscripts/observability/metrics.py` — thread-safe counters, gauges, and
  histograms with Prometheus exposition.
- `zscripts/observability/tracing.py` — context manager for spans that update
  metrics and logging in lockstep.
- `zscripts/observability/health.py` — background HTTP server exposing health
  (readiness/liveness) and metrics.
- `zscripts/extensions/base.py` — defines `ExtensionContext` and the
  `ToolkitExtension` contract.
- `zscripts/extensions/scaffolding.py` — renders starter modules instrumented
  with telemetry helpers.
- `scripts/bootstrap.py` — installs dependencies and configures pre-commit
  hooks.
- `scripts/dev_start.py` — runs lint/type/security/tests/coverage checks and
  enforces an 85% coverage threshold.
- `scripts/agent_guard.py` — runs lint, mypy, bandit, and pytest for quick
  agent-friendly validation.
- `scripts/tag_release.py` — bumps semantic versions and optionally creates git
  tags to anchor release notes.

Refer to `EXTENSION_GUIDE.md` for hands-on steps to create a new extension using
`python cli.py extensions scaffold`, and `AUTOMATION.md` for guidance on
operating the telemetry endpoints and quality gates in automated environments.
