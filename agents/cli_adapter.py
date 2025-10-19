"""Structured metadata describing the zscripts CLI surface for agents."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from zscripts.presets import (
    get_collect_extension_map,
    get_single_extension_map,
    presets_to_agent_payload,
)


@dataclass(frozen=True, slots=True)
class CLIParameterSpec:
    """Describe a command-line parameter for agent tooling."""

    name: str
    type: str
    description: str
    required: bool = False
    default: str | bool | None = None
    choices: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        """Return a JSON-serialisable payload."""

        payload: dict[str, object] = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }
        if self.default is not None:
            payload["default"] = self.default
        if self.choices:
            payload["choices"] = list(self.choices)
        return payload


@dataclass(frozen=True, slots=True)
class CLICommandSpec:
    """Describe one CLI command including parameters and usage examples."""

    name: str
    summary: str
    parameters: tuple[CLIParameterSpec, ...]
    examples: tuple[str, ...]
    returns: str

    def to_payload(self) -> dict[str, object]:
        """Return a JSON-serialisable payload."""

        return {
            "name": self.name,
            "summary": self.summary,
            "parameters": [param.to_payload() for param in self.parameters],
            "examples": list(self.examples),
            "returns": self.returns,
        }


def _choices_from_mapping(mapping: Iterable[str]) -> tuple[str, ...]:
    return tuple(mapping)


def get_cli_command_specs() -> tuple[CLICommandSpec, ...]:
    """Return the structured metadata for the supported CLI commands."""

    collect_choices = _choices_from_mapping(get_collect_extension_map().keys())
    single_choices = _choices_from_mapping(get_single_extension_map().keys())

    collect_params = (
        CLIParameterSpec(
            name="types",
            type="string",
            description="Comma-separated list of stack presets to capture.",
            default="python",
            choices=collect_choices,
        ),
        CLIParameterSpec(
            name="project_root",
            type="path",
            description=(
                "Root directory to scan. Defaults to auto-detecting the nearest "
                "project or repository root."
            ),
        ),
        CLIParameterSpec(
            name="output_dir",
            type="path",
            description="Optional directory for generated log bundles.",
        ),
        CLIParameterSpec(
            name="dry_run",
            type="boolean",
            description="Preview actions without writing any files.",
            default=False,
        ),
    )

    consolidate_params = (
        CLIParameterSpec(
            name="types",
            type="string",
            description="Stack preset to consolidate (single value).",
            default="python",
            choices=single_choices,
        ),
        CLIParameterSpec(
            name="output",
            type="path",
            description="Destination file for the consolidated bundle. Use '-' for stdout.",
        ),
        CLIParameterSpec(
            name="project_root",
            type="path",
            description="Root directory to consolidate from (auto-detected when omitted).",
        ),
        CLIParameterSpec(
            name="dry_run",
            type="boolean",
            description="Preview consolidation without touching the filesystem.",
            default=False,
        ),
    )

    tree_params = (
        CLIParameterSpec(
            name="output",
            type="path",
            description="Destination for the tree snapshot. Use '-' to stream to stdout.",
        ),
        CLIParameterSpec(
            name="include_contents",
            type="boolean",
            description="Include file contents inline with the tree output.",
            default=False,
        ),
        CLIParameterSpec(
            name="max_bytes",
            type="integer",
            description="Maximum bytes to read per file when including contents.",
            default="4096",
        ),
        CLIParameterSpec(
            name="project_root",
            type="path",
            description="Root directory to inspect (auto-detected when omitted).",
        ),
    )

    return (
        CLICommandSpec(
            name="collect",
            summary="Generate per-application source logs for selected stacks.",
            parameters=collect_params,
            examples=(
                "python -m zscripts collect --types python,js",
                "zscripts --verbose collect --dry-run",
            ),
            returns="Exit code 0 on success; writes log files to the configured directory.",
        ),
        CLICommandSpec(
            name="consolidate",
            summary="Merge sources for a stack into a single file or stream.",
            parameters=consolidate_params,
            examples=(
                "python -m zscripts consolidate --types html --output -",
                "zscripts consolidate --types python --output-dir ./logs",
            ),
            returns="Exit code 0 on success; writes a consolidated log file or stdout stream.",
        ),
        CLICommandSpec(
            name="tree",
            summary="Produce a filtered project tree with optional file contents.",
            parameters=tree_params,
            examples=(
                "python -m zscripts tree --include-contents --max-bytes 2048",
                "zscripts tree --output ./logs/project_tree.txt",
            ),
            returns="Exit code 0 on success; writes a project tree snapshot.",
        ),
    )


def export_cli_metadata() -> dict[str, object]:
    """Return a payload suitable for publishing agent metadata documents."""

    return {
        "commands": [spec.to_payload() for spec in get_cli_command_specs()],
        "presets": presets_to_agent_payload(),
    }
