from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from zscripts.observability.health import HealthTelemetryServer


def test_scaffold_extension_creates_template(tmp_path: Path) -> None:
    target_dir = tmp_path / "extensions"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/scaffold_extension.py",
            "demo_plugin",
            "--directory",
            str(target_dir),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    module_path = target_dir / "demo_plugin.py"
    assert module_path.exists()
    content = module_path.read_text(encoding="utf-8")
    assert "class DemoPluginExtension" in content
    assert "def get_extension" in content


def test_dev_start_honors_skip_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZSKIP_LINT", "1")
    monkeypatch.setenv("ZSKIP_TYPE", "1")
    monkeypatch.setenv("ZSKIP_SECURITY", "1")
    monkeypatch.setenv("ZSKIP_TESTS", "1")
    monkeypatch.setenv("QUALITY_COVERAGE_MIN", "0")
    result = subprocess.run(
        [sys.executable, "scripts/dev_start.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    summary_path = Path("reports/quality_gate.json")
    assert summary_path.exists()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["steps"]["lint"]["status"] == "skipped"
    assert payload["steps"]["tests"]["status"] == "skipped"


def test_ops_status_reports_health(tmp_path: Path) -> None:
    server = HealthTelemetryServer()
    server.start(host="127.0.0.1", port=0)
    try:
        time.sleep(0.1)
        url = f"http://{server.host}:{server.port}"
        output_path = tmp_path / "status.json"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/ops_status.py",
                "--url",
                url,
                "--output",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] in {"ok", "pass"}
        assert output_path.exists()
    finally:
        server.stop()


def test_ops_status_flags_degraded_status(tmp_path: Path) -> None:
    server = HealthTelemetryServer(status_provider=lambda: {"status": "degraded"})
    server.start(host="127.0.0.1", port=0)
    try:
        time.sleep(0.1)
        url = f"http://{server.host}:{server.port}"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/ops_status.py",
                "--url",
                url,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "degraded"
    finally:
        server.stop()
