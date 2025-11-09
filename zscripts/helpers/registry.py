from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Callable, Dict

import yaml

_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "configs" / "registry.yaml"


def _load_registry() -> Dict[str, str]:
    with _REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve(tag: str) -> Callable[..., Any]:
    """Resolve a tag to a callable using registry.yaml.

    Tag format maps to entries like: module.path:object or module.path:function
    Example: 'pillow.add_watermark' → 'helpers.pillow.add_watermark:add_watermark'
    """
    mapping = _load_registry()
    target = mapping.get(tag)
    if not target:
        raise KeyError(f"Unknown registry tag: {tag}")
    if ":" not in target:
        raise ValueError(f"Invalid target spec for {tag!r}: {target!r}")
    mod_path, obj_name = target.split(":", 1)
    mod = importlib.import_module(mod_path)
    fn = getattr(mod, obj_name)
    if not callable(fn):
        raise TypeError(f"Resolved object is not callable: {target}")
    return fn


def call(tag: str, *args: Any, **kwargs: Any) -> Any:
    """Convenience wrapper to resolve and invoke a callable by tag."""
    fn = resolve(tag)
    return fn(*args, **kwargs)
