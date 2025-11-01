"""Schema validation adapters."""

from __future__ import annotations

from importlib import import_module
from importlib.util import find_spec
from typing import Any, Protocol, cast

from zscripts.domain.interfaces import SchemaValidatorProtocol
from zscripts.schemas import NormalizedLog, load_normalized_schema


class _JsonSchemaModule(Protocol):
    def validate(self, *, instance: Any, schema: dict[str, Any]) -> None: ...


def _resolve_jsonschema() -> _JsonSchemaModule | None:
    if find_spec("jsonschema") is None:
        return None
    module = import_module("jsonschema")
    return cast(_JsonSchemaModule, module)


jsonschema = _resolve_jsonschema()


class JsonSchemaValidator(SchemaValidatorProtocol):
    """Validate normalized logs using the bundled JSON schema."""

    def __init__(self) -> None:
        self._schema: dict[str, Any] | None = load_normalized_schema() if jsonschema else None

    def validate(self, data: NormalizedLog) -> None:
        if self._schema is None or jsonschema is None:
            return
        jsonschema.validate(instance=data.to_dict(), schema=self._schema)


__all__ = ["JsonSchemaValidator"]
