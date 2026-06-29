"""Agent-oriented helpers for integrating with zscripts."""

from .cli_adapter import CLICommandSpec, CLIParameterSpec, get_cli_command_specs

__all__ = ["CLICommandSpec", "CLIParameterSpec", "get_cli_command_specs"]
