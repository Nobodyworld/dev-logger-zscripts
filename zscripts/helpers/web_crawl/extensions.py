"""Extension interfaces for :mod:`helpers.web_crawl`.

The crawler now exposes an event-driven surface that allows independent
modules to observe or influence the crawl lifecycle without modifying the
core implementation. Extensions are small Python objects with optional hook
methods that are invoked by :class:`~helpers.web_crawl.crawler.Crawler` at
deterministic points.

The contract intentionally mirrors the parameters passed to the crawler so
that new integrations (e.g. persistence adapters, analytics sinks, alerting
hooks) can be implemented without touching the crawler itself. The provided
``SitemapExtension`` doubles as a reference implementation and a handy tool
for quickly visualising link graphs while developing or debugging a crawl.
"""

from __future__ import annotations

import importlib.util
import inspect
import time
from collections import deque
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, List, Sequence, cast

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from .crawler import CrawledPage, FetchResult


@dataclass(slots=True)
class CrawlEvent:
    """Metadata describing the current crawl state."""

    url: str
    depth: int


class BaseCrawlerExtension:
    """Base class for crawler extensions.

    Sub-classes can override any of the lifecycle hooks; the default
    implementation performs no action. Hooks are intentionally typed to
    accept both :class:`FetchResult` and :class:`CrawledPage` instances so the
    extension can reason about both raw responses and extracted text.
    """

    name = "base"

    def before_fetch(self, event: CrawlEvent) -> None:  # pragma: no cover - default noop
        """Called immediately before a URL is fetched."""

    def after_fetch(
        self, event: CrawlEvent, result: "FetchResult"
    ) -> None:  # pragma: no cover - default noop
        """Called after a successful fetch before link extraction."""

    def on_retry(
        self, event: CrawlEvent, attempt: int, exc: Exception
    ) -> None:  # pragma: no cover - default noop
        """Called when a fetch attempt fails but the crawler will retry."""

    def on_give_up(
        self, event: CrawlEvent, attempts: int, exc: Exception
    ) -> None:  # pragma: no cover - default noop
        """Called when all retry attempts failed for a URL."""

    def on_skip(self, event: CrawlEvent, reason: str) -> None:  # pragma: no cover - default noop
        """Called when a URL is skipped before fetching (e.g. robots)."""

    def on_links_discovered(
        self, event: CrawlEvent, links: Sequence[str]
    ) -> None:  # pragma: no cover - default noop
        """Called with the normalised links extracted from a page."""

    def on_page_crawled(
        self, event: CrawlEvent, page: "CrawledPage"
    ) -> None:  # pragma: no cover - default noop
        """Called when a page has been successfully crawled and persisted."""

    def on_finish(
        self, pages: Sequence["CrawledPage"], success: bool
    ) -> None:  # pragma: no cover - default noop
        """Called once the crawl loop exits."""


class ExtensionManager:
    """Invoke a sequence of extensions for each lifecycle event."""

    def __init__(self, extensions: Iterable[BaseCrawlerExtension] | None = None) -> None:
        """Initialise the manager with an optional iterable of extensions."""
        self._extensions: List[BaseCrawlerExtension] = list(extensions or [])

    def add(self, extension: BaseCrawlerExtension) -> None:
        """Register an additional extension at runtime."""
        self._extensions.append(extension)

    def before_fetch(self, event: CrawlEvent) -> None:
        """Dispatch the ``before_fetch`` hook to all extensions."""
        for ext in self._extensions:
            ext.before_fetch(event)

    def after_fetch(self, event: CrawlEvent, result: "FetchResult") -> None:
        """Dispatch the ``after_fetch`` hook to all extensions."""
        for ext in self._extensions:
            ext.after_fetch(event, result)

    def on_retry(self, event: CrawlEvent, attempt: int, exc: Exception) -> None:
        """Dispatch retry notifications to extensions."""
        for ext in self._extensions:
            ext.on_retry(event, attempt, exc)

    def on_give_up(self, event: CrawlEvent, attempts: int, exc: Exception) -> None:
        """Inform extensions when a URL is abandoned."""
        for ext in self._extensions:
            ext.on_give_up(event, attempts, exc)

    def on_skip(self, event: CrawlEvent, reason: str) -> None:
        """Notify extensions when the crawler skips a URL."""
        for ext in self._extensions:
            ext.on_skip(event, reason)

    def on_links_discovered(self, event: CrawlEvent, links: Sequence[str]) -> None:
        """Provide the list of discovered links to all extensions."""
        for ext in self._extensions:
            ext.on_links_discovered(event, links)

    def on_page_crawled(self, event: CrawlEvent, page: "CrawledPage") -> None:
        """Notify extensions that a page has been crawled."""
        for ext in self._extensions:
            ext.on_page_crawled(event, page)

    def on_finish(self, pages: Sequence["CrawledPage"], success: bool) -> None:
        """Call ``on_finish`` on all extensions when the crawl completes."""
        for ext in self._extensions:
            ext.on_finish(pages, success)


class SitemapExtension(BaseCrawlerExtension):
    """Collect a site map that maps each crawled URL to its outbound links."""

    name = "sitemap"

    def __init__(self) -> None:
        """Initialise the in-memory site map graph."""
        self.graph: dict[str, list[str]] = {}

    def on_links_discovered(self, event: CrawlEvent, links: Sequence[str]) -> None:
        """Capture the outbound links for ``event.url``."""
        self.graph[event.url] = sorted(dict.fromkeys(links))

    def on_finish(self, pages: Sequence["CrawledPage"], success: bool) -> None:
        """Normalise ordering after the crawl completes."""
        # Preserve deterministic ordering for reproducibility in tests and logs.
        self.graph = {url: self.graph.get(url, []) for url in sorted(self.graph)}


@dataclass(slots=True)
class StreamEvent:
    """Structured representation of events emitted by ``EventStreamExtension``."""

    timestamp: float
    name: str
    payload: dict[str, object]


class EventStreamExtension(BaseCrawlerExtension):
    """Capture crawl lifecycle events into an in-memory ring buffer."""

    name = "event_stream"

    def __init__(self, max_events: int = 200) -> None:
        """Initialise the event buffer with a bounded deque."""
        self._events: deque[StreamEvent] = deque(maxlen=max_events)

    def _record(self, name: str, **payload: object) -> None:
        """Append a new event with the provided payload."""
        self._events.append(StreamEvent(time.time(), name, payload))

    def before_fetch(self, event: CrawlEvent) -> None:
        """Record the next URL scheduled for fetching."""
        self._record("before_fetch", url=event.url, depth=event.depth)

    def after_fetch(self, event: CrawlEvent, result: "FetchResult") -> None:
        """Capture the size of the fetched payload."""
        self._record("after_fetch", url=event.url, bytes=len(result.content))

    def on_retry(self, event: CrawlEvent, attempt: int, exc: Exception) -> None:
        """Track retry attempts and the exception raised."""
        self._record("retry", url=event.url, attempt=attempt, error=str(exc))

    def on_give_up(self, event: CrawlEvent, attempts: int, exc: Exception) -> None:
        """Record terminal failures once retries are exhausted."""
        self._record("give_up", url=event.url, attempts=attempts, error=str(exc))

    def on_skip(self, event: CrawlEvent, reason: str) -> None:
        """Log skipped URLs along with the reason."""
        self._record("skip", url=event.url, reason=reason)

    def on_links_discovered(self, event: CrawlEvent, links: Sequence[str]) -> None:
        """Count the links discovered for ``event.url``."""
        self._record("links", url=event.url, discovered=len(links))

    def on_page_crawled(self, event: CrawlEvent, page: "CrawledPage") -> None:
        """Record the storage location of successfully crawled pages."""
        self._record("page", url=event.url, storage=str(page.storage_path) if page.storage_path else None)

    def on_finish(self, pages: Sequence["CrawledPage"], success: bool) -> None:
        """Emit a final summary once the crawl terminates."""
        self._record("finish", pages=len(pages), success=success)

    def snapshot(self) -> list[dict[str, object]]:
        """Return the buffered events as JSON serialisable dictionaries."""
        return [{"timestamp": evt.timestamp, "event": evt.name, **evt.payload} for evt in list(self._events)]


ExtensionFactory = Callable[[], BaseCrawlerExtension]


def _wrap_instance(instance: BaseCrawlerExtension) -> ExtensionFactory:
    """Create a factory that always returns ``instance``."""

    def factory() -> BaseCrawlerExtension:
        return instance

    return factory


class ExtensionRegistry:
    """Registry + discovery helpers for crawler extensions."""

    def __init__(self) -> None:
        """Initialise the internal registry mapping."""
        self._factories: dict[str, ExtensionFactory] = {}

    def register(self, name: str, factory: ExtensionFactory) -> None:
        """Register a new extension factory under ``name``."""
        self._factories[name] = factory

    def create(self, name: str) -> BaseCrawlerExtension:
        """Instantiate the extension referenced by ``name``."""
        try:
            factory = self._factories[name]
        except KeyError as exc:
            raise KeyError(f"Unknown extension: {name}") from exc
        return factory()

    def available(self) -> list[str]:
        """Return the sorted list of registered extension names."""
        return sorted(self._factories)

    # -- Discovery helpers -------------------------------------------------
    def discover_entry_points(self, group: str) -> None:
        """Load entry point factories registered under ``group``."""
        for entry_point in metadata.entry_points().select(group=group):
            factory_obj = entry_point.load()
            if inspect.isclass(factory_obj) and issubclass(factory_obj, BaseCrawlerExtension):
                self.register(entry_point.name, factory_obj)
            elif isinstance(factory_obj, BaseCrawlerExtension):
                self.register(entry_point.name, _wrap_instance(factory_obj))
            elif callable(factory_obj):
                self.register(entry_point.name, cast(ExtensionFactory, factory_obj))
            else:  # pragma: no cover - defensive branch
                message = "Entry point '%s' must provide an extension factory or instance" % entry_point.name
                raise TypeError(message)

    def discover_directory(self, path: Path) -> None:
        """Import Python files in ``path`` looking for ``EXTENSION_FACTORY`` hooks."""
        if not path.exists():
            return
        for file in sorted(path.glob("*.py")):
            spec = importlib.util.spec_from_file_location(file.stem, file)
            if spec is None or spec.loader is None:  # pragma: no cover - importlib edge case
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            factory = getattr(module, "EXTENSION_FACTORY", None)
            extension = getattr(module, "EXTENSION", None)
            if callable(factory):
                self.register(file.stem, cast(ExtensionFactory, factory))
            elif isinstance(extension, BaseCrawlerExtension):
                self.register(file.stem, _wrap_instance(extension))


__all__ = [
    "BaseCrawlerExtension",
    "CrawlEvent",
    "EventStreamExtension",
    "ExtensionManager",
    "ExtensionRegistry",
    "SitemapExtension",
]
