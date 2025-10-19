from __future__ import annotations

from agents.cli_adapter import CLICommandSpec, export_cli_metadata, get_cli_command_specs


def test_cli_command_specs_cover_expected_commands() -> None:
    specs = get_cli_command_specs()
    names = {spec.name for spec in specs}
    assert names == {"collect", "consolidate", "tree"}
    for spec in specs:
        assert isinstance(spec, CLICommandSpec)
        assert spec.parameters, "each command should advertise parameters"


def test_export_cli_metadata_contains_presets() -> None:
    payload = export_cli_metadata()
    assert "commands" in payload
    assert "presets" in payload
    assert any(preset["name"] == "python" for preset in payload["presets"])
