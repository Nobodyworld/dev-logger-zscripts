# .NET Adapter Quickstart

Parse `dotnet build` and `dotnet test` logs using the .NET adapter to capture
framework versions, test outcomes, and warnings.

**Inputs**
- Structured `dotnet` CLI logs (see `examples/dotnet/sample.log`).

**Outputs**
- Normalized JSON with TRX artifact references and deprecation warnings.

**CLI Example**

```bash
python cli.py summarize --adapter dotnet --input examples/dotnet/sample.log
```

**Programmatic Example**

```python
from pathlib import Path

from adapters import get_adapter

adapter = get_adapter("dotnet")
normalized = adapter.parse(Path("examples/dotnet/sample.log").read_text())
print(normalized.summary)
```
