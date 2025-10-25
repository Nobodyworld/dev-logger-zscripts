# Extension Authoring Guidelines

Extensions under this directory must expose a callable `get_extension()` that returns an
object implementing `ToolkitExtensionProtocol`. Prefer subclassing
`zscripts.extensions.base.ToolkitExtension` for sensible defaults.

When adding new files:
- Keep imports lazy to avoid circular dependencies with `zscripts.cli` or
  `zscripts.application` modules.
- Instrument long-running work with `TelemetryManager.span()` via the provided
  `ExtensionContext.telemetry` object when possible.
- Avoid direct `print()` calls unless the command produces CLI output. Instead,
  use `zscripts.observability.logging.get_logger` for structured logs.

Any new extension should include short module-level docstrings and type annotations.
