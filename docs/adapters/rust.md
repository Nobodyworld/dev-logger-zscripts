# Rust Adapter Quickstart

The Rust adapter consumes structured `cargo test` output and surfaces warnings
and build metadata.

**Inputs**
- Structured Cargo logs (see `examples/rust/sample.log`).

**Outputs**
- Normalized JSON with artifact directories, warnings, and toolchain info.

**CLI Example**

```bash
python cli.py summarize --adapter rust --input examples/rust/sample.log
```

**Programmatic Example**

```python
from pathlib import Path

from adapters import get_adapter

adapter = get_adapter("rust")
normalized = adapter.parse(Path("examples/rust/sample.log").read_text())
print(normalized.summary)
```
