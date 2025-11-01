"""Helpers for validating and writing CLI output destinations safely."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Callable, TextIO

__all__ = [
    "OutputPathError",
    "prepare_output_path",
    "atomic_write_text",
    "atomic_write_text_stream",
    "atomic_write_bytes",
]


class OutputPathError(RuntimeError):
    """Raised when an output destination cannot be prepared or written."""

    def __init__(self, path: Path, message: str, *, cause: Exception | None = None) -> None:
        self.path = path
        self.cause = cause
        super().__init__(message)


def prepare_output_path(path: Path) -> Path:
    """Expand and validate an output path before writing.

    The returned path is safe for writing via :func:`atomic_write_text` or
    :func:`atomic_write_bytes`. The helper
    ensures parent directories exist, are traversable, and rejects destinations that
    already exist as directories.
    """

    expanded = path.expanduser()
    try:
        resolved = expanded.resolve(strict=False)
    except OSError:
        # Fallback to the expanded path when resolution fails (e.g., broken symlink).
        resolved = expanded

    if resolved.exists() and resolved.is_dir():
        raise OutputPathError(resolved, f"destination '{resolved}' is a directory")

    parent = resolved.parent if resolved.parent != Path("") else Path.cwd()
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputPathError(resolved, f"unable to create parent directory '{parent}'", cause=exc) from exc

    if not parent.is_dir():
        raise OutputPathError(resolved, f"parent '{parent}' is not a directory")

    required_mode = os.W_OK | os.X_OK
    if not os.access(parent, required_mode):
        raise OutputPathError(
            resolved,
            f"parent directory '{parent}' is not writable or accessible",
        )

    return resolved


def _atomic_write(
    path: Path,
    *,
    open_kwargs: dict[str, Any],
    write_payload: Callable[[Any], None],
) -> None:
    """Perform an atomic write using ``write_payload``."""

    destination = prepare_output_path(path)
    directory = destination.parent

    temp_file_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=False, **open_kwargs) as handle:
            temp_file_path = Path(handle.name)
            write_payload(handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_file_path, destination)
    except OSError as exc:
        message = f"unable to write to '{destination}': {exc.strerror or exc}"
        raise OutputPathError(destination, message, cause=exc) from exc
    finally:
        if temp_file_path and temp_file_path.exists():
            try:
                temp_file_path.unlink()
            except OSError:
                # Ignore cleanup errors; the temp file lives alongside the target
                # directory and can be removed manually if necessary.
                pass


def atomic_write_text_stream(path: Path, writer: Callable[[TextIO], None]) -> None:
    """Write to ``path`` atomically using a callable that receives a text handle."""

    _atomic_write(
        path,
        open_kwargs={"mode": "w", "encoding": "utf-8"},
        write_payload=writer,
    )


def atomic_write_text(path: Path, payload: str) -> None:
    """Write ``payload`` to ``path`` atomically as UTF-8 text."""

    def _writer(handle: TextIO) -> None:
        handle.write(payload)

    atomic_write_text_stream(path, _writer)


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Write ``payload`` to ``path`` atomically as raw bytes."""

    def _writer(handle: Any) -> None:
        handle.write(payload)

    _atomic_write(
        path,
        open_kwargs={"mode": "wb"},
        write_payload=_writer,
    )

