from __future__ import annotations

import os
from pathlib import Path
from typing import Union

from dotenv import find_dotenv, load_dotenv

# Load .env once at import time (search upwards from CWD)
load_dotenv(find_dotenv(), override=False)


def _env_path(var: str) -> Path | None:
    value = os.environ.get(var)
    if not value:
        return None
    try:
        return Path(value).expanduser().resolve()
    except Exception:
        return Path(value).expanduser()


def organization_storage_root() -> Path:
    """Return the configured organization storage root.

    Uses the first defined of:
    - ORGANIZATION_STORAGE_ROOT
    - ORGANIZATION_STORAGE
    Falls back to the current working directory if unset.
    """
    for var in ("ORGANIZATION_STORAGE_ROOT", "ORGANIZATION_STORAGE"):
        p = _env_path(var)
        if p is not None:
            return p
    return Path.cwd()


def org_path(*parts: Union[str, os.PathLike]) -> Path:
    """Build a path under the organization storage root.

    Example:
        org_path('Revenue Streams', 'Blogs', 'format_ai', 'after_mst')
    """
    base = organization_storage_root()
    out = base
    for segment in parts:
        out = out / Path(segment)
    return out
