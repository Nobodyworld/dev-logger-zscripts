# Extension Guide

This guide explains how to create and register a toolkit extension using the
new plugin system.

## 1. Scaffold a module

Use the built-in CLI scaffolder to generate a template module. The command
ensures naming conventions and boilerplate remain consistent with
`zscripts.extensions.base.ToolkitExtension`.

```bash
python cli.py extensions scaffold demo_adapter
```

The command creates `zscripts/extensions/demo_adapter.py` with a skeleton
extension that registers a CLI command, exports `get_extension()`, and wires a
baseline health check into `context.health_checks` so diagnostics immediately
include extension status.

## 2. Implement extension logic

Edit the generated module:

- Update `name`, `description`, and `version` to describe your extension.
- Declare `capabilities` (e.g. `("cli", "ingest")`) so automation can route
  traffic based on supported behaviours. Optionally set `config_keys` to list
  configuration entries your extension honours.
- Implement `register_cli` to add CLI options or subcommands using the provided
  `ExtensionContext`. The context exposes the adapter registry, telemetry
  manager, instrumentation manager, and active configuration.
- Add a handler method (e.g. `handle_cli`) to perform your extension-specific
  work. Use `context.instrumentation.operation(...)` to record spans, metrics,
  and correlation IDs for long-running operations. Structured logs written via
  `context.logger` automatically include the current correlation ID.
- Optionally implement `after_service_ready` and inspect `self.manifest` to emit
  metadata once the application service is initialised.
- Register lifecycle hooks with `self.register_hook("service_ready", callback)`
  to receive events emitted by the new `ExtensionHookRegistry`. Hook callbacks
  are instrumented automatically and surfaced through diagnostics payloads so
  operators can confirm which plugins respond to each lifecycle stage.
- Publish health information with `context.health_checks.register(...)`. When
  telemetry is enabled these entries appear under `cli diagnostics` and update
  the Prometheus gauge `zscripts_health_checks_status`. Standalone services can
  scaffold a reusable provider via `python scripts/scaffold_module.py health
  <name>` and import it wherever the registry is available.

## 3. Enable the extension

Add the module’s dotted path to the `extensions` configuration field via file
or CLI override:

```toml
extensions = ["zscripts.extensions.demo_adapter"]
```

Or at runtime:

```bash
python cli.py --set extensions=zscripts.extensions.demo_adapter extensions
```

## 4. Verify

List loaded extensions to confirm the new module is active:

```bash
python cli.py extensions --output-format json
```

The manifest output includes the module path, version, capabilities, and any
declared configuration keys. Plain-text output remains available via
`python cli.py extensions` for interactive inspection.

Run the CLI command registered by your extension:

```bash
python cli.py demo_adapter --message "hello"
```

The plugin system loads extensions before parsing subcommands, so new commands
and overrides are available immediately.

Refer to `zscripts/extensions/examples/plugin_echo.py` for a minimal CLI
integration, `plugin_metrics.py` for a hook-driven diagnostics example, and
`plugin_health.py` for registry-backed health probes. The scaffolding template
(`scripts/scaffold_extension.py`) now registers a `service_ready` hook, logs its
manifest automatically, and publishes a baseline health snapshot so new plugins
follow best practices out of the box.
