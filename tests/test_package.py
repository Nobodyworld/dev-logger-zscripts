"""Smoke tests for top-level package helpers and entry points."""

from __future__ import annotations

import runpy

import pytest

import zscripts
from zscripts import get_default_config, get_version


def test_get_version_falls_back_when_metadata_missing(monkeypatch: pytest.MonkeyPatch) -> None:
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
