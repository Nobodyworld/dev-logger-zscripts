"""First half of a static import cycle."""

from . import cycle_b


def alpha() -> None:
    _ = cycle_b
