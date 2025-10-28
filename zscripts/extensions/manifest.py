"""Extension manifest definitions for runtime and automation tooling."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import cast


@dataclass(frozen=True, slots=True)
class ExtensionManifest:
    """Lightweight metadata describing a loaded extension."""

    name: str
    module: str
    description: str
    entrypoint: str
    version: str | None = None
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    config_keys: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dictionary representation."""

        return {
            "name": self.name,
            "module": self.module,
            "description": self.description,
            "entrypoint": self.entrypoint,
            "version": self.version,
            "capabilities": list(self.capabilities),
            "config_keys": list(self.config_keys),
        }


def build_manifest(
    *,
    extension: object,
    module: str,
    entrypoint: str,
    default_name: str,
) -> ExtensionManifest:
    """Create an :class:`ExtensionManifest` from a loaded extension object."""

    raw_name = cast(object, getattr(extension, "name", default_name))
    name = str(raw_name or default_name)
    raw_description = cast(object, getattr(extension, "description", ""))
    description = str(raw_description).strip()
    version_value = cast(object, getattr(extension, "version", None))
    version = str(version_value) if version_value is not None else None
    capabilities = _coerce_iterable_strings(cast(object, getattr(extension, "capabilities", ())))
    config_keys = _coerce_iterable_strings(cast(object, getattr(extension, "config_keys", ())))
    return ExtensionManifest(
        name=name,
        module=module,
        description=description,
        entrypoint=entrypoint,
        version=version,
        capabilities=capabilities,
        config_keys=config_keys,
    )


def _coerce_iterable_strings(raw: object) -> tuple[str, ...]:
    if isinstance(raw, str | bytes):
        return (str(raw),)
    if isinstance(raw, Iterable):
        return tuple(str(item) for item in raw)
    return ()


__all__ = ["ExtensionManifest", "build_manifest"]
