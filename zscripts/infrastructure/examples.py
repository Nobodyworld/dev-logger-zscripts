"""Example discovery backed by the repository filesystem."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from zscripts.domain.interfaces import ExampleRepositoryProtocol


class FileSystemExampleRepository(ExampleRepositoryProtocol):
    """Locate bundled example log files on disk."""

    def __init__(self, base_directory: Path) -> None:
        self._base = base_directory

    def list_examples(self, adapter: str | None = None) -> Sequence[Path]:
        if not self._base.exists():
            return []
        entries: list[Path] = []
        for adapter_dir in sorted(self._base.iterdir()):
            if not adapter_dir.is_dir():
                continue
            if adapter and adapter_dir.name != adapter:
                continue
            for file in sorted(adapter_dir.glob("*.log")):
                entries.append(file)
        return entries


__all__ = ["FileSystemExampleRepository"]
