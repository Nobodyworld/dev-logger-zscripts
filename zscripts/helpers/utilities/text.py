import re
from typing import Final

# TODO - add global path function
_NON_ALNUM_RE: Final = re.compile(r"[^a-zA-Z0-9\-_. ]+")
# TODO - add global path function
_WHITESPACE_RE: Final = re.compile(r"\s+")


def slugify(value: str) -> str:
    """Convert text to a simple, filename-friendly slug with dashes.

    Keeps ASCII letters/numbers, dash/underscore/dot. Collapses whitespace to single dashes.
    """
    value = _NON_ALNUM_RE.sub("", value)
    value = _WHITESPACE_RE.sub("-", value).strip("-._ ")
    return value or "untitled"


def safe_filename(value: str, default: str = "untitled") -> str:
    slug = slugify(value)
    # Avoid empty names after sanitisation
    return slug if slug else default
