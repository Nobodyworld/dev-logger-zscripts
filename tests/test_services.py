from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pytest

from zscripts.application.services import ToolkitService
from zscripts.domain.interfaces import (
    AdapterRegistryProtocol,
    ExampleRepositoryProtocol,
    LogAdapterProtocol,
    RedactorProtocol,
    SandboxRunnerProtocol,
    SchemaValidatorProtocol,
)
from zscripts.domain.models import SandboxOptions, SandboxResult
from zscripts.schemas import LogIssue, NormalizedLog, TestSummary


class FakeAdapter(LogAdapterProtocol):
    def __init__(self) -> None:
        self.identifier = "fake"
        self.ecosystem = "python"
        self.description = "fake adapter"
        self.collected: list[Path] = []
        self.parsed: list[str] = []
        self.summarized: list[NormalizedLog] = []

    def collect(self, source: Path, sandbox: SandboxOptions | None = None) -> str:
        self.collected.append(source)
        return "raw"

    def parse(self, raw: str) -> NormalizedLog:
        self.parsed.append(raw)
        return NormalizedLog(
            tool="pytest",
            ecosystem="python",
            command="pytest",
            status="passed",
            summary="all good",
            timestamp=datetime.utcnow(),
            tests=TestSummary(passed=1, failed=0, skipped=0),
            errors=[LogIssue(message="boom", file="a.py", line=10)],
            warnings=[],
            artifacts=["coverage.xml"],
            metadata={"key": "value"},
        )

    def summarize(self, normalized: NormalizedLog) -> str:
        self.summarized.append(normalized)
        return "summary"


class SingleAdapterRegistry(AdapterRegistryProtocol):
    def __init__(self, adapter: LogAdapterProtocol) -> None:
        self._adapter = adapter
        self.resolutions: list[str] = []

    def available(self) -> Sequence[str]:
        return (self._adapter.identifier,)

    def resolve(self, key: str) -> LogAdapterProtocol:
        self.resolutions.append(key)
        if key != self._adapter.identifier:
            raise KeyError(key)
        return self._adapter


class RecordingValidator(SchemaValidatorProtocol):
    def __init__(self) -> None:
        self.validated: list[NormalizedLog] = []

    def validate(self, data: NormalizedLog) -> None:
        self.validated.append(data)


class RecordingRedactor(RedactorProtocol):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def redact(self, text: str) -> str:
        self.calls.append(text)
        return f"redacted:{text}"


class StaticExamples(ExampleRepositoryProtocol):
    def __init__(self, entries: Sequence[Path]) -> None:
        self._entries = list(entries)

    def list_examples(self, adapter: str | None = None) -> Sequence[Path]:
        return self._entries


class StubSandboxRunner(SandboxRunnerProtocol):
    def __init__(self) -> None:
        self.commands: list[Sequence[str]] = []
        self.result = SandboxResult(stdout="out", stderr="err", returncode=0)

    def run(self, command: Sequence[str]) -> SandboxResult:
        self.commands.append(tuple(command))
        return self.result


@pytest.fixture()
def service_components() -> dict[str, object]:
    adapter = FakeAdapter()
    registry = SingleAdapterRegistry(adapter)
    validator = RecordingValidator()
    redactor = RecordingRedactor()
    examples = StaticExamples([Path("examples/python/sample.log")])
    sandbox_runner = StubSandboxRunner()

    def factory(_: SandboxOptions) -> SandboxRunnerProtocol:
        return sandbox_runner

    service = ToolkitService(
        adapter_registry=registry,
        sandbox_factory=factory,
        schema_validator=validator,
        example_repository=examples,
        redactor=redactor,
        sandbox_options=SandboxOptions(),
        default_adapter=adapter.identifier,
    )
    return {
        "service": service,
        "adapter": adapter,
        "validator": validator,
        "redactor": redactor,
        "examples": examples,
        "sandbox": sandbox_runner,
        "registry": registry,
    }


def test_parse_logs_validates_output(service_components: dict[str, object]) -> None:
    service: ToolkitService = service_components["service"]  # type: ignore[assignment]
    validator: RecordingValidator = service_components["validator"]  # type: ignore[assignment]

    normalized = service.parse_logs(adapter_key=None, raw_text="payload")

    assert normalized.summary == "all good"
    assert validator.validated and validator.validated[0] is normalized


def test_collect_logs_runs_command_and_redacts(service_components: dict[str, object]) -> None:
    service: ToolkitService = service_components["service"]  # type: ignore[assignment]
    sandbox: StubSandboxRunner = service_components["sandbox"]  # type: ignore[assignment]
    redactor: RecordingRedactor = service_components["redactor"]  # type: ignore[assignment]

    payload = service.collect_logs(
        adapter_key=None,
        input_path=None,
        command=["echo", "hi"],
        stdin_fallback=None,
        redact=True,
    )

    assert sandbox.commands == [("echo", "hi")]
    assert redactor.calls == ["out\nerr"]
    assert payload == "redacted:out\nerr"


def test_collect_logs_omits_empty_sections(service_components: dict[str, object]) -> None:
    service: ToolkitService = service_components["service"]  # type: ignore[assignment]
    sandbox: StubSandboxRunner = service_components["sandbox"]  # type: ignore[assignment]
    redactor: RecordingRedactor = service_components["redactor"]  # type: ignore[assignment]

    sandbox.result = SandboxResult(stdout="only", stderr="", returncode=0)

    payload = service.collect_logs(
        adapter_key=None,
        input_path=None,
        command=["echo", "hi"],
        stdin_fallback=None,
        redact=False,
    )

    assert payload == "only"
    assert not redactor.calls


def test_collect_logs_includes_returncode_on_failure(
    service_components: dict[str, object]
) -> None:
    service: ToolkitService = service_components["service"]  # type: ignore[assignment]
    sandbox: StubSandboxRunner = service_components["sandbox"]  # type: ignore[assignment]

    sandbox.result = SandboxResult(stdout="", stderr="", returncode=7)

    payload = service.collect_logs(
        adapter_key=None,
        input_path=None,
        command=["echo", "hi"],
        stdin_fallback=None,
        redact=False,
    )

    assert payload == "Command exited with 7"
    assert sandbox.commands == [("echo", "hi")]


def test_guardrails_snapshot_reflects_sandbox_options(service_components: dict[str, object]) -> None:
    service: ToolkitService = service_components["service"]  # type: ignore[assignment]
    snapshot = service.guardrails_snapshot()

    assert snapshot["dangerous_mode"] is False
    assert snapshot["timeout_seconds"] == 120


def test_list_examples_returns_strings(service_components: dict[str, object]) -> None:
    service: ToolkitService = service_components["service"]  # type: ignore[assignment]

    entries = service.list_examples()

    assert entries == ["examples/python/sample.log"]


def test_explain_logs_includes_metadata(service_components: dict[str, object]) -> None:
    service: ToolkitService = service_components["service"]  # type: ignore[assignment]

    explanation = service.explain_logs(adapter_key=None, raw_text="payload")

    assert "Metadata:\n  - key: value" in explanation


def test_summarize_logs_resolves_adapter_once(service_components: dict[str, object]) -> None:
    service: ToolkitService = service_components["service"]  # type: ignore[assignment]
    registry: SingleAdapterRegistry = service_components["registry"]  # type: ignore[assignment]
    adapter: FakeAdapter = service_components["adapter"]  # type: ignore[assignment]

    summary = service.summarize_logs(adapter_key=None, raw_text="payload")

    assert summary == "summary"
    assert adapter.parsed == ["payload"]
    assert registry.resolutions == [adapter.identifier]
