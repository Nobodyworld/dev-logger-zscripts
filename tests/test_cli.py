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


@pytest.mark.parametrize(
    ("policy", "severity", "expected"),
    [
        ("never", "ok", False),
        ("warnings", "warning", True),
        ("warnings", "ok", False),
        ("errors", "warning", False),
        ("errors", "error", True),
        ("errors", "critical", True),
    ],
)
def test_cli_should_fail_threshold(policy: str, severity: str, expected: bool) -> None:
    assert cli_module._should_fail(policy, severity) is expected


def test_read_stdin_payload_ignores_unsupported_select(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnsupportedSelectStdin:
        closed = False

        def fileno(self) -> int:
            return 0

        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            raise AssertionError("stdin should not be read when select fails")

    def raise_os_error(*_args: object, **_kwargs: object) -> tuple[list[object], list[object], list[object]]:
        raise OSError("unsupported stdin handle")

    monkeypatch.setattr(cli_module.sys, "stdin", UnsupportedSelectStdin())
    monkeypatch.setattr(cli_module.select, "select", raise_os_error)

    assert cli_module._read_stdin_payload() is None


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


def test_cli_report_json_output() -> None:
    result = _run_cli(
        "report",
        "--input",
        str(Path("examples/python/sample.log")),
        "--format",
        "json",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["normalized"]["tool"] == "pytest"
    assert payload["redacted_text"] is None
    assert payload["severity"] == "error"


def test_cli_report_markdown_output() -> None:
    result = _run_cli(
        "report",
        "--input",
        str(Path("examples/python/sample.log")),
        "--format",
        "markdown",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("# pytest Report")
    assert "- **Severity:**" in result.stdout


def test_cli_report_redact_markdown_redacts_normalized_content() -> None:
    result = _run_cli(
        "--adapter",
        "ci",
        "report",
        "--input",
        str(Path("examples/raw_to_report/raw.log")),
        "--format",
        "markdown",
        "--redact",
    )

    assert result.returncode == 0, result.stderr
    assert "not-a-real-secret-redaction-fixture-1234567890abcdef" not in result.stdout
    assert "[REDACTED]" in result.stdout


def test_cli_report_redact_json_redacts_normalized_content() -> None:
    result = _run_cli(
        "--adapter",
        "ci",
        "report",
        "--input",
        str(Path("examples/raw_to_report/raw.log")),
        "--format",
        "json",
        "--redact",
    )

    assert result.returncode == 0, result.stderr
    assert "not-a-real-secret-redaction-fixture-1234567890abcdef" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["redacted_text"] is not None


def test_cli_global_adapter_must_precede_subcommand() -> None:
    invalid = _run_cli(
        "report",
        "--adapter",
        "ci",
        "--input",
        str(Path("examples/raw_to_report/raw.log")),
        "--format",
        "json",
    )
    valid = _run_cli(
        "--adapter",
        "ci",
        "report",
        "--input",
        str(Path("examples/raw_to_report/raw.log")),
        "--format",
        "json",
    )

    assert invalid.returncode == 2
    assert "unrecognized arguments: --adapter ci" in invalid.stderr
    assert valid.returncode == 0, valid.stderr


def test_cli_report_respects_redact_toggle(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.toml"
    config_path.write_text("report_redact = true\n", encoding="utf-8")

    result = _run_cli(
        "--config",
        str(config_path),
        "report",
        "--input",
        str(Path("examples/python/sample.log")),
        "--format",
        "json",
        "--no-redact",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["redacted_text"] is None


def test_cli_report_fail_on_errors_exits_nonzero() -> None:
    result = _run_cli(
        "report",
        "--input",
        str(Path("examples/python/sample.log")),
        "--format",
        "json",
        "--fail-on",
        "errors",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["severity"] == "error"


def test_cli_report_fail_on_respects_configuration(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.toml"
    config_path.write_text("report_fail_on = 'errors'\n", encoding="utf-8")

    result = _run_cli(
        "--config",
        str(config_path),
        "report",
        "--input",
        str(Path("examples/python/sample.log")),
        "--format",
        "json",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["severity"] == "error"


def test_cli_report_fail_on_cli_override(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.toml"
    config_path.write_text("report_fail_on = 'errors'\n", encoding="utf-8")

    result = _run_cli(
        "--config",
        str(config_path),
        "report",
        "--input",
        str(Path("examples/python/sample.log")),
        "--format",
        "json",
        "--fail-on",
        "never",
    )

    assert result.returncode == 0, result.stderr


def test_cli_summarize_outputs_summary() -> None:
    result = _run_cli(
        "summarize",
        "--input",
        str(Path("examples/python/sample.log")),
    )

    assert result.returncode == 0, result.stderr
    assert "[FAILED] pytest run for python" in result.stdout


def test_cli_explain_outputs_details() -> None:
    result = _run_cli(
        "explain",
        "--input",
        str(Path("examples/python/sample.log")),
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("Tool: pytest")
    assert "Summary:" in result.stdout


def test_cli_redact_applies_patterns(tmp_path: Path) -> None:
    sample = tmp_path / "secret.log"
    sample.write_text("token=SECRET12345\n", encoding="utf-8")
    config_path = tmp_path / "settings.toml"
    config_path.write_text("redact_patterns = ['SECRET\\d+']\n", encoding="utf-8")

    result = _run_cli(
        "--config",
        str(config_path),
        "redact",
        "--input",
        str(sample),
    )

    assert result.returncode == 0, result.stderr
    assert "[REDACTED]" in result.stdout
    assert "SECRET" not in result.stdout


def test_cli_examples_lists_paths() -> None:
    result = _run_cli("examples")

    assert result.returncode == 0, result.stderr
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert "examples/python/sample.log" in lines


def test_cli_examples_json_format() -> None:
    result = _run_cli("examples", "--format", "json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "examples/python/sample.log" in payload


def test_cli_adapters_json_format() -> None:
    result = _run_cli("adapters", "--format", "json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    identifiers = [entry["identifier"] for entry in payload]
    assert identifiers == [
        "ci",
        "docker",
        "dotnet",
        "go",
        "java",
        "javascript",
        "python",
        "rust",
    ]
    python_entry = next(entry for entry in payload if entry["identifier"] == "python")
    assert python_entry["examples"] == ["examples/python/sample.log"]


def test_cli_adapters_respects_adapter_override() -> None:
    result = _run_cli("--adapter", "python", "adapters", "--format", "json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert [entry["identifier"] for entry in payload] == ["python"]


def test_cli_adapters_unknown_adapter_exits_nonzero() -> None:
    result = _run_cli("--adapter", "doesnotexist", "adapters", "--format", "json")

    assert result.returncode == 2
    assert "Unknown adapter: doesnotexist" in result.stderr


def test_cli_report_output_directory_error(tmp_path: Path) -> None:
    result = _run_cli(
        "report",
        "--input",
        str(Path("examples/python/sample.log")),
        "--format",
        "json",
        "--output",
        str(tmp_path),
    )

    assert result.returncode == 2
    assert "is a directory" in result.stderr


def test_cli_diagnostics_output_directory_error(tmp_path: Path) -> None:
    result = _run_cli(
        "diagnostics",
        "--output",
        str(tmp_path),
    )

    assert result.returncode == 2
    assert "is a directory" in result.stderr


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
    assert "echo (v1.0.0) [zscripts.extensions.examples.plugin_echo]" in result.stdout


def test_cli_extensions_list_json_format(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.toml"
    config_path.write_text(
        "extensions = ['zscripts.extensions.examples.plugin_echo']",
        encoding="utf-8",
    )

    result = _run_cli(
        "--config",
        str(config_path),
        "extensions",
        "--output-format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert payload and payload[0]["name"] == "echo"
    assert payload[0]["module"] == "zscripts.extensions.examples.plugin_echo"
    assert payload[0]["capabilities"] == ["cli", "demo"]


def test_cli_extensions_scaffold_creates_file(tmp_path: Path) -> None:
    target_dir = tmp_path / "extensions"
    result = _run_cli(
        "extensions",
        "scaffold",
        "demo_extension",
        "--directory",
        str(target_dir),
    )

    assert result.returncode == 0, result.stderr
    module_path = target_dir / "demo_extension.py"
    assert module_path.exists()
    contents = module_path.read_text(encoding="utf-8")
    assert "class DemoExtension" in contents
    assert "context.instrumentation" in contents
    assert 'version = "0.1.0"' in contents
    assert "def after_service_ready" in contents


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
def telemetry_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[metrics_module.MetricsRegistry, type[cli_module.TelemetryManager]]:
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


def test_cli_records_success_metrics(
    tmp_path: Path,
    telemetry_harness: tuple[metrics_module.MetricsRegistry, type[cli_module.TelemetryManager]],
) -> None:
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


def test_cli_records_failure_metrics(
    tmp_path: Path,
    telemetry_harness: tuple[metrics_module.MetricsRegistry, type[cli_module.TelemetryManager]],
) -> None:
    registry, _ = telemetry_harness
    config_path = tmp_path / "settings.toml"
    config_path.write_text(f"telemetry_port = {_allocate_port()}\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        cli_module.main(
            [
                "--config",
                str(config_path),
                "--enable-telemetry",
                "collect",
                "--command",
            ]
        )

    assert excinfo.value.code == 2
    metrics_text = registry.collect_prometheus()
    assert "zscripts_cli_invocations_total" in metrics_text
    assert 'command="collect"' in metrics_text
    assert 'status="error"' in metrics_text


def test_cli_diagnostics_generates_json(tmp_path: Path) -> None:
    output_path = tmp_path / "diagnostics.json"
    cli_module.main(["diagnostics", "--output", str(output_path)])
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["extensions"]["count"] == 0
    assert "telemetry" in payload
    assert payload["telemetry"]["status"] in {"ok", "degraded", "inactive"}


def test_cli_diagnostics_text_format(capsys: pytest.CaptureFixture[str]) -> None:
    cli_module.main(["diagnostics", "--format", "text"])
    output = capsys.readouterr().out
    assert "Generated:" in output
    assert "Status:" in output
