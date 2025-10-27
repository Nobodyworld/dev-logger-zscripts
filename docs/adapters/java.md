# Java Adapter Quickstart

The Java adapter parses structured Maven or Gradle build logs, capturing
compiler diagnostics and CI metadata.

**Inputs**
- Structured Maven/Gradle output (see `examples/java/sample.log`).

**Outputs**
- Normalized JSON with build errors, warnings, and artifact locations.

**CLI Example**

```bash
python cli.py parse --adapter java --input examples/java/sample.log
```

**Programmatic Example**

```python
from pathlib import Path

from adapters import get_adapter

adapter = get_adapter("java")
normalized = adapter.parse(Path("examples/java/sample.log").read_text())
print(normalized.summary)
```
