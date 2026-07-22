from __future__ import annotations

from importlib import import_module
from importlib.metadata import version


def _major_minor(distribution: str) -> tuple[int, int]:
    parts = version(distribution).split(".")
    return int(parts[0]), int(parts[1])


def test_refreshed_helper_dependencies_import_at_supported_minimums() -> None:
    import_module("lxml")
    import_module("nltk")
    import_module("PIL")
    import_module("dotenv")

    assert _major_minor("lxml") >= (6, 1)
    assert _major_minor("nltk") >= (3, 10)
    assert _major_minor("pillow") >= (12, 3)
    assert _major_minor("python-dotenv") >= (1, 2)
