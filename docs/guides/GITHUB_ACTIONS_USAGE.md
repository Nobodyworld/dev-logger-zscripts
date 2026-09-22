# GitHub Actions Usage

Use the maintained CLI in workflows when a deterministic log artifact is useful. Repository
Review itself is local-first and does not require GitHub Actions.

The example below follows this repository's reviewed supply-chain conventions: read-only
permissions, full-SHA GitHub-owned Actions, and non-persisted checkout credentials.

## Minimal redacted-report example

```yaml
name: Log Diagnostics

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - name: Set up Python
        uses: actions/setup-python@9191ea1a55b1e7028943ee5647bf579e1182b42d # reviewed post-v7.0.0 security commit
        with:
          python-version: "3.11"

      - name: Install Zscripts from this checkout
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e .

      - name: Build redacted JSON report
        run: |
          python cli.py --adapter ci report --input examples/ci/sample.log --format json --redact --output report.json

      - name: Build redacted Markdown report
        run: |
          python cli.py --adapter ci report --input examples/ci/sample.log --format markdown --redact --output report.md

      - name: Upload reviewed outputs
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: zscripts-reports
          path: |
            report.json
            report.md
```

## Safety notes

- Treat every artifact as independently reviewable output. Redacting one file does not sanitize
  another file produced by a different command.
- Automated redaction is defense in depth, not proof that an artifact is safe to publish.
- Use synthetic/public fixtures in examples and review generated artifacts before sharing them.
- Do not replace immutable Action SHAs with floating tags merely for readability.
- When copying this example later, re-check maintained Action provenance in
  `docs/DEPENDENCIES.md`; dependency/action upgrades are separate maintenance decisions.
