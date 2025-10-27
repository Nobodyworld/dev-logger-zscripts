# Configuration & Overrides

The zscripts CLI reads configuration in three layers, applied in the following
order:

1. Built-in defaults defined by `ToolkitConfig`.
2. Values loaded from an optional TOML or JSON configuration file passed via
   `--config`.
3. Inline overrides provided through repeated `--set KEY=VALUE` flags.
4. Convenience switches such as `--dangerous` and `--adapter` (which apply last).

If a setting is not specified in later layers it retains the value from the
previous layers.

## Supported keys

The configuration file accepts the keys below. All keys are optional.

- `allowed_paths` (array or string): Paths the sandbox may read. Strings accept
  the platform path separator (`:` or `;`), commas, or newlines to separate
  entries. Each path is expanded relative to the current working directory.
- `timeout_seconds` (integer): Maximum runtime for sandboxed subprocesses. Must
  be greater than zero.
- `dangerous_mode` (boolean): When `true`, disables sandbox guardrails.
- `default_adapter` (string): Adapter identifier used when a subcommand omits
  `--adapter`.
- `redact_patterns` (array or string): Regular expressions that will be applied
  to redact sensitive content from logs. Multiple entries can be separated with
  commas, semicolons, or newlines.
- `examples_path` (string): Directory containing bundled example logs returned
  by `python cli.py examples`.
- `telemetry_enabled` (boolean): When `true`, starts the HTTP health/metrics
  server for telemetry scraping.
- `telemetry_host` (string): Interface to bind the telemetry server to. Defaults
  to `127.0.0.1`.
- `telemetry_port` (integer): Port for the telemetry server. Use `0` to request
  an ephemeral port.
- `log_level` (string): Minimum structured log level (e.g. `INFO`, `DEBUG`).
- `log_format` (string): Structured log format, either `text` or `json`.
- `report_format` (string): Default formatter for the `report` command (`json`
  or `markdown`).
- `report_redact` (boolean): When `true`, redacts textual fields in generated
  reports by default.
- `report_fail_on` (string): Severity threshold that forces the `report`
  command to exit non-zero. Accepts `never`, `warnings`, or `errors`.
- `extensions` (array or string): Dotted module paths for extensions to load.
  Strings accept separators in the same fashion as `allowed_paths`.

## File formats

Use either TOML or JSON. TOML is recommended for readability.

```toml
# settings.toml
allowed_paths = ["examples", "~/workspace/logs"]
timeout_seconds = 90
dangerous_mode = false
default_adapter = "python"
redact_patterns = ["(?i)secret=([A-Za-z0-9_-]+)"]
examples_path = "./custom_examples"
telemetry_enabled = true
telemetry_host = "0.0.0.0"
telemetry_port = 9464
log_level = "INFO"
log_format = "json"
report_format = "json"
report_redact = false
report_fail_on = "never"
extensions = ["zscripts.extensions.examples.plugin_echo"]
```

```json
{
  "allowed_paths": ["examples", "~/workspace/logs"],
  "timeout_seconds": 90,
  "dangerous_mode": false,
  "default_adapter": "python",
  "redact_patterns": ["(?i)secret=([A-Za-z0-9_-]+)"],
  "examples_path": "./custom_examples",
  "telemetry_enabled": true,
  "telemetry_host": "0.0.0.0",
  "telemetry_port": 9464,
  "log_level": "INFO",
  "log_format": "json",
  "report_format": "json",
  "report_redact": false,
  "report_fail_on": "never",
  "extensions": ["zscripts.extensions.examples.plugin_echo"]
}
```

## CLI overrides

Override individual keys without editing the configuration file:

```bash
python cli.py --config settings.toml --set timeout_seconds=30 --set dangerous_mode=true guardrails
```

Boolean overrides accept `true`, `false`, `1`, and `0` (case-insensitive).
Repeat `--set` for each key you want to change.

### Convenience toggles

- `--enable-telemetry`: starts the telemetry server for the current command.
- `--telemetry-host`, `--telemetry-port`: override host/port at runtime.
- `--log-level`, `--log-format`: adjust logging without editing configuration.
- `--redact/--no-redact`: override the reporting redaction toggle for a single
  invocation.
- `--fail-on`: override the failure policy for the `report` command (`never`,
  `warnings`, `errors`).
- `--adapter`: override the default adapter for the command being executed.
- `--dangerous`: temporarily disable guardrails.

## Troubleshooting

- **Unknown key**: The loader raises `ConfigurationError` when a file or
  override references an unsupported key. Fix the typo or remove the entry.
- **Type mismatch**: Ensure numeric values are integers and booleans are valid
  (`true`/`false`, `yes`/`no`, `1`/`0`).
- **File not found**: Double-check relative paths to configuration files and
  example directories. Paths are resolved relative to the current working
  directory.
