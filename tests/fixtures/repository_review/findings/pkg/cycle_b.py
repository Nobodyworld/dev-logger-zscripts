"""Second confirmed dependency-cycle member."""

from pkg import cycle_a


def from_b() -> str:
    return cycle_a.__name__
