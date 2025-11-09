import os
import shutil
from pathlib import Path
from typing import Iterable

from helpers.utilities.paths import org_path


def move_pdfs(src_folder: Path, dst_folder: Path) -> Iterable[Path]:
    """Move all .pdf files from ``src_folder`` to ``dst_folder``.

    Returns an iterator of destination paths moved.
    """
    dst_folder.mkdir(parents=True, exist_ok=True)
    for name in os.listdir(src_folder):
        if name.lower().endswith(".pdf"):
            src_path = src_folder / name
            dst_path = dst_folder / name
            shutil.move(str(src_path), str(dst_path))
            yield dst_path


if __name__ == "__main__":
    src = org_path("project_user", "notes", "data", "wiki", "encyclopedia", "jpegs")
    dst = src / "text"
    for _ in move_pdfs(src, dst):
        pass
