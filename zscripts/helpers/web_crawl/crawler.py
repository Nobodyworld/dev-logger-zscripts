"""High level crawling utilities with optional persistence.

The original crawler helpers in this repository were tightly coupled to
``BeautifulSoup`` and eagerly performed network requests at import time.
This refactor extracts the crawler into a reusable module that keeps side
effects at the boundaries and provides clean abstractions for fetching, text
extraction, and storage.

The implementation now tracks per-page metadata (content hashes, crawl depth,
timestamps) and exposes an injectable storage protocol so crawled artefacts can
be persisted to custom backends or the built-in directory writer. A
``deduplicate_content`` flag skips writing pages whose extracted text matches
prior responses within the same crawl run.
"""

from __future__ import annotations

import hashlib
import logging
import random
import re
import time
import urllib.error
import urllib.request
import urllib.robotparser
from collections import deque
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from importlib import util as importlib_util
from pathlib import Path
from typing import (
    Any,
    Callable,
    Iterable,
    MutableSet,
    NamedTuple,
    Optional,
    Protocol,
    cast,
)
from urllib.parse import urljoin, urlparse

from .extensions import BaseCrawlerExtension, CrawlEvent, ExtensionManager
from .health import CrawlerHealth
from .rate_limit import RateLimiter
from .storage import DirectoryStorage, StorageBackend, StorageDocument
from .telemetry import CrawlerTelemetry, FetchTimer, NullCrawlerTelemetry


class _BeautifulSoupProtocol(Protocol):
    """Subset of the BeautifulSoup API required by the crawler."""

    def get_text(self, separator: str = ..., strip: bool = ...) -> str:
        """Return normalised text extracted from the parsed document."""


BeautifulSoupFactory = Callable[..., _BeautifulSoupProtocol]

if importlib_util.find_spec("bs4") is not None:
    from bs4 import BeautifulSoup as _BeautifulSoupClass

    BeautifulSoup: BeautifulSoupFactory | None = cast(
        BeautifulSoupFactory, _BeautifulSoupClass
    )
else:  # pragma: no cover - optional dependency path
    BeautifulSoup = None

logger = logging.getLogger(__name__)

# Pre-compiled regex for matching absolute HTTP/HTTPS URLs.
HTTP_URL_PATTERN = re.compile(r"^https?://.+", re.IGNORECASE)

# Regex pattern to scrub a URL path into a filesystem-safe slug.
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9_.-]+")

DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; DevScriptCrawler/1.0)"
DEFAULT_TIMEOUT = 20.0
DEFAULT_RETRY_BASE_DELAY = 1.0
DEFAULT_RETRY_BACKOFF = 2.0
DEFAULT_RETRY_JITTER = 0.3


def _retry_after_delay(value: str | None, *, now: float | None = None) -> float | None:
    """Convert a ``Retry-After`` header value to a delay in seconds."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            target = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        reference = now if now is not None else time.time()
        delay = target.timestamp() - reference
        return float(delay) if delay > 0 else 0.0
    else:
        if seconds < 0:
            return 0.0
        return float(seconds)


class HyperlinkParser(HTMLParser):
    """HTML parser that collects hyperlink href attributes."""

    def __init__(self) -> None:
        """Initialise the hyperlink collector."""
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:  # noqa: D401
        """Collect the ``href`` attribute when parsing anchor tags."""
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if href:
            self.links.append(href)


class PlainTextExtractor(HTMLParser):
    """Simple HTML parser that extracts visible text content."""

    def __init__(self) -> None:
        """Initialise parser buffers."""
        super().__init__()
        self._buffer: list[str] = []
        self._skip_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._skip_stack and self._skip_stack[-1] == tag:
            self._skip_stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._skip_stack:
            text = data.strip()
            if text:
                self._buffer.append(text)

    def get_text(self) -> str:
        return "\n".join(self._buffer)


class FetchResult(NamedTuple):
    """Return value for page fetch operations."""

    url: str
    content: str
    content_type: str | None


FetchCallable = Callable[[str], FetchResult]
SleepCallable = Callable[[float], None]
TextExtractor = Callable[[str], str]


def default_fetch(
    url: str, *, user_agent: str, timeout: float = DEFAULT_TIMEOUT
) -> FetchResult:
    """Fetch a URL using :mod:`urllib`.

    Parameters
    ----------
    url:
        Target URL to fetch.
    user_agent:
        User agent header passed to the remote server.
    timeout:
        Timeout in seconds for the HTTP request.

    Returns:
    -------
    FetchResult
        Normalised URL, decoded HTML content, and the response content type.
    """
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type")
        encoding = response.headers.get_content_charset() or "utf-8"
        body = response.read()
    return FetchResult(final_url, body.decode(encoding, errors="replace"), content_type)


def extract_links(html: str) -> list[str]:
    """Extract raw href values from HTML content."""
    parser = HyperlinkParser()
    parser.feed(html)
    return parser.links


def normalise_link(base_url: str, href: str) -> str | None:
    """Normalise a hyperlink relative to ``base_url``.

    Non-http(s) links, in-document references, and mailto links are ignored.
    Returned URLs are stripped of fragments and trailing slashes for stable
    comparisons.
    """
    if not href:
        return None
    href = href.strip()
    if href.startswith("#") or href.startswith("mailto:"):
        return None
    absolute = urljoin(base_url, href)
    if not HTTP_URL_PATTERN.match(absolute):
        return None
    parsed = urlparse(absolute)
    cleaned = parsed._replace(fragment="").geturl()
    if cleaned.endswith("/"):
        cleaned = cleaned[:-1]
    return cleaned


def same_domain(url: str, domain: str) -> bool:
    """Return ``True`` when ``url`` belongs to ``domain``."""
    return urlparse(url).netloc.lower() == domain.lower()


def slugify_url(url: str) -> str:
    """Create a filesystem-friendly slug for ``url``."""
    parsed = urlparse(url)
    candidate = parsed.path.rsplit("/", 1)[-1] or "index"
    candidate = SAFE_FILENAME.sub("_", candidate)[:80] or "page"
    digest = hashlib.blake2s(url.encode("utf-8"), digest_size=8).hexdigest()
    return f"{candidate}-{digest}"


def extract_text(html: str) -> str:
    """Extract visible text from HTML using BeautifulSoup when available."""
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n", strip=True)

    parser = PlainTextExtractor()
    parser.feed(html)
    return parser.get_text()


@dataclass(slots=True)
class CrawledPage:
    """Container holding the result of a single crawled page."""

    url: str
    text: str
    storage_path: Path | None
    content_hash: str
    fetched_at: float
    content_type: str | None
    metadata: dict[str, Any]


class RobotsGate:
    """Lazy :mod:`robots.txt` reader that caches parser instances per domain."""

    def __init__(self, user_agent: str, enabled: bool) -> None:
        """Configure the robots.txt gatekeeper."""
        self.user_agent = user_agent
        self.enabled = enabled
        self._cache: dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}

    def allows(self, url: str) -> bool:
        """Return ``True`` when ``url`` is allowed to be crawled."""
        if not self.enabled:
            return True
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain not in self._cache:
            robots_parser = urllib.robotparser.RobotFileParser()
            scheme = parsed.scheme or "https"
            robots_url = urljoin(f"{scheme}://{domain}", "/robots.txt")
            try:
                robots_parser.set_url(robots_url)
                robots_parser.read()
            except (
                Exception
            ) as exc:  # pragma: no cover - network failures depend on environment
                logger.debug("Failed to read robots.txt for %s: %s", domain, exc)
                self._cache[domain] = None
            else:
                self._cache[domain] = robots_parser
        cached_parser = self._cache.get(domain)
        if cached_parser is None:
            return True
        return cached_parser.can_fetch(self.user_agent, url)


class Crawler:
    """Breadth-first crawler that extracts text content from a website."""

    def __init__(
        self,
        root_url: str,
        *,
        fetch: FetchCallable | None = None,
        storage_dir: Path | None = None,
        storage: StorageBackend | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        delay: float = 1.0,
        respect_robots: bool = True,
        sleep: SleepCallable | None = None,
        text_extractor: TextExtractor | None = None,
        max_depth: int | None = None,
        max_retries: int = 2,
        retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
        retry_jitter: float = DEFAULT_RETRY_JITTER,
        crawl_id: str | None = None,
        telemetry: CrawlerTelemetry | None = None,
        extensions: Iterable[BaseCrawlerExtension] | None = None,
        health: CrawlerHealth | None = None,
        deduplicate_content: bool = False,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """Configure crawler dependencies and behaviour."""
        if not HTTP_URL_PATTERN.match(root_url):
            raise ValueError(f"root_url must be an absolute HTTP(S) URL: {root_url!r}")
        self.root_url = root_url.rstrip("/")
        self.domain = urlparse(self.root_url).netloc
        self.fetch = fetch or (lambda url: default_fetch(url, user_agent=user_agent))
        if storage_dir is not None and storage is not None:
            raise ValueError("Provide either storage_dir or storage, not both")
        self.storage_dir = Path(storage_dir).expanduser() if storage_dir else None
        if self.storage_dir is not None:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        if storage is not None:
            self.storage: StorageBackend | None = storage
        elif self.storage_dir is not None:
            self.storage = DirectoryStorage(self.storage_dir, slugify=slugify_url)
        else:
            self.storage = None
        self.user_agent = user_agent
        self.delay = delay
        self.sleep = sleep or time.sleep
        self.text_extractor = text_extractor or extract_text
        self.max_depth = max_depth
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if retry_base_delay < 0:
            raise ValueError("retry_base_delay must be >= 0")
        if retry_backoff < 1:
            raise ValueError("retry_backoff must be >= 1")
        if retry_jitter < 0:
            raise ValueError("retry_jitter must be >= 0")
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.retry_backoff = retry_backoff
        self.retry_jitter = retry_jitter
        self.crawl_id = (
            crawl_id
            or hashlib.blake2s(self.root_url.encode("utf-8"), digest_size=8).hexdigest()
        )
        self._log_extra = {"crawl_id": self.crawl_id, "root_url": self.root_url}
        self.telemetry = telemetry or NullCrawlerTelemetry()
        self.extensions = ExtensionManager(extensions or [])
        self.health = health or CrawlerHealth()
        self.robots = RobotsGate(user_agent=user_agent, enabled=respect_robots)
        self.deduplicate_content = deduplicate_content
        self._seen_hashes: set[str] = set()
        self.rate_limiter = rate_limiter

    def crawl(self, *, max_pages: int | None = None) -> list[CrawledPage]:
        """Crawl starting from ``root_url``.

        Parameters
        ----------
        max_pages:
            Optional limit on how many pages to crawl. When ``None`` the crawler
            proceeds until the queue is exhausted.

        Returns:
        -------
        list[CrawledPage]
            A list of crawled page objects containing the harvested text and
            optional storage path.
        """
        queue: deque[tuple[str, int]] = deque([(self.root_url, 0)])
        seen: MutableSet[str] = set()
        results: list[CrawledPage] = []
        success = False

        self.health.report_start(self.root_url)

        try:
            while queue:
                self.telemetry.record_queue_depth(len(queue))
                self.health.record_queue_depth(len(queue))

                url, depth = queue.popleft()
                event = CrawlEvent(url=url, depth=depth)

                if url in seen:
                    self.extensions.on_skip(event, "duplicate")
                    continue
                seen.add(url)

                if not self.robots.allows(url):
                    logger.debug(
                        "Skipping disallowed URL %s", url, extra=self._log_extra
                    )
                    self.extensions.on_skip(event, "robots")
                    self.health.record_skip(url, "robots")
                    continue

                self._apply_rate_limit(url)
                self.extensions.before_fetch(event)
                response = self._fetch_with_retries(event, skip_initial_rate_limit=True)
                if response is None:
                    continue

                content_type = response.content_type or "text/html"
                if "html" not in content_type:
                    logger.debug(
                        "Skipping non-HTML content from %s (%s)",
                        url,
                        content_type,
                        extra=self._log_extra,
                    )
                    reason = f"content-type:{content_type}"
                    self.extensions.on_skip(event, reason)
                    self.health.record_skip(response.url, reason)
                    continue

                text = self.text_extractor(response.content)
                content_hash = hashlib.blake2s(
                    text.encode("utf-8"), digest_size=16
                ).hexdigest()
                if self.deduplicate_content and content_hash in self._seen_hashes:
                    reason = "duplicate-content"
                    logger.debug(
                        "Skipping duplicate content for %s",
                        response.url,
                        extra=self._log_extra,
                    )
                    self.extensions.on_skip(event, reason)
                    self.health.record_skip(response.url, reason)
                    continue
                self._seen_hashes.add(content_hash)
                fetched_at = time.time()
                metadata = {
                    "crawl_id": self.crawl_id,
                    "root_url": self.root_url,
                    "depth": depth,
                }
                storage_path = self._persist(
                    response.url,
                    text,
                    content_hash,
                    fetched_at,
                    content_type,
                    metadata,
                )
                page = CrawledPage(
                    url=response.url,
                    text=text,
                    storage_path=storage_path,
                    content_hash=content_hash,
                    fetched_at=fetched_at,
                    content_type=content_type,
                    metadata=metadata,
                )
                results.append(page)

                text_bytes = len(text.encode("utf-8"))
                self.telemetry.record_page_crawled(response.url, text_bytes)
                self.health.record_page(response.url)
                self.extensions.on_page_crawled(event, page)

                if max_pages is not None and len(results) >= max_pages:
                    success = True
                    break
                if self.max_depth is not None and depth >= self.max_depth:
                    continue

                discovered: list[str] = []
                for href in extract_links(response.content):
                    normalised = normalise_link(response.url, href)
                    if normalised is None:
                        continue
                    next_event = CrawlEvent(url=normalised, depth=depth + 1)
                    if not same_domain(normalised, self.domain):
                        self.extensions.on_skip(next_event, "external-domain")
                        self.health.record_skip(normalised, "external-domain")
                        continue
                    if not self.robots.allows(normalised):
                        self.extensions.on_skip(next_event, "robots")
                        self.health.record_skip(normalised, "robots")
                        continue
                    discovered.append(normalised)
                    if normalised not in seen:
                        queue.append((normalised, depth + 1))

                if discovered:
                    self.extensions.on_links_discovered(event, discovered)

                if self.delay > 0:
                    self.sleep(self.delay)

            self.telemetry.record_queue_depth(0)
            self.health.record_queue_depth(0)
            if not success:
                success = True
        finally:
            if self.storage is not None:
                try:
                    self.storage.close()
                except Exception as exc:  # pragma: no cover - defensive safety
                    logger.debug("Storage close failed: %s", exc, extra=self._log_extra)
            self.health.report_finish(success)
            self.extensions.on_finish(results, success)

        return results

    def _apply_rate_limit(self, url: str) -> None:
        """Apply rate limiting before issuing a network request."""
        if self.rate_limiter is None:
            return
        wait = self.rate_limiter.delay_before_request(url)
        if wait > 0:
            logger.debug(
                "Rate limiter delaying fetch of %s by %.2fs",
                url,
                wait,
                extra=self._log_extra,
            )
            self.sleep(wait)

    def _fetch_with_retries(
        self, event: CrawlEvent, *, skip_initial_rate_limit: bool = False
    ) -> FetchResult | None:
        """Fetch ``url`` applying retry with exponential backoff and jitter."""
        attempt = 0
        delay = self.retry_base_delay or 0.0
        skip_rate_limit = skip_initial_rate_limit
        while True:
            if not skip_rate_limit:
                self._apply_rate_limit(event.url)
            else:
                skip_rate_limit = False
            try:
                with FetchTimer(self.telemetry, event.url):
                    result = self.fetch(event.url)
            except Exception as exc:
                tries = attempt + 1
                retry_after_delay = None
                if isinstance(exc, urllib.error.HTTPError):
                    header_value = getattr(exc, "headers", None)
                    retry_after_delay = _retry_after_delay(
                        header_value.get("Retry-After") if header_value else None,
                        now=time.time(),
                    )
                    if retry_after_delay is not None and self.rate_limiter is not None:
                        self.rate_limiter.register_retry_after(
                            event.url, retry_after_delay
                        )
                        logger.debug(
                            "Honouring Retry-After %.2fs for %s",
                            retry_after_delay,
                            event.url,
                            extra=self._log_extra,
                        )
                logger.warning(
                    "Fetch attempt %s for %s failed: %s",
                    tries,
                    event.url,
                    exc,
                    extra=self._log_extra,
                )
                self.extensions.on_retry(event, tries, exc)
                if attempt >= self.max_retries:
                    logger.error(
                        "Giving up on %s after %s attempts",
                        event.url,
                        tries,
                        extra=self._log_extra,
                    )
                    self.extensions.on_give_up(event, tries, exc)
                    self.health.record_error(event.url, exc)
                    return None
                sleep_for = delay + (
                    random.uniform(0, self.retry_jitter)  # nosec B311
                    if self.retry_jitter
                    else 0.0  # nosec B311
                )
                if retry_after_delay is not None:
                    sleep_for = max(sleep_for, retry_after_delay)
                if sleep_for > 0:
                    logger.debug(
                        "Sleeping %.2fs before retrying %s",
                        sleep_for,
                        event.url,
                        extra=self._log_extra,
                    )
                    self.sleep(sleep_for)
                delay = (delay or 1.0) * self.retry_backoff
                attempt += 1
            else:
                self.extensions.after_fetch(event, result)
                return result

    def _persist(
        self,
        url: str,
        text: str,
        content_hash: str,
        fetched_at: float,
        content_type: str | None,
        metadata: dict[str, Any],
    ) -> Path | None:
        if self.storage is None:
            return None
        document = StorageDocument(
            url=url,
            text=text,
            content_type=content_type,
            content_hash=content_hash,
            fetched_at=fetched_at,
            metadata=metadata,
        )
        try:
            return self.storage.persist(document)
        except OSError as exc:
            logger.error("Failed to persist %s: %s", url, exc, extra=self._log_extra)
            self.telemetry.record_error(url, exc)
            self.health.record_error(url, exc)
            return None
        except Exception as exc:  # pragma: no cover - defensive guardrail
            logger.exception(
                "Unexpected storage failure for %s", url, extra=self._log_extra
            )
            self.telemetry.record_error(url, exc)
            self.health.record_error(url, exc)
            return None


__all__ = [
    "Crawler",
    "CrawledPage",
    "FetchResult",
    "FetchCallable",
    "HyperlinkParser",
    "RobotsGate",
    "extract_links",
    "extract_text",
    "normalise_link",
    "same_domain",
    "slugify_url",
]
