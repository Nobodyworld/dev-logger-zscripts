"""Framework-shaped fixture that must only be parsed as syntax."""

import django

django.setup()


class ExampleModel:
    """A framework-neutral class despite the inert setup call above."""

    pass
