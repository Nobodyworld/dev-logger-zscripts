"""CLI utility for running the web crawler with observability hooks."""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import logging
import sys
import threading
from pathlib import Path
from typing import Any

from zscripts.helpers.web_crawl import (
    BaseCrawlerExtension,
    Crawler,
    CrawlerHealth,
    DirectoryStorage,
    EventStreamExtension,
    ExtensionRegistry,
    FixedWindowRateLimiter,
    ObservabilityService,
    OpenTelemetryCrawlerTelemetry,
    PrometheusCrawlerTelemetry,
    SitemapExtension,
    combine_telemetry,
    prometheus_wsgi_app,
    slugify_url,
)
from zscripts.helpers.web_crawl.logging import configure_structured_logging


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_url", help="Absolute URL to crawl")
    parser.add_argument("--storage-dir", type=Path, help="Directory to persist crawled text")
    parser.add_argument(
        "--storage-index",
        type=Path,
        help="Optional JSONL index file to append metadata for each page",
    )
    parser.add_argument("--max-pages", type=int, help="Optional limit on pages to crawl")
    parser.add_argument("--max-depth", type=int, help="Maximum crawl depth relative to root")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests (seconds)")
    parser.add_argument(
        "--max-requests-per-second",
        type=float,
        help="Maximum sustained request rate (enables the adaptive rate limiter)",
    )
    parser.add_argument(
        "--min-request-interval",
        type=float,
        help="Minimum seconds between requests (alternative to --max-requests-per-second)",
    )
    parser.add_argument("--no-robots", action="store_true", help="Ignore robots.txt directives")
    parser.add_argument(
        "--prometheus-port",
        type=int,
        help="Expose Prometheus metrics on the given port (uses prometheus_client)",
    )
    parser.add_argument(
        "--health-port",
        type=int,
        help="Expose /healthz and /readyz endpoints on the given port",
    )
    parser.add_argument(
        "--health-host",
        default="0.0.0.0",
        help="Host interface for the health endpoint (defaults to all interfaces)",
    )
    parser.add_argument(
        "--observability-port",
        type=int,
        help="Serve a combined health/metrics/events surface on this port",
    )
    parser.add_argument(
        "--observability-host",
        default="0.0.0.0",
        help="Host interface for the observability endpoint",
    )
    parser.add_argument(
        "--otel-service-name",
        help="Configure a basic OpenTelemetry tracer with the provided service name",
    )
    parser.add_argument(
        "--sitemap-output",
        type=Path,
        help="Write the discovered site map graph to this JSON file",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (DEBUG, INFO, WARNING, ...)",
    )
    parser.add_argument(
        "--log-structured",
        action="store_true",
        help="Emit JSON logs with crawl metadata for aggregators",
    )
    parser.add_argument(
        "--deduplicate-content",
        action="store_true",
        help="Skip persisting pages whose text matches content already seen in this crawl",
    )
    parser.add_argument(
        "--extension",
        action="append",
        dest="extensions",
        help="Register an extension by name or import path (defaults to sitemap)",
    )
    parser.add_argument(
        "--extension-dir",
        action="append",
        dest="extension_dirs",
        type=Path,
        help="Directory containing extension modules exposing EXTENSION or EXTENSION_FACTORY",
    )
    parser.add_argument(
        "--extension-entrypoint",
        action="append",
        dest="extension_entrypoints",
        help="Entry point group providing crawler extensions",
    )
    return parser.parse_args(argv)


def start_health_server(health: CrawlerHealth, host: str, port: int) -> threading.Thread:
    from wsgiref.simple_server import make_server

    server = make_server(host, port, health.wsgi_app())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def configure_tracing(service_name: str) -> OpenTelemetryCrawlerTelemetry | None:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except ImportError:  # pragma: no cover - optional dependency
        logging.getLogger(__name__).warning("OpenTelemetry SDK not installed; skipping tracing configuration")
        return None

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    return OpenTelemetryCrawlerTelemetry()


def _as_extension(candidate: Any) -> BaseCrawlerExtension:
    if isinstance(candidate, BaseCrawlerExtension):
        return candidate
    if inspect.isclass(candidate) and issubclass(candidate, BaseCrawlerExtension):
        return candidate()
    if callable(candidate):
        produced = candidate()
        if isinstance(produced, BaseCrawlerExtension):
            return produced
    raise TypeError("Object is not or did not produce a BaseCrawlerExtension")


def _resolve_extension(identifier: str, registry: ExtensionRegistry) -> BaseCrawlerExtension:
    if identifier in registry.available():
        return registry.create(identifier)
    if ":" in identifier:
        module_name, attr = identifier.split(":", 1)
    else:
        module_name, attr = identifier.rsplit(".", 1)
    module = importlib.import_module(module_name)
    target = getattr(module, attr)
    try:
        return _as_extension(target)
    except TypeError as exc:
        raise TypeError(f"{identifier} did not resolve to a crawler extension") from exc


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.log_structured:
        configure_structured_logging(args.log_level)
    else:
        logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    telemetry_collectors: list[Any] = []
    metrics_wsgi = None
    if args.prometheus_port is not None or args.observability_port is not None:
        try:
            from prometheus_client import start_http_server
        except ImportError:  # pragma: no cover - optional dependency
            logging.getLogger(__name__).warning(
                "prometheus_client not installed; skipping Prometheus telemetry"
            )
        else:
            prom = PrometheusCrawlerTelemetry()
            telemetry_collectors.append(prom)
            if args.prometheus_port is not None:
                start_http_server(args.prometheus_port, registry=prom.registry)
            if args.observability_port is not None:
                metrics_wsgi = prometheus_wsgi_app(prom.registry)

    if args.otel_service_name:
        tracer = configure_tracing(args.otel_service_name)
        if tracer is not None:
            telemetry_collectors.append(tracer)

    telemetry = combine_telemetry(*telemetry_collectors)
    health = CrawlerHealth()
    health_thread: threading.Thread | None = None
    observability: ObservabilityService | None = None
    if args.observability_port is not None:
        observability = ObservabilityService(health, metrics_app=metrics_wsgi)
    elif args.health_port is not None:
        health_thread = start_health_server(health, args.health_host, args.health_port)
        logging.info("Health endpoint listening on http://%s:%s", args.health_host, args.health_port)

    registry = ExtensionRegistry()
    registry.register("sitemap", SitemapExtension)
    registry.register("event_stream", EventStreamExtension)
    for directory in args.extension_dirs or []:
        registry.discover_directory(directory)
    for group in args.extension_entrypoints or []:
        registry.discover_entry_points(group)

    extension_ids = args.extensions or ["sitemap"]
    extensions: list[BaseCrawlerExtension] = []
    event_stream: EventStreamExtension | None = None
    for identifier in extension_ids:
        extension = _resolve_extension(identifier, registry)
        extensions.append(extension)
        if isinstance(extension, EventStreamExtension):
            event_stream = extension

    if observability is not None:
        if event_stream is None:
            event_stream = EventStreamExtension()
            extensions.append(event_stream)
        observability.add_json_endpoint("/events", event_stream.snapshot)
        observability.start(args.observability_host, args.observability_port)
        logging.info(
            "Observability endpoint listening on http://%s:%s",
            args.observability_host,
            args.observability_port,
        )

    storage_backend = None
    storage_dir = args.storage_dir
    if args.storage_index is not None:
        if args.storage_dir is None:
            raise SystemExit("--storage-index requires --storage-dir to be set")
        storage_backend = DirectoryStorage(
            args.storage_dir,
            slugify=slugify_url,
            index_path=args.storage_index,
        )
        storage_dir = None

    if args.max_requests_per_second is not None and args.min_request_interval is not None:
        raise SystemExit("Choose either --max-requests-per-second or --min-request-interval")

    rate_limiter = None
    if args.max_requests_per_second is not None:
        rate_limiter = FixedWindowRateLimiter(requests_per_second=args.max_requests_per_second)
        logging.info("Applying rate limit: ≤ %.2f requests/s", args.max_requests_per_second)
    elif args.min_request_interval is not None:
        rate_limiter = FixedWindowRateLimiter(min_interval=args.min_request_interval)
        logging.info("Applying rate limit: ≥ %.2fs between requests", args.min_request_interval)

    crawler = Crawler(
        args.root_url,
        storage_dir=storage_dir,
        storage=storage_backend,
        delay=args.delay,
        respect_robots=not args.no_robots,
        max_depth=args.max_depth,
        telemetry=telemetry,
        extensions=extensions,
        health=health,
        deduplicate_content=args.deduplicate_content,
        rate_limiter=rate_limiter,
    )

    pages = crawler.crawl(max_pages=args.max_pages)

    logging.info("Crawled %s pages", len(pages))
    logging.debug("Health snapshot: %s", json.dumps(health.snapshot(), indent=2))

    for extension in extensions:
        if isinstance(extension, SitemapExtension) and args.sitemap_output:
            args.sitemap_output.write_text(json.dumps(extension.graph, indent=2), encoding="utf-8")
            logging.info("Site map written to %s", args.sitemap_output)
        elif isinstance(extension, SitemapExtension) and args.sitemap_output is None:
            print(json.dumps(extension.graph, indent=2))

    if health_thread is not None:
        logging.info("Health thread is running in the background; press Ctrl+C to exit.")

    if observability is not None:
        logging.info("Observability server running in the background; press Ctrl+C to exit.")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main(sys.argv[1:]))
