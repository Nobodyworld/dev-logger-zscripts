"""Typed helpers around :func:`functools.lru_cache`."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import ParamSpec, TypeVar, cast

_P = ParamSpec("_P")
_R = TypeVar("_R")


def typed_lru_cache(maxsize: int | None = None) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Return an :func:`lru_cache` decorator that preserves type information."""

    def decorator(func: Callable[_P, _R]) -> Callable[_P, _R]:
        cached = functools.lru_cache(maxsize=maxsize)(func)
        return cast(Callable[_P, _R], cached)

    return decorator
