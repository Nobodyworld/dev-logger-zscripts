from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

DPI: Tuple[int, int] = (300, 300)


@dataclass(frozen=True)
class ResizeProfile:
    """Immutable profile for resizing with optional margins."""

    label: str
    size: Tuple[int, int]
    margin_inches: float = 0.0


# Default print profiles used by image_ratio helpers
DEFAULT_PROFILES: tuple[ResizeProfile, ...] = (
    ResizeProfile("11x14", (3300, 4200), 0.0),
    ResizeProfile("4x5", (4800, 6000), 0.0),
    ResizeProfile("3x4", (5400, 7200), 0.5),
    ResizeProfile("2x3", (6000, 9000), 0.5),
    ResizeProfile("International", (5906, 8268), 0.5),
)
