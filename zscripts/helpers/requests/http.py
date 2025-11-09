"""Requests helpers for resilient HTTP access."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from urllib3.util.retry import Retry

import requests
from requests.adapters import HTTPAdapter

__all__ = ["create_retrying_session", "fetch_json"]


def create_retrying_session(
    *,
    total: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: Iterable[int] | None = None,
    allowed_methods: Iterable[str] | None = None,
) -> requests.Session:
    """Return a :class:`requests.Session` configured with sane retry defaults."""
    retry = Retry(
        total=total,
        read=total,
        connect=total,
        status=total,
        backoff_factor=backoff_factor,
        status_forcelist=frozenset(status_forcelist or (500, 502, 503, 504)),
        allowed_methods=frozenset(
            allowed_methods
            or (
                "DELETE",
                "GET",
                "HEAD",
                "PATCH",
                "POST",
                "PUT",
            )
        ),
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch_json(
    url: str,
    *,
    session: requests.Session | None = None,
    timeout: float | tuple[float, float] | None = 10,
    headers: Mapping[str, str] | None = None,
) -> Any:
    """Fetch JSON from ``url`` with retries and return the decoded payload."""
    close_session = False
    if session is None:
        session = create_retrying_session(total=1, backoff_factor=0)
        close_session = True

    try:
        response = session.get(url, timeout=timeout, headers=dict(headers or {}))
        response.raise_for_status()
        return response.json()
    finally:
        if close_session:
            session.close()
