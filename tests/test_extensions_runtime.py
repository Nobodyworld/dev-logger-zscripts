from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from zscripts import get_default_config
from zscripts.extensions import scaffold_extension
from zscripts.extensions.base import ExtensionContext
from zscripts.extensions.examples.plugin_echo import EchoExtension
from zscripts.extensions.manifest import build_manifest
from zscripts.extensions.registry import ExtensionLoadError, load_extensions
from zscripts.infrastructure.adapters import AdapterRegistry
from zscripts.observability.instrumentation import InstrumentationManager
from zscripts.observability.logging import get_logger
from zscripts.observability.telemetry import TelemetryManager, TelemetrySettings


def _make_context() -> ExtensionContext:
    telemetry = TelemetryManager(TelemetrySettings())
    instrumentation = InstrumentationManager(telemetry=telemetry, component="test")
    return ExtensionContext(
        config=get_default_config(),
        adapter_registry=AdapterRegistry(),
        telemetry=telemetry,
        instrumentation=instrumentation,
        logger=get_logger("extensions.test"),
    )


def test_load_extensions_records_metrics() -> None:
    context = _make_context()
    loaded = load_extensions(["zscripts.extensions.examples.plugin_echo"], context=context)
    assert loaded and isinstance(loaded[0], EchoExtension)
    gauge = context.instrumentation.gauge(
        "zscripts_extensions_active",
        "Number of active toolkit extensions.",
    )
    samples = list(gauge.samples())
    assert samples
    _, value = samples[0]
    assert value == 1
    assert "echo" in context.manifests
    manifest = context.manifests["echo"]
    assert manifest.module == "zscripts.extensions.examples.plugin_echo"
    assert "cli" in manifest.capabilities


def test_load_extensions_errors_on_missing_module() -> None:
    context = _make_context()
    with pytest.raises(ExtensionLoadError):
        load_extensions(["does.not.exist"], context=context)


def test_load_extensions_requires_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _make_context()
    module = ModuleType("fake_extension")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    try:
        with pytest.raises(ExtensionLoadError):
            load_extensions([module.__name__], context=context)
    finally:
        sys.modules.pop(module.__name__, None)


def test_toolkit_extension_context_accessor() -> None:
    context = _make_context()
    extension = EchoExtension()
    extension.on_load(context)
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")
    extension.register_cli(subparsers, context)
    assert extension.context is context
    context.manifests[extension.name] = build_manifest(
        extension=extension,
        module=extension.__class__.__module__,
        entrypoint=f"{extension.__class__.__module__}:{extension.__class__.__name__}",
        default_name=extension.name,
    )
    assert extension.manifest is not None


def test_scaffold_extension_generates_template(tmp_path: Path) -> None:
    target = scaffold_extension("sample_demo", tmp_path)
    contents = target.read_text(encoding="utf-8")
    assert "class SampleDemoExtension" in contents
    assert "instrumentation.operation" in contents
    with pytest.raises(FileExistsError):
        scaffold_extension("sample_demo", tmp_path)
    with pytest.raises(ValueError):
        scaffold_extension("1bad", tmp_path)


def test_echo_extension_handle_cli_outputs_message(capsys: pytest.CaptureFixture[str]) -> None:
    context = _make_context()
    extension = EchoExtension()
    extension.on_load(context)
    extension.handle_cli(SimpleNamespace(message="hello"), service=None)
    output = capsys.readouterr().out.strip()
    assert output == "hello"
