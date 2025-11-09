# Web Crawl Observability Surface

The crawler ships with multiple instrumentation layers (telemetry metrics,
OpenTelemetry spans, health snapshots). `helpers.web_crawl.observability`
combines them into a single HTTP interface so operators and agents can inspect
state without juggling multiple ports.

## Endpoints

| Path | Description |
| ---- | ----------- |
| `/` | Returns the latest health snapshot plus a manifest of available endpoints. |
| `/healthz` `/readyz` `/livez` | Delegated to `CrawlerHealth.wsgi_app()` for conventional probe semantics. |
| `/metrics` | Exposes Prometheus metrics when `prometheus_client` is installed; otherwise responds with a 503 and remediation hint. |
| `/events` (example) | JSON endpoint registered via `ObservabilityService.add_json_endpoint`. The CLI wires the `EventStreamExtension` here by default. |

Additional JSON endpoints can be registered at any time by calling
`ObservabilityService.add_json_endpoint("/custom", producer)`. Producers are
zero-argument callables returning JSON-serialisable objects. Endpoints are
re-evaluated on every request so extensions can surface live state even after
the server is running. Use `remove_json_endpoint` to retire surfaces when an
extension unloads or rotates ownership.

## CLI Integration

`scripts/crawl_site.py` exposes the following flags to control observability:

* `--observability-port` / `--observability-host` – serve the aggregated surface.
* `--prometheus-port` – optional legacy metrics server (you can run both).
* `--extension event_stream` – registers the in-memory event buffer so
  `/events` emits crawl lifecycle events.
* `--log-structured` – switches Python logging to JSON using
  `helpers.web_crawl.logging.configure_structured_logging` for easy ingestion.

Enable Prometheus metrics either by installing `prometheus_client` and using the
flags above or by instantiating `PrometheusCrawlerTelemetry` and passing its
registry to `prometheus_wsgi_app()` before creating `ObservabilityService`.

## Agent Playbook

Agents can safely extend the surface by:

1. Subclassing `BaseCrawlerExtension` and registering it through the CLI
   (`--extension`), an extension directory, or an entry point.
2. Surfacing extension state through JSON endpoints. For example, expose a
   queue length histogram by wiring `ObservabilityService.add_json_endpoint` to a
   lambda that returns your extension’s internal counters.
3. Updating `docs/guides/automation.md` with any new endpoints or incident procedures so the
   next operator understands the telemetry narrative.

