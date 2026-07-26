# Guardrails and Redaction

The toolkit defaults to a locked-down sandbox to keep log collection safe:

- File access is limited to the current working directory and children.
- Subprocesses have CPU, memory, and file-size limits enforced when the host
  platform supports them.
- Environment variables are whitelisted to avoid accidental credential leaks.
- Outbound network access is not required; commands inherit only the most basic
  environment variables by default.

Use the `--dangerous` flag to bypass guardrails when you explicitly need full
host access. The CLI documents this flag prominently to discourage accidental
use.

Redaction uses regular expressions defined in `ToolkitConfig.redact_patterns`.
You can preview the effect by running:

```bash
python cli.py redact --input examples/python/sample.log
```

To customize guardrails for automation, subclass `SandboxRunner` or
preconfigure a `SandboxSettings` instance and pass it directly when using the
Python API.

## Repository Review static-analysis boundary

Repository Review reads Python source through `ast` and never imports analyzed
modules, evaluates annotations, follows dynamic imports, or runs project
commands. Import, inheritance, and type-reference relationships are static
evidence, not runtime claims. Unique internal targets can be resolved;
ambiguous candidates and unsupported or external targets remain explicit
non-edge records.

Graph queries use allowlisted modes, relationship types, resolution statuses,
and sort behavior. Depth, nodes, edges, and cycle results are bounded before
serialization. The localhost workspace retains strict same-origin CSP, embeds
no remote runtime assets, and performs no ordinary outbound request.
