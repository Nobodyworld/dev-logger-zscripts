from __future__ import annotations

import argparse
import py_compile
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

import scripts.scaffold_module as scaffold_module
from zscripts import get_default_config
from zscripts.extensions import ExtensionHookRegistry, scaffold_extension
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
    hook_registry = ExtensionHookRegistry(instrumentation)
    return ExtensionContext(
        config=get_default_config(),
        adapter_registry=AdapterRegistry(),
        telemetry=telemetry,
        instrumentation=instrumentation,
        logger=get_logger("extensions.test"),
        hook_registry=hook_registry,
        health_checks=telemetry.health_checks,
    )


def test_load_extensions_records_metrics() -> None:
    context = _make_context()
    manager = load_extensions(["zscripts.extensions.examples.plugin_echo"], context=context)
    assert len(manager) == 1
    assert isinstance(manager[0], EchoExtension)
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


def test_extension_hook_registry_records_callbacks() -> None:
    context = _make_context()
    extension = EchoExtension()
    extension.on_load(context)

    called: list[str] = []

    def _callback(*args: object, **kwargs: object) -> None:
        called.append("hooked")

    extension.register_hook("service_ready", _callback)
    manager = load_extensions([], context=context)
    outcomes = manager.emit("service_ready")
    assert outcomes == [None]
    assert called == ["hooked"]


def test_extension_manager_hook_summary() -> None:
    context = _make_context()
    extension = EchoExtension()
    extension.on_load(context)
    context.hook_registry.register("service_ready", lambda: None, extension=extension.name)
    manager = load_extensions([], context=context)
    summary = manager.hook_summary()
    assert summary.get("service_ready") == 1


def test_health_monitor_extension_registers_health_check() -> None:
    context = _make_context()
    manager = load_extensions(["zscripts.extensions.examples.plugin_health"], context=context)
    assert len(manager) == 1
    snapshot = context.health_checks.snapshot()
    assert snapshot["summary"]["total"] == 1
    entry = snapshot["checks"]["extensions.health_monitor"]
    assert entry["status"] == "ok"
    assert entry["kind"] == "extension"


def test_scaffold_extension_generates_template(tmp_path: Path) -> None:
    target = scaffold_extension("sample_demo", tmp_path)
    contents = target.read_text(encoding="utf-8")
    assert "class SampleDemoExtension" in contents
    assert "instrumentation.operation" in contents
    with pytest.raises(FileExistsError):
        scaffold_extension("sample_demo", tmp_path)
    with pytest.raises(ValueError):
        scaffold_extension("1bad", tmp_path)


def test_scaffold_module_health(tmp_path: Path) -> None:
    target_dir = tmp_path / "checks"
    exit_code = scaffold_module.main(
        [
            "health",
            "demo_probe",
            "--directory",
            str(target_dir),
            "--description",
            "Demo health check",
        ]
    )
    assert exit_code == 0
    module_path = target_dir / "demo_probe.py"
    contents = module_path.read_text(encoding="utf-8")
    assert "registry.register" in contents
    assert "Demo health check" in contents
    py_compile.compile(str(module_path), doraise=True)


def test_echo_extension_handle_cli_outputs_message(capsys: pytest.CaptureFixture[str]) -> None:
    context = _make_context()
    extension = EchoExtension()
    extension.on_load(context)
    extension.handle_cli(SimpleNamespace(message="hello"), service=None)
    output = capsys.readouterr().out.strip()
    assert output == "hello"
