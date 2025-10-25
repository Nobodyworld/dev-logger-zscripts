"""Integration tests exercising the CLI entry point."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from zscripts import cli as cli_module
from zscripts.observability import metrics as metrics_module

CLI = Path("cli.py")
PYTHON = sys.executable


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([PYTHON, str(CLI), *args], check=False, text=True, capture_output=True)


def _allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


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


@pytest.fixture()
def telemetry_harness(monkeypatch: pytest.MonkeyPatch) -> tuple[metrics_module.MetricsRegistry, type[cli_module.TelemetryManager]]:
    registry = metrics_module.MetricsRegistry()
    monkeypatch.setattr(metrics_module, "default_registry", registry)

    class RecordingTelemetryManager(cli_module.TelemetryManager):
        instances: list[RecordingTelemetryManager] = []

        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            kwargs.setdefault("metrics", registry)
            super().__init__(*args, **kwargs)
            self.stop_calls = 0
            RecordingTelemetryManager.instances.append(self)

        def stop(self) -> None:  # noqa: D401 - override to track invocations
            self.stop_calls += 1
            super().stop()

    RecordingTelemetryManager.instances.clear()
    monkeypatch.setattr(cli_module, "TelemetryManager", RecordingTelemetryManager)
    return registry, RecordingTelemetryManager


def test_cli_records_success_metrics(tmp_path: Path, telemetry_harness: tuple[metrics_module.MetricsRegistry, type[cli_module.TelemetryManager]]) -> None:
    registry, manager_cls = telemetry_harness
    config_path = tmp_path / "settings.toml"
    config_path.write_text(f"telemetry_port = {_allocate_port()}\n", encoding="utf-8")

    cli_module.main(["--config", str(config_path), "--enable-telemetry", "guardrails"])

    metrics_text = registry.collect_prometheus()
    assert "zscripts_cli_invocations_total" in metrics_text
    assert 'command="guardrails"' in metrics_text
    assert 'status="success"' in metrics_text
    assert "zscripts_cli_duration_seconds_count" in metrics_text
    instance = manager_cls.instances[-1]
    assert instance.stop_calls == 1
    assert instance.health_server.is_running() is False


def test_cli_records_failure_metrics(tmp_path: Path, telemetry_harness: tuple[metrics_module.MetricsRegistry, type[cli_module.TelemetryManager]]) -> None:
    registry, _ = telemetry_harness
    config_path = tmp_path / "settings.toml"
    config_path.write_text(f"telemetry_port = {_allocate_port()}\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        cli_module.main([
            "--config",
            str(config_path),
            "--enable-telemetry",
            "collect",
            "--command",
        ])

    assert excinfo.value.code == 2
    metrics_text = registry.collect_prometheus()
    assert "zscripts_cli_invocations_total" in metrics_text
    assert 'command="collect"' in metrics_text
    assert 'status="error"' in metrics_text
