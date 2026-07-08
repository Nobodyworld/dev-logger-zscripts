# CI Adapter Quickstart

Use the CI adapter to normalize logs from orchestrators such as GitHub Actions
or GitLab CI. It captures workflow metadata, warnings about configuration, and
error messages raised by child jobs.

**Inputs**

- Structured CI job logs (see `examples/ci/sample.log`).

**Outputs**

- Normalized JSON with error and warning summaries plus run identifiers.

**CLI Example**

```bash
python cli.py --adapter ci explain --input examples/ci/sample.log
```

**Programmatic Example**

```python
from pathlib import Path

from adapters import get_adapter

adapter = get_adapter("ci")
normalized = adapter.parse(Path("examples/ci/sample.log").read_text())
print(normalized.summary)
```
