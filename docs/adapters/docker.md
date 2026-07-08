# Docker Adapter Quickstart

The Docker adapter normalizes `docker build` logs for container pipelines.

**Inputs**

- Structured Docker build output (see `examples/docker/sample.log`).

**Outputs**

- Normalized JSON with build errors, warnings, artifact tarballs, and registry
  metadata.

**CLI Example**

```bash
python cli.py --adapter docker parse --input examples/docker/sample.log
```

**Programmatic Example**

```python
from pathlib import Path

from adapters import get_adapter

adapter = get_adapter("docker")
normalized = adapter.parse(Path("examples/docker/sample.log").read_text())
print(normalized.summary)
```
