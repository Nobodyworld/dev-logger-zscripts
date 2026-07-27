"""A recognized test module with a resolved import to the source module."""

from pkg import metrics


def exercise_fixture_import() -> None:
    assert metrics.orphan_candidate()
