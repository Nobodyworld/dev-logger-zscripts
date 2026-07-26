"""Second half of a static import cycle."""

from . import cycle_a


def beta() -> None:
    _ = cycle_a
