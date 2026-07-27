"""First confirmed dependency-cycle member."""

from pkg import cycle_b


def from_a() -> str:
    return cycle_b.from_b()
