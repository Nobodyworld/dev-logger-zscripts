"""CLI smoke tests for zscripts."""

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
