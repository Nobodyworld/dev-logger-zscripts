"""Web crawling helpers with optional persistence utilities."""

from .crawler import (
    CrawledPage,
    Crawler,
    FetchCallable,
    FetchResult,
    RobotsGate,
    extract_links,
    extract_text,
    normalise_link,
    same_domain,
    slugify_url,
)
from .extensions import (
    BaseCrawlerExtension,
    CrawlEvent,
    EventStreamExtension,
    ExtensionManager,
    ExtensionRegistry,
    SitemapExtension,
)
from .health import CrawlerHealth
from .logging import JsonLogFormatter, configure_structured_logging
from .observability import ObservabilityService, prometheus_wsgi_app
from .rate_limit import FixedWindowRateLimiter, RateLimiter
from .storage import DirectoryStorage, StorageBackend, StorageDocument
from .telemetry import (
    CompositeCrawlerTelemetry,
    CrawlerTelemetry,
    FetchTimer,
    NullCrawlerTelemetry,
    OpenTelemetryCrawlerTelemetry,
    PrometheusCrawlerTelemetry,
    combine_telemetry,
)

__all__ = [
    "Crawler",
    "CrawledPage",
    "FetchCallable",
    "FetchResult",
    "RobotsGate",
    "extract_links",
    "extract_text",
    "normalise_link",
    "same_domain",
    "slugify_url",
    "DirectoryStorage",
    "StorageBackend",
    "StorageDocument",
    "BaseCrawlerExtension",
    "CrawlEvent",
    "EventStreamExtension",
    "ExtensionManager",
    "ExtensionRegistry",
    "SitemapExtension",
    "CrawlerHealth",
    "ObservabilityService",
    "JsonLogFormatter",
    "configure_structured_logging",
    "CrawlerTelemetry",
    "CompositeCrawlerTelemetry",
    "FetchTimer",
    "NullCrawlerTelemetry",
    "OpenTelemetryCrawlerTelemetry",
    "PrometheusCrawlerTelemetry",
    "combine_telemetry",
    "RateLimiter",
    "FixedWindowRateLimiter",
    "prometheus_wsgi_app",
]
