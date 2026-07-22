# GitHub Actions Usage

Use the CLI directly in workflows to normalize and summarize build logs.

## Minimal Example

```yaml
name: Log Diagnostics

on:
  workflow_dispatch:
  push:
    branches: ["main"]

jobs:
  normalize-logs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.11"
      - name: Install project
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e .[dev]
      - name: Normalize sample CI log
        run: |
          python cli.py --adapter ci parse --input examples/ci/sample.log > normalized_ci_log.json
      - name: Build redacted markdown report
        run: |
          python cli.py --adapter ci report --input examples/ci/sample.log --format markdown --redact --output report.md
      - name: Upload outputs
        uses: actions/upload-artifact@v5
        with:
          name: normalized-and-report
          path: |
            normalized_ci_log.json
            report.md
```

## Notes

- Keep `--redact` enabled for CI artifacts.
- Prefer adapter-specific inputs (for example `--adapter ci`) to improve parsing quality.
- Reuse `python scripts/quality_gate.py quality` to run the hosted quality
  contract locally.
