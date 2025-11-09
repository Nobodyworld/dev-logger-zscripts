"""Starter template for implementing a crawler extension."""

from __future__ import annotations

from helpers.web_crawl import BaseCrawlerExtension, CrawledPage, CrawlEvent, FetchResult


class SampleExtension(BaseCrawlerExtension):
    """Document the behaviour of your extension here."""

    name = "sample"

    def before_fetch(self, event: CrawlEvent) -> None:
        """Inspect the next ``event`` before the crawler performs the HTTP request."""
        # Optional: inspect event.url or event.depth before the crawler fetches it.
        pass

    def after_fetch(self, event: CrawlEvent, result: FetchResult) -> None:
        """React to the HTTP response represented by ``result``."""
        # Optional: examine the HTTP response and extracted metadata.
        pass

    def on_page_crawled(self, event: CrawlEvent, page: CrawledPage) -> None:
        """Handle the parsed ``page`` after the crawler extracts its content."""
        # Optional: persist structured metadata after text extraction. The
        # `page` object now exposes `content_hash`, `fetched_at`, `content_type`,
        # and a `metadata` dictionary mirroring the JSON sidecar written by the
        # crawler.
        pass


def EXTENSION_FACTORY() -> SampleExtension:
    """Factory used by `ExtensionRegistry.discover_directory`."""

    return SampleExtension()

