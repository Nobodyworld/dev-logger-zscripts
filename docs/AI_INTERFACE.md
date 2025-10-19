# Agent Interface

This repository ships an agent-facing adapter that describes the CLI surface in a
machine-readable format. Use it to feed MCP/AgentKit style systems or other
assistant frameworks that need declarative command metadata.

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

## Extending the Adapter

- Add new presets by updating `zscripts/presets.py`; the adapter automatically
  reflects the change.
- Expose new commands by appending to `agents.cli_adapter.get_cli_command_specs()`.
- Re-run `export_cli_metadata()` in your automation pipeline to pick up the new
  payload.

