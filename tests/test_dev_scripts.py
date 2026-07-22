from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

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
