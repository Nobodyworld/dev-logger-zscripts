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

Metric and finding analysis consumes the same bounded static evidence and never
executes the project. Findings use conservative candidate language where
static syntax cannot prove runtime behavior. Review notes are explicit local
user data: they are length-bounded, excluded from canonical snapshot evidence,
and never sent outbound. Review updates use allowlisted states/reasons and
optimistic versions; lifecycle reconciliation occurs only with a completed,
transactionally promoted snapshot.

Comparisons read immutable stored evidence only, reject cross-repository
snapshot pairs, and surface old-schema, version, truncation, parse-gap, and
superseded-analysis limitations. Incomplete target evidence cannot produce a
strong removal claim.

Handoffs are local, bounded, non-executable Markdown/JSON. Repository-derived
text and task objectives are escaped for Markdown/React display. Review notes
require explicit per-finding selection; clipboard access requires a click;
download media types and filenames are fixed. Handoff creation performs no
network request, filesystem picker, repository write, issue creation, or PR
creation.
