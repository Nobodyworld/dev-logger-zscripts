# Future Roadmap

This roadmap highlights areas for future investment now that observability and
extensions are in place.

## Scalability

- **Multi-tenant telemetry**: promote the health server into a standalone
  process (e.g., uvicorn + FastAPI) to multiplex requests across concurrent CLI
  sessions.
- **Adapter sandbox pooling**: add a worker pool to reuse sandbox processes and
  avoid repeated initialisation overhead when parsing large batches.

## Platform Integrations

- **Remote metrics export**: add optional OpenTelemetry exporters so metrics and
  traces can be forwarded to OTLP collectors without relying solely on the
  embedded HTTP server.
- **Extension registry**: publish an index of vetted extensions, including
  metadata (version, compatibility) to allow dynamic discovery.

## Deployment

- **Containerisation**: ship a Dockerfile with baked-in telemetry defaults and a
  non-root runtime user. Couple with a compose file exposing `/metrics` for
  monitoring stacks such as Prometheus + Grafana.
- **Release automation**: integrate semantic versioning with changelog
  generation and auto-tag releases once the quality gate passes on `main`.

## Agent Safety

- **Policy engine**: extend `ExtensionContext` with a policy evaluation hook so
  automated agents can enforce allow/deny rules before executing extension
  commands.
- **Redaction packs**: allow configuration to reference named redaction packs
  stored under `docs/security/` for dynamic updates without code changes.

Each milestone should keep observability first-class: new features must emit
structured logs, telemetry, and actionable health signals.
