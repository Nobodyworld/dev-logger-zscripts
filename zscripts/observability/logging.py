"""Structured logging helpers with correlation-ID support."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import cast

_CORRELATION_ID: ContextVar[str | None] = ContextVar("zscripts_correlation_id", default=None)


class _CorrelationFilter(logging.Filter):
    """Inject the current correlation ID into log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 - interface requirement
        record_dict = cast(dict[str, object], record.__dict__)
        record_dict["correlation_id"] = _CORRELATION_ID.get() or "-"
        return True


class _TextFormatter(logging.Formatter):
    """Text formatter that appends correlation IDs when present."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - override
        message = super().format(record)
        correlation = cast(str, getattr(record, "correlation_id", "-"))
        if correlation and correlation != "-":
            return f"{message} [cid={correlation}]"
        return message


class _JsonFormatter(logging.Formatter):
    """Render log records as structured JSON objects."""

    _RESERVED = {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
    }

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - override
        message = super().format(record)
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }
        correlation = cast(str, getattr(record, "correlation_id", "-"))
        if correlation and correlation != "-":
            payload["correlation_id"] = correlation
        extras: dict[str, object] = {}
        for key, value in cast(Mapping[str, object], record.__dict__).items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            extras[key] = value
        if extras:
            payload["extra"] = extras
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", fmt: str = "text") -> logging.Logger:
    """Configure the zscripts root logger."""

    logger = logging.getLogger("zscripts")
    logger.setLevel(_normalize_level(level))
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.addFilter(_CorrelationFilter())
    formatter: logging.Formatter
    mode = fmt.lower()
    if mode not in {"json", "text"}:
        raise ValueError("log format must be 'text' or 'json'")
    if mode == "json":
        formatter = _JsonFormatter()
    else:
        formatter = _TextFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _normalize_level(level: str | int) -> int:
    if isinstance(level, int):
        return level
    candidate = level.upper()
    level_value = cast(int | str, logging.getLevelName(candidate))
    if isinstance(level_value, str):
        raise ValueError(f"Unknown log level: {level}")
    return level_value


def get_logger(name: str) -> logging.Logger:
    """Return a child logger bound to the zscripts hierarchy."""

    return logging.getLogger(f"zscripts.{name}")


@contextmanager
def bind_correlation_id(identifier: str) -> Iterator[None]:
    """Context manager binding a correlation ID for structured logs."""

    token = _CORRELATION_ID.set(identifier)
    try:
        yield
    finally:
        _CORRELATION_ID.reset(token)


def current_correlation_id() -> str | None:
    """Return the active correlation ID, if any."""

    return _CORRELATION_ID.get()


__all__ = ["configure_logging", "get_logger", "bind_correlation_id", "current_correlation_id"]
