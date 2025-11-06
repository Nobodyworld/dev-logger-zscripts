from __future__ import annotations

from agents import cli_adapter


def test_cli_command_metadata_includes_new_surfaces() -> None:
    commands = {spec.name for spec in cli_adapter.get_cli_command_specs()}
    expected = {"summarize", "explain", "redact", "examples"}
    assert expected.issubset(commands)


def test_export_cli_metadata_shape() -> None:
    payload = cli_adapter.export_cli_metadata()
    command_names = {entry["name"] for entry in payload["commands"]}
    assert "report" in command_names
    summarize_entry = next(item for item in payload["commands"] if item["name"] == "summarize")
    parameter_names = {param["name"] for param in summarize_entry["parameters"]}
    assert {"input", "command", "redact"} <= parameter_names
    assert any(param["name"] == "format" for param in payload["global_parameters"]) is False
