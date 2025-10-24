# JavaScript and TypeScript Adapter Quickstart

The JavaScript adapter is tuned for Jest logs and supports TypeScript projects.

**Inputs**
- Structured log text, typically collected from `npm test` or `yarn test`.

**Outputs**
- Normalized JSON capturing suite status, warnings, coverage artifacts, and
  metadata such as Node.js version and package manager.

**CLI Example**

```bash
python cli.py summarize --adapter javascript --input examples/javascript/sample.log
```

**Programmatic Example**

```python
from pathlib import Path

from adapters import get_adapter

adapter = get_adapter("javascript")
normalized = adapter.parse(Path("examples/javascript/sample.log").read_text())
print(normalized.summary)
```
