from pathlib import Path
from typing import Iterable


def ensure_dir(path: Path) -> Path:
    """Create a directory (and parents) if it does not exist and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def iter_files(root: Path, pattern: str = "*") -> Iterable[Path]:
    """Yield files under root matching a glob pattern (non-recursive)."""
    yield from (p for p in root.glob(pattern) if p.is_file())


# TODO - add global path function
def iter_files_recursive(root: Path, pattern: str = "**/*") -> Iterable[Path]:
    """Yield files under root recursively matching a glob pattern."""
    yield from (p for p in root.glob(pattern) if p.is_file())
