# Python Adapter Quickstart

The Python adapter targets structured pytest build logs. Use it when parsing
Python project CI runs or local developer builds.

**Inputs**

- Structured log text (see `examples/python/sample.log`).
- Optional metadata captured via `INFO` lines.

**Outputs**

- Normalized log JSON with test counts, errors, warnings, artifacts, and
  metadata such as code coverage.

**CLI Example**

```bash
python cli.py --adapter python parse --input examples/python/sample.log
python cli.py --adapter python summarize --input examples/python/sample.log
```

**Programmatic Example**

```python
from pathlib import Path

from adapters import get_adapter

adapter = get_adapter("python")
normalized = adapter.parse(Path("examples/python/sample.log").read_text())
print(normalized.summary)
```
