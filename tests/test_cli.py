"""Integration tests exercising the CLI entry point."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

CLI = Path("cli.py")
PYTHON = sys.executable


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([PYTHON, str(CLI), *args], check=False, text=True, capture_output=True)


def test_cli_parse_produces_json() -> None:
    result = _run_cli(
        "--adapter",
        "python",
        "parse",
        "--input",
        str(Path("examples/python/sample.log")),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["tool"] == "pytest"
    assert payload["status"] == "failed"


def test_cli_guardrails_outputs_settings() -> None:
    result = _run_cli("guardrails")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "allowed_paths" in payload
    assert "dangerous_mode" in payload


def test_cli_uses_configuration_file(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.toml"
    config_path.write_text(
        "\n".join(
            [
                "timeout_seconds = 7",
                "dangerous_mode = true",
                "allowed_paths = ['examples', 'tests']",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_cli("--config", str(config_path), "guardrails")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["timeout_seconds"] == 7
    assert payload["dangerous_mode"] is True
    assert set(payload["allowed_paths"]) >= {"examples", "tests"}


def test_cli_set_overrides_take_precedence(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.toml"
    config_path.write_text(
        "\n".join(
            [
                "timeout_seconds = 15",
                "dangerous_mode = true",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_cli(
        "--config",
        str(config_path),
        "--set",
        "timeout_seconds=33",
        "--set",
        "dangerous_mode=false",
        "guardrails",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["timeout_seconds"] == 33
    assert payload["dangerous_mode"] is False


def test_cli_extensions_command_lists_loaded(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.toml"
    config_path.write_text(
        "extensions = ['zscripts.extensions.examples.plugin_echo']",
        encoding="utf-8",
    )

    result = _run_cli("--config", str(config_path), "extensions")

    assert result.returncode == 0, result.stderr
    assert "echo" in result.stdout


def test_cli_extension_command_executes(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.toml"
    config_path.write_text(
        "extensions = ['zscripts.extensions.examples.plugin_echo']",
        encoding="utf-8",
    )

    result = _run_cli("--config", str(config_path), "echo", "hello")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "hello"
