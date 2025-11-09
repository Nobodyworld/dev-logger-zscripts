from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Iterator

from .fs import ensure_dir


def read_text(path: Path, encoding: str = "utf-8") -> str:
    return path.read_text(encoding=encoding)


def write_text(path: Path, data: str, encoding: str = "utf-8") -> None:
    ensure_dir(path.parent)
    path.write_text(data, encoding=encoding)


def read_jsonl(path: Path, encoding: str = "utf-8") -> Iterator[Any]:
    with path.open("r", encoding=encoding) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def write_jsonl(path: Path, items: Iterable[Any], encoding: str = "utf-8") -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding=encoding) as fh:
        for obj in items:
            # TODO - add global path function
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
