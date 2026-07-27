"""Resolved internal inheritance-depth fixture."""


class Base:
    """Base class."""


class LevelOne(Base):
    """Level one."""


class LevelTwo(LevelOne):
    """Level two."""


class LevelThree(LevelTwo):
    """Level three."""


class LevelFour(LevelThree):
    """Level four."""


class LevelFive(LevelFour):
    """Level five."""


class LevelSix(LevelFive):
    """Level six."""
