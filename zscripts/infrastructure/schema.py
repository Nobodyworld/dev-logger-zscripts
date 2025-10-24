"""Schema validation adapters."""

from __future__ import annotations

from typing import Any

from zscripts.domain.interfaces import SchemaValidatorProtocol
from zscripts.schemas import NormalizedLog, load_normalized_schema

try:  # pragma: no cover - optional dependency
    import jsonschema
except ImportError:  # pragma: no cover - optional dependency missing
    jsonschema = None  # type: ignore[assignment]


class JsonSchemaValidator(SchemaValidatorProtocol):
    """Validate normalized logs using the bundled JSON schema."""

    def __init__(self) -> None:
        self._schema: dict[str, Any] | None = load_normalized_schema() if jsonschema else None

    def validate(self, data: NormalizedLog) -> None:
        if self._schema is None or jsonschema is None:
            return
        jsonschema.validate(instance=data.to_dict(), schema=self._schema)


__all__ = ["JsonSchemaValidator"]
