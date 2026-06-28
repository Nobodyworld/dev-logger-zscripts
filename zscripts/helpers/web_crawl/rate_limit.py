"""Rate limiting primitives for the crawler stack."""

from __future__ import annotations

import threading
import time
from typing import Callable, Protocol


class RateLimiter(Protocol):
    """Protocol describing how the crawler coordinates request pacing."""

    def delay_before_request(self, url: str) -> float:
        """Return seconds to wait before issuing a request for ``url``."""

    def register_retry_after(self, url: str, delay: float) -> None:
        """Record a server-supplied ``Retry-After`` delay for ``url``."""


class FixedWindowRateLimiter:
    """Enforce a minimum interval between fetches with optional Retry-After gates."""

    def __init__(
        self,
        *,
        min_interval: float | None = None,
        requests_per_second: float | None = None,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        """Configure the rate limiter.

        Parameters
        ----------
        min_interval:
            Minimum number of seconds that must elapse between requests. Provide
            this when you want an explicit delay between successive fetches.
        requests_per_second:
            Alternative configuration expressing the maximum sustained rate. It
            is mutually exclusive with ``min_interval`` and will be converted to
            the corresponding interval internally.
        time_fn:
            Optional monotonic clock used for testing. Defaults to
            :func:`time.monotonic`.
        """
        if (min_interval is None) == (requests_per_second is None):
            raise ValueError(
                "Provide exactly one of min_interval or requests_per_second"
            )
        if requests_per_second is not None:
            if requests_per_second <= 0:
                raise ValueError("requests_per_second must be > 0")
            min_interval = 1.0 / requests_per_second
        if min_interval is None:
            raise ValueError("min_interval must be provided")
        if min_interval <= 0:
            raise ValueError("min_interval must be > 0")
        self._interval = float(min_interval)
        self._time_fn = time_fn or time.monotonic
        self._lock = threading.Lock()
        now = self._time_fn()
        self._next_available = now
        self._gate_until = now

    def delay_before_request(self, url: str) -> float:
        """Return the delay required before the next request may fire."""
        del url
        with self._lock:
            now = self._time_fn()
            gate = max(self._gate_until, self._next_available)
            wait = max(0.0, gate - now)
            scheduled = now + wait
            self._next_available = scheduled + self._interval
            return wait

    def register_retry_after(self, url: str, delay: float) -> None:
        """Extend the internal gate in response to ``Retry-After`` headers."""
        del url
        if delay <= 0:
            return
        with self._lock:
            now = self._time_fn()
            target = now + delay
            if target > self._gate_until:
                self._gate_until = target
            if self._next_available < self._gate_until:
                self._next_available = self._gate_until


__all__ = ["FixedWindowRateLimiter", "RateLimiter"]
