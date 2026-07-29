# Operational Workflows

The following workflows demonstrate how teams integrate zscripts into CI/CD
pipelines, local development, and observability loops.

## 1. CI Pipeline Log Capture

1. Install dependencies with `python -m pip install zscripts jsonschema` or use
   the editable install for internal repositories.
2. Run build/test jobs as usual.
3. Pipe relevant logs into zscripts:
   ```bash
   python -m zscripts collect --command pytest --output artifacts/test.log
   ```
4. Commit the normalized artefacts or upload them as pipeline artifacts for
   downstream consumption by LLM agents or auditing tools.

## 2. Local Failure Investigation

1. Reproduce the failing command locally.
2. Capture the logs with redaction enabled to prevent secrets from leaving your
   terminal history:
   ```bash
   python cli.py collect --command "pytest -k flaky::test_case" --redact
   ```
3. Summarize the logs for a quick status snapshot:
   ```bash
   python cli.py summarize --input logs.txt
   ```
4. Use `python cli.py explain` to obtain a richer narrative suitable for issue
   templates or incident reports.

## 3. Guardrail Verification

1. Run `python cli.py guardrails` to review sandbox defaults (allowed paths,
   timeout, dangerous mode state).
2. If additional directories must be allowed (e.g., `/tmp/build`), update
   `zscripts.config` or provide an override when constructing the service.
3. Re-run the command to ensure the sandbox runner honours the changes.

## 4. Adapter Discovery

1. Explore available adapters with `python cli.py examples` or filter by
   ecosystem (`--adapter python`).
2. Inspect `adapters/<name>.py` to understand capabilities and extension points.
3. Register custom adapters via configuration or contribute them upstream after
   adding tests and documentation.

## 5. Automation Embedding

1. Instantiate `ToolkitService` inside your automation script.
2. Reuse the cached service to parse logs from different commands without
   re-spawning sandbox runners (the service now caches the runner internally).
3. Serialize results or forward them to monitoring/analysis pipelines as needed.

Each workflow benefits from the improved error handling in the CLI: failures to
provide a log source now emit clear error messages and exit with status code 2
instead of uncaught tracebacks. Destination paths are validated up front as
well—the CLI creates missing directories, uses atomic writes, and reports
permission errors before any partial files are left behind.

## 6. Local Repository Review

1. Build the private frontend workspace and packaged assets:

   ```sh
   pnpm --dir workspace-ui install --frozen-lockfile
   pnpm --dir workspace-ui build
   python scripts/build_workspace_assets.py
   ```

2. Start `zscripts workspace` and open `http://127.0.0.1:8765`.
3. Select a local Python repository and begin analysis.
4. Watch bounded progress or cancel between files.
5. Review counts, parse gaps, and factual relationship totals in Overview.
6. Search/filter/sort Symbols and request a bounded source excerpt when needed.
7. Explore a focused import, package, containment, inheritance, or type graph;
   inspect cycles, incoming/outgoing edges, and source evidence.
8. Filter deterministic Findings, inspect the metric/threshold and source
   evidence, then explicitly save a reviewed, accepted, or dismissed decision.
9. Reopen the completed snapshot from the recent-repository/snapshot controls;
   completed rescans preserve review decisions and record resolved/reactivated
   lifecycle events.
10. In Compare, choose a same-repository baseline and target, then inspect
    bounded logical file/symbol/relationship/cycle/metric/finding deltas and
    compatibility warnings.
11. In Handoff, select only the needed deltas/findings, opt into individual
    notes if appropriate, preview the deterministic budgets/omissions, then
    copy, download Markdown/JSON, or save the local record for reopening.
10. In Compare, choose a same-repository baseline and target, then inspect
    bounded logical file/symbol/relationship/cycle/metric/finding deltas and
    compatibility warnings.
11. In Handoff, select only the needed deltas/findings, opt into individual
    notes if appropriate, preview the deterministic budgets/omissions, then
    copy, download Markdown/JSON, or save the local record for reopening.

No repository command, framework setup, migration, hook, plugin, or analyzed
Python module is executed. Use the experimental CLI when a deterministic JSON
contract is preferable to the UI. See
[Experimental Repository Review Workspace](repository-review.md).
