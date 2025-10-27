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
