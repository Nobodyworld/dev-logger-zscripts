# Future Roadmap

Zscripts is transitioning toward a local, deterministic repository intelligence,
reporting, visualization, and agent-handoff product.

The authoritative product plan is:

- [Zscripts 0.2 Repository Intelligence Roadmap](product/REPOSITORY_INTELLIGENCE_ROADMAP.md)
- [Umbrella issue #76](https://github.com/Nobodyworld/dev-logger-zscripts/issues/76)

## Current priority

The fastest safe route is:

1. build a deterministic Python/Django static-analysis engine;
2. produce useful symbol, metric, dependency, inheritance, and call evidence;
3. ship Markdown, Excel, GraphML, and agent-handoff exports;
4. add a localhost-only dashboard after the evidence contracts stabilize;
5. dogfood the Python MVP before approving additional languages.

## Deferred directions

The previous roadmap emphasized hosted telemetry, message queues, containers,
autoscaling, and remote extension registries. Those ideas are not current product
priorities. They may be reconsidered only when repository intelligence requires
them and after the local product has demonstrated value.

The core product remains local, read-only, deterministic, and usable without an
LLM. The legacy helper compatibility track under issues #62 and #73 remains
separate from this roadmap.
