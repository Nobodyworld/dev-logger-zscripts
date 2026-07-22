"""Tests covering infrastructure adapter, sandbox, and schema layers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import ValidationError

from zscripts.domain.models import SandboxOptions
from zscripts.infrastructure import adapters as adapters_module
from zscripts.infrastructure import sandbox as sandbox_module
from zscripts.infrastructure import schema as schema_module
from zscripts.infrastructure.examples import FileSystemExampleRepository
from zscripts.schemas.normalized import NormalizedLog


def test_adapter_registry_wraps_concrete_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, int] = {"available": 0, "get": 0}

    class DummyAdapter:
        identifier = "dummy"
        ecosystem = "python"
        description = "Dummy adapter"

        def __init__(self) -> None:
            self.collect_args: list[object] = []

        def collect(self, source: Path, settings: object) -> str:
            self.collect_args.append(settings)
            return f"collected:{source.name}"

        def parse(self, raw: str) -> str:
            return f"parsed:{raw}"

        def summarize(self, normalized: NormalizedLog) -> str:
            return normalized.summary

    adapter_instance = DummyAdapter()

    def fake_available() -> list[str]:
        calls["available"] += 1
        return ["dummy"]

    def fake_get(name: str) -> DummyAdapter:
        calls["get"] += 1
        assert name == "dummy"
        return adapter_instance

    monkeypatch.setattr(adapters_module, "available_adapters", fake_available)
    monkeypatch.setattr(adapters_module, "get_adapter", fake_get)

    registry = adapters_module.AdapterRegistry()
    assert registry.available() == ("dummy",)
    sandbox = SandboxOptions(
        allowed_paths=(Path("/tmp"),),
        timeout_seconds=5,
        dangerous_mode=True,
        env_allowlist=("PATH", "PYTHONPATH"),
    )
    wrapper = registry.resolve("dummy")
    again = registry.resolve("dummy")
    assert wrapper is again
    result = wrapper.collect(Path("/tmp/example.log"), sandbox)
    assert result == "collected:example.log"
    settings = adapter_instance.collect_args[-1]
    assert settings.allowed_paths == sandbox.allowed_paths
    assert settings.timeout_seconds == sandbox.timeout_seconds
    assert settings.dangerous_mode == sandbox.dangerous_mode
    parsed = wrapper.parse("payload")
    assert parsed == "parsed:payload"
    normalized = NormalizedLog(
        tool="pytest",
        ecosystem="python",
        command="pytest -q",
        status="passed",
        summary="ok",
        timestamp=datetime.utcnow(),
    )
    assert wrapper.summarize(normalized) == "ok"
    assert calls["get"] == 1


def test_file_system_example_repository_filters(tmp_path: Path) -> None:
    base = tmp_path / "examples"
    python_dir = base / "python"
    go_dir = base / "go"
    python_dir.mkdir(parents=True)
    go_dir.mkdir()
    sample = python_dir / "demo.log"
    sample.write_text("demo", encoding="utf-8")
    (python_dir / "notes.txt").write_text("ignore", encoding="utf-8")
    (go_dir / "skip.log").write_text("skip", encoding="utf-8")

    repo = FileSystemExampleRepository(base)
    all_examples = repo.list_examples()
    assert all_examples == [go_dir / "skip.log", sample]
    python_examples = repo.list_examples(adapter="python")
    assert python_examples == [sample]
    go_examples = repo.list_examples(adapter="go")
    assert go_examples == [go_dir / "skip.log"]
    assert repo.list_examples(adapter="rust") == []


def test_file_system_example_repository_handles_missing_base(tmp_path: Path) -> None:
    repo = FileSystemExampleRepository(tmp_path / "missing")
    assert repo.list_examples() == []


def test_sandbox_command_runner_wraps_results(monkeypatch: pytest.MonkeyPatch) -> None:
    completed = SimpleNamespace(stdout="out", stderr="err", returncode=3)

    class DummyRunner:
        def __init__(self, settings: object) -> None:
            self.settings = settings

        def run(self, command: tuple[str, ...]) -> SimpleNamespace:
            assert command == ("echo", "hi")
            return completed

    monkeypatch.setattr(sandbox_module, "SandboxRunner", DummyRunner)

    options = SandboxOptions(timeout_seconds=9)
    runner = sandbox_module.build_sandbox_runner(options)
    assert isinstance(runner, sandbox_module.SandboxCommandRunner)
    result = runner.run(("echo", "hi"))
    assert result.stdout == "out"
    assert result.stderr == "err"
    assert result.returncode == 3


def test_json_schema_validator_uses_jsonschema(monkeypatch: pytest.MonkeyPatch) -> None:
    invoked: dict[str, object] = {}

    def fake_validate(*, instance: dict[str, object], schema: dict[str, object]) -> None:
        invoked["instance"] = instance
        invoked["schema"] = schema

    monkeypatch.setattr(schema_module, "jsonschema", SimpleNamespace(validate=fake_validate))
    monkeypatch.setattr(schema_module, "load_normalized_schema", lambda: {"type": "object"})

    validator = schema_module.JsonSchemaValidator()
    payload = NormalizedLog(
        tool="pytest",
        ecosystem="python",
        command="pytest",
        status="passed",
        summary="ok",
        timestamp=datetime.utcnow(),
    )
    validator.validate(payload)
    assert invoked["schema"] == {"type": "object"}
    assert invoked["instance"]["tool"] == "pytest"


def test_json_schema_validator_rejects_invalid_normalized_payload() -> None:
    validator = schema_module.JsonSchemaValidator()
    payload = NormalizedLog(
        tool="pytest",
        ecosystem="python",
        command="pytest",
        status="passed",
        summary="ok",
        timestamp=datetime.utcnow(),
        metadata={"attempt": 1},
    )
    with pytest.raises(ValidationError):
        validator.validate(payload)
