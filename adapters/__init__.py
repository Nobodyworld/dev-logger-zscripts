"""Collection of framework-agnostic log adapters."""

from __future__ import annotations

from adapters.ci import ADAPTER as CI_ADAPTER
from adapters.docker import ADAPTER as DOCKER_ADAPTER
from adapters.dotnet import ADAPTER as DOTNET_ADAPTER
from adapters.go import ADAPTER as GO_ADAPTER
from adapters.java import ADAPTER as JAVA_ADAPTER
from adapters.javascript import ADAPTER as JAVASCRIPT_ADAPTER
from adapters.python import ADAPTER as PYTHON_ADAPTER
from adapters.registry import (
    AdapterNotFoundError,
    available_adapters,
    get_adapter,
    register_adapters,
)
from adapters.rust import ADAPTER as RUST_ADAPTER

register_adapters(
    [
        PYTHON_ADAPTER,
        JAVASCRIPT_ADAPTER,
        JAVA_ADAPTER,
        GO_ADAPTER,
        RUST_ADAPTER,
        DOTNET_ADAPTER,
        DOCKER_ADAPTER,
        CI_ADAPTER,
    ]
)

__all__ = [
    "available_adapters",
    "get_adapter",
    "register_adapters",
    "AdapterNotFoundError",
]
