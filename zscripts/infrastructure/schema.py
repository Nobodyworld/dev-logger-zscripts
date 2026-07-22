"""Schema validation adapters."""

from __future__ import annotations

import jsonschema

from zscripts.domain.interfaces import SchemaValidatorProtocol
from zscripts.schemas import NormalizedLog, load_normalized_schema


class JsonSchemaValidator(SchemaValidatorProtocol):
    """Validate normalized logs using the bundled JSON schema."""

    def __init__(self) -> None:
        self._schema = load_normalized_schema()

    def validate(self, data: NormalizedLog) -> None:
        jsonschema.validate(instance=data.to_dict(), schema=self._schema)


__all__ = ["JsonSchemaValidator"]
