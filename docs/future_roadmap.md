# Future Roadmap

Zscripts is transitioning toward a local, deterministic **repository review
workspace**.

The authoritative plan is:

- [Zscripts 0.2 Repository Review Workspace Roadmap](product/REPOSITORY_INTELLIGENCE_ROADMAP.md)
- [Umbrella issue #76](https://github.com/Nobodyworld/dev-logger-zscripts/issues/76)

## Product workflow

```text
Scan → Explore → Review → Compare → Handoff
```

The workspace—not a generated spreadsheet or report bundle—is the product.
Analysis remains local, read-only, reviewable, and usable without an LLM.

## Current priority

The fastest safe route is:

1. finalize safety, evidence, snapshot, and review-state contracts;
2. build one end-to-end generic Python Repository Review MVP;
3. deliver a thin localhost UI with Overview and Symbols views immediately;
4. add relationships, persistent findings, comparisons, and handoffs in vertical
   slices;
5. dogfood the Python workspace before approving framework-specific enrichment or
   additional languages.

Optional exports are generated from the active view. XLSX, cloud services,
desktop packaging, multi-user collaboration, and additional language analyzers are
deferred until the local workspace demonstrates value.

## Deferred directions

The previous roadmap emphasized hosted telemetry, message queues, containers,
autoscaling, remote extension registries, Excel-first reports, framework-specific
analysis, and a dashboard delivered after the engine. Those are not current
priorities.

The legacy helper compatibility track under issues #62 and #73 remains separate
from product development and must not block the repository review roadmap.
