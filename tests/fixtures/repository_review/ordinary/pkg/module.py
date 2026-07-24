"""Ordinary Python syntax used by repository review tests."""
# ruff: noqa: F821

from __future__ import annotations

import collections.abc as cabc
from pathlib import Path as FilePath


@decorator("value")
class Example(BaseExample, ProtocolLike):
    """A representative class."""

    class Nested:
        pass

    async def method(
        self,
        value: int,
        /,
        option: str = "safe",
        *items: object,
        enabled: bool = True,
        **metadata: str,
    ) -> cabc.Sequence[str]:
        """Return static evidence."""

        def nested_function(argument: FilePath | None = None) -> bool:
            return argument is not None

        return [str(value), option, str(enabled), str(nested_function())]


def top_level(name: str | None = None) -> str:
    return name or "default"
