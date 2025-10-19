"""Shared type preset registry for log aggregation commands."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ._cache import typed_lru_cache


@dataclass(frozen=True, slots=True)
class TypePreset:
    """Describe a stack preset used by the CLI commands."""

    name: str
    extensions: tuple[str, ...]
    collect_log: str
    single_target: str
    summary: str

    def normalised_extensions(self) -> frozenset[str]:
        """Return the extension set as lowercase, deduplicated entries."""

        return frozenset(extension.lower() for extension in self.extensions)

    def to_agent_payload(self) -> dict[str, object]:
        """Return a serialisable structure for AI integrations."""

        return {
            "name": self.name,
            "extensions": list(self.extensions),
            "collect_log": self.collect_log,
            "single_target": self.single_target,
            "summary": self.summary,
        }


_PRESETS: tuple[TypePreset, ...] = (
    TypePreset(
        name="python",
        extensions=(".py",),
        collect_log="logs_apps_pyth",
        single_target="capture_all_pyth.txt",
        summary="Standard Python modules and packages.",
    ),
    TypePreset(
        name="html",
        extensions=(".html",),
        collect_log="logs_apps_html",
        single_target="capture_all_html.txt",
        summary="Static HTML templates and documents.",
    ),
    TypePreset(
        name="css",
        extensions=(".css",),
        collect_log="logs_apps_css",
        single_target="capture_all_css.txt",
        summary="Stylesheets for browsers and web components.",
    ),
    TypePreset(
        name="js",
        extensions=(".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"),
        collect_log="logs_apps_js",
        single_target="capture_all_js.txt",
        summary="JavaScript and TypeScript sources, including module variants.",
    ),
    TypePreset(
        name="python_html",
        extensions=(".py", ".html"),
        collect_log="logs_apps_both",
        single_target="capture_all_python_html.txt",
        summary="Combined Python and HTML stack for server-rendered apps.",
    ),
)


@typed_lru_cache(maxsize=1)
def get_preset_map() -> Mapping[str, TypePreset]:
    """Return an immutable mapping of preset name to definition."""

    return MappingProxyType({preset.name: preset for preset in _PRESETS})


def iter_presets() -> Iterator[TypePreset]:
    """Yield each preset definition in declaration order."""

    return iter(_PRESETS)


@typed_lru_cache(maxsize=1)
def get_collect_extension_map() -> Mapping[str, frozenset[str]]:
    """Return the per-preset extension map including the aggregated ``all`` bucket."""

    mapping = {name: preset.normalised_extensions() for name, preset in get_preset_map().items()}
    mapping["all"] = frozenset().union(*mapping.values())
    return MappingProxyType(mapping)


@typed_lru_cache(maxsize=1)
def get_single_extension_map() -> Mapping[str, frozenset[str]]:
    """Return the extension map for single-file consolidation targets."""

    collect_map = dict(get_collect_extension_map())
    mapping = {name: collect_map[name] for name in get_preset_map()}
    mapping["any"] = collect_map["all"]
    return MappingProxyType(mapping)


@typed_lru_cache(maxsize=1)
def get_default_collection_logs() -> Mapping[str, str]:
    """Return default directory names keyed by collection type."""

    mapping = {preset.name: preset.collect_log for preset in get_preset_map().values()}
    mapping.update({"all": "logs_apps_all", "single": "logs_single_files"})
    return MappingProxyType(mapping)


@typed_lru_cache(maxsize=1)
def get_default_single_targets() -> Mapping[str, str]:
    """Return default filenames for single-target consolidations."""

    mapping = {preset.name: preset.single_target for preset in get_preset_map().values()}
    mapping["any"] = "capture_all.txt"
    return MappingProxyType(mapping)


def list_preset_names() -> tuple[str, ...]:
    """Return the ordered preset names for presentation purposes."""

    return tuple(preset.name for preset in _PRESETS)


def list_extension_choices(bucket: str, *, single: bool = False) -> frozenset[str]:
    """Return extension set for the named bucket (``all``/``any`` supported)."""

    mapping = get_single_extension_map() if single else get_collect_extension_map()
    if bucket not in mapping:
        raise KeyError(f"Unknown preset bucket: {bucket}")
    return mapping[bucket]


def presets_to_agent_payload() -> list[dict[str, object]]:
    """Serialise all presets for agent metadata documents."""

    return [preset.to_agent_payload() for preset in _PRESETS]
