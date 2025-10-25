from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


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
