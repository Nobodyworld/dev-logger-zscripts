"""Smoke tests for top-level package helpers and entry points."""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import zscripts
from scripts.build_artifact import build_cli_bundle
from zscripts import get_default_config, get_version


def test_get_version_falls_back_when_metadata_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_not_found(name: str) -> str:
        raise zscripts.metadata.PackageNotFoundError()

    monkeypatch.setattr(zscripts.metadata, "version", raise_not_found)
    assert get_version() == "0.0.0"


def test_get_default_config_returns_fresh_instances() -> None:
    first = get_default_config()
    second = get_default_config()
    assert first is not second
    first.timeout_seconds = 999
    assert second.timeout_seconds != 999


def test_module_entry_point_invokes_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    def fake_main(argv: list[str] | None = None) -> None:
        calls.append(argv)

    monkeypatch.setattr("zscripts.cli.main", fake_main)
    runpy.run_module("zscripts.__main__", run_name="__main__")
    assert calls == [None]


def test_pyproject_declares_console_script() -> None:
    pyproject = Path("pyproject.toml")
    payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    scripts = payload["project"]["scripts"]
    assert scripts["zscripts"] == "zscripts.cli:main"


def test_built_zipapp_runs_guardrails(tmp_path: Path) -> None:
    bundle_path = build_cli_bundle(tmp_path / "zscripts.pyz")

    result = subprocess.run(
        [sys.executable, str(bundle_path), "guardrails"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "allowed_paths" in result.stdout


def test_built_zipapp_lists_adapters_json(tmp_path: Path) -> None:
    bundle_path = build_cli_bundle(tmp_path / "zscripts.pyz")

    result = subprocess.run(
        [sys.executable, str(bundle_path), "adapters", "--format", "json"],
        check=False,
        text=True,
        capture_output=True,
    )

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
