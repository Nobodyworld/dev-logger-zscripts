# Go Adapter Quickstart

Use the Go adapter to normalize `go test` output for multi-module projects.

**Inputs**

- Structured Go tooling output (see `examples/go/sample.log`).

**Outputs**

- Normalized JSON with package test counts, artifacts, and module metadata.

**CLI Example**

```bash
python cli.py --adapter go summarize --input examples/go/sample.log
```

**Programmatic Example**

```python
from pathlib import Path

from adapters import get_adapter

adapter = get_adapter("go")
normalized = adapter.parse(Path("examples/go/sample.log").read_text())
print(normalized.summary)
```
