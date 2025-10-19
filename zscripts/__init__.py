"""zscripts package entry point for programmatic access."""

from .config import get_config  # re-export for convenience
from .presets import get_collect_extension_map, get_single_extension_map, presets_to_agent_payload

__all__ = [
    "get_config",
    "get_collect_extension_map",
    "get_single_extension_map",
    "presets_to_agent_payload",
]
