# Agent Interface

This repository ships an agent-facing adapter that describes the CLI surface in a
machine-readable format. Use it to feed MCP/AgentKit style systems or other
assistant frameworks that need declarative command metadata. The adapter mirrors
the CLI defaults so that orchestration layers never fall out of sync with new
releases.

## Integration Checklist

1. Add `agents/` to the Python path of your automation runtime.
2. Call `agents.cli_adapter.export_cli_metadata()` during startup or during
   capability discovery.
3. Persist the returned payload (JSON/YAML/etc.) or feed it directly into the
   tooling interface that renders commands to the end user.
4. Re-run the export whenever you bump the `zscripts` dependency to pick up new
   presets or command flags.

## Python API

```python
from agents.cli_adapter import export_cli_metadata

metadata = export_cli_metadata()
```

`metadata` is a dictionary with two keys:

- `commands` – list of command payloads. Each payload includes `name`,
  `summary`, `parameters`, `examples`, and `returns` fields suitable for JSON
  schema generation or prompt templating.
- `presets` – list of preset descriptors coming from `zscripts.presets`. These
  entries mirror the CLI options (`python`, `html`, `css`, `js`, `python_html`,
  plus aggregated `all/any` choices) and include default log/target names.

Every command definition also exposes:

- **`parameters`** – each parameter object contains type hints, default values,
  enumerated `choices` (when applicable), and an example snippet.
- **`examples`** – concrete CLI strings intended for insertion into prompts or
  documentation.
- **`returns`** – human-readable expectations that downstream systems can turn
  into tooltips or success criteria.

## Parameter Schema

Each command parameter payload contains:

| Field | Meaning |
| ----- | ------- |
| `name` | CLI flag or argument identifier. |
| `type` | Logical type hint (`string`, `path`, `boolean`, `integer`). |
| `description` | Human-readable explanation of the option. |
| `required` | Whether the parameter must be provided. |
| `default` | Default value when applicable. |
| `choices` | Enumerated options (empty when free-form). |
| `example` | Copy-pastable snippet showing typical usage. |

## Example Payload

```json
{
  "commands": [
    {
      "name": "collect",
      "summary": "Generate per-application source logs for selected stacks.",
      "parameters": [
        {"name": "types", "type": "string", "choices": ["python", "html", "css", "js", "python_html", "all"]},
        {"name": "project_root", "type": "path"},
        {"name": "output_dir", "type": "path"},
        {"name": "dry_run", "type": "boolean", "default": false}
      ],
      "examples": ["python -m zscripts collect --types python,js"],
      "returns": "Exit code 0 on success; writes log files to the configured directory."
    }
  ],
  "presets": [
    {"name": "python", "collect_log": "logs_apps_pyth", "single_target": "capture_all_pyth.txt"}
  ]
}
```

## Troubleshooting

- **Missing commands:** Ensure your automation environment imports the correct
  version of `zscripts`. Running `python -m zscripts --help` locally should list
  the same commands as the exported payload.
- **Stale presets:** If metadata lacks new presets, confirm that
  `export_cli_metadata()` is executed after dependency upgrades (e.g., during
  container build or agent startup).
- **Schema drift:** The payload intentionally avoids optional fields. If a field
  appears unexpectedly, upgrade your integration to consume the richer contract
  instead of filtering it out.

## Extending the Adapter

- Add new presets by updating `zscripts/presets.py`; the adapter automatically
  reflects the change.
- Expose new commands by appending to `agents.cli_adapter.get_cli_command_specs()`.
- Re-run `export_cli_metadata()` in your automation pipeline to pick up the new
  payload.

