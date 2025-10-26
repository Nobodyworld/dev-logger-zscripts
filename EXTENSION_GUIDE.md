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
extension that registers a CLI command and exports `get_extension()`.

## 2. Implement extension logic

Edit the generated module:

- Update `name` and `description` to describe your extension.
- Implement `register_cli` to add CLI options or subcommands using the provided
  `ExtensionContext`. The context exposes the adapter registry, telemetry
  manager, instrumentation manager, and active configuration.
- Add a handler method (e.g. `handle_cli`) to perform your extension-specific
  work. Use `context.instrumentation.operation(...)` to record spans, metrics,
  and correlation IDs for long-running operations. Structured logs written via
  `context.logger` automatically include the current correlation ID.

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
python cli.py extensions
```

Run the CLI command registered by your extension:

```bash
python cli.py demo_adapter --message "hello"
```

The plugin system loads extensions before parsing subcommands, so new commands
and overrides are available immediately.

Refer to `zscripts/extensions/examples/plugin_echo.py` for a minimal reference
implementation.
