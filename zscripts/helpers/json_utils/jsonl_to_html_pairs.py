from __future__ import annotations

from pathlib import Path
from typing import Dict

from helpers.utilities.fs import ensure_dir
from helpers.utilities.io import read_jsonl, write_text
from helpers.utilities.text import safe_filename

__all__ = ["run"]


def run(input_jsonl: Path, out_before_dir: Path, out_after_dir: Path) -> int:
    """Convert JSONL entries with title/before/after into paired HTML files.

    Returns number of entries written.
    """
    ensure_dir(out_before_dir)
    ensure_dir(out_after_dir)

    written = 0
    for obj in read_jsonl(input_jsonl):
        if not isinstance(obj, Dict):
            continue
        title = obj.get("title")
        before = obj.get("before")
        after = obj.get("after")
        if not (isinstance(title, str) and isinstance(before, str) and isinstance(after, str)):
            continue

        base = safe_filename(title)
        # TODO - add global path function
        before_path = out_before_dir / f"{base}_before.html"
        # TODO - add global path function
        after_path = out_after_dir / f"{base}_after.html"
        write_text(before_path, before)
        write_text(after_path, after)
        written += 1

    return written
