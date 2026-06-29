"""Persistence backends for crawler output.

The original crawler only wrote the extracted text to ``*.txt`` files. As the
helper collection grew we needed richer metadata for downstream processing,
including content hashes, crawl depth, and crawl identifiers. This module
provides a structured interface for persisting crawled pages alongside a JSON
metadata companion so future automation has a reliable substrate to build on.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

__all__ = [
    "StorageDocument",
    "StorageBackend",
    "DirectoryStorage",
]


@dataclass(slots=True)
class StorageDocument:
    """Container describing the payload that should be persisted."""

    url: str
    text: str
    content_type: str | None
    content_hash: str
    fetched_at: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the document metadata."""
        payload = {
            "url": self.url,
            "content_type": self.content_type,
            "content_hash": self.content_hash,
            "fetched_at": self.fetched_at,
        }
        payload.update(self.metadata)
        payload["text_bytes"] = len(self.text.encode("utf-8"))
        return payload


class StorageBackend(Protocol):
    """Protocol implemented by crawler persistence backends."""

    def persist(self, document: StorageDocument) -> Path | None:
        """Persist ``document`` returning the path to the primary text artefact."""

    def close(self) -> None:
        """Release any open resources held by the backend."""


class DirectoryStorage:
    """Persist crawled pages as ``.txt`` + ``.json`` pairs within a directory."""

    def __init__(
        self,
        root: Path,
        *,
        slugify: Callable[[str], str],
        metadata_suffix: str = ".json",
        index_path: Path | None = None,
    ) -> None:
        """Initialise the storage directory and optional metadata index."""
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._slugify = slugify
        self._metadata_suffix = metadata_suffix
        self._index_path = index_path
        self._index_lock = threading.Lock()
        if self._index_path is not None:
            self._index_path.parent.mkdir(parents=True, exist_ok=True)

    def persist(self, document: StorageDocument) -> Path | None:
        """Persist the text and metadata for ``document`` to disk."""
        slug = self._slugify(document.url)
        text_path = self.root / f"{slug}.txt"
        metadata_path = text_path.with_suffix(self._metadata_suffix)

        text_path.write_text(document.text, encoding="utf-8")
        metadata = document.to_metadata()
        metadata["text_path"] = str(text_path)
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

        if self._index_path is not None:
            serialised = json.dumps(metadata, sort_keys=True)
            with self._index_lock:
                with self._index_path.open("a", encoding="utf-8") as handle:
                    handle.write(serialised + "\n")

        return text_path

    def close(self) -> None:  # pragma: no cover - provided for interface symmetry
        """Close the storage backend (no-op for directory storage)."""
        return None
