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


class RecordingSandboxFactory:
    def __init__(self, runner: SandboxRunnerProtocol) -> None:
        self._runner = runner
        self.calls = 0

    def __call__(self, _: SandboxOptions) -> SandboxRunnerProtocol:
        self.calls += 1
        return self._runner


@pytest.fixture()
def service_components() -> dict[str, object]:
    adapter = FakeAdapter()
    registry = SingleAdapterRegistry(adapter)
    validator = RecordingValidator()
    redactor = RecordingRedactor()
    examples = StaticExamples([Path("examples/python/sample.log")])
    sandbox_runner = StubSandboxRunner()
    factory = RecordingSandboxFactory(sandbox_runner)

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
        "sandbox_factory": factory,
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


def test_collect_logs_reuses_cached_sandbox_runner(
    service_components: dict[str, object]
) -> None:
    service: ToolkitService = service_components["service"]  # type: ignore[assignment]
    sandbox: StubSandboxRunner = service_components["sandbox"]  # type: ignore[assignment]
    factory: RecordingSandboxFactory = service_components["sandbox_factory"]  # type: ignore[assignment]

    service.collect_logs(
        adapter_key=None,
        input_path=None,
        command=["echo", "first"],
        stdin_fallback=None,
        redact=False,
    )
    service.collect_logs(
        adapter_key=None,
        input_path=None,
        command=["echo", "second"],
        stdin_fallback=None,
        redact=False,
    )

    assert sandbox.commands == [("echo", "first"), ("echo", "second")]
    assert factory.calls == 1


def test_collect_logs_requires_a_source(service_components: dict[str, object]) -> None:
    service: ToolkitService = service_components["service"]  # type: ignore[assignment]

    with pytest.raises(ValueError, match="No log source provided"):
        service.collect_logs(
            adapter_key=None,
            input_path=None,
            command=None,
            stdin_fallback=None,
            redact=False,
        )


def test_collect_logs_rejects_empty_stdin(service_components: dict[str, object]) -> None:
    service: ToolkitService = service_components["service"]  # type: ignore[assignment]

    with pytest.raises(ValueError, match="STDIN data was empty"):
        service.collect_logs(
            adapter_key=None,
            input_path=None,
            command=None,
            stdin_fallback="   ",
            redact=False,
        )


def test_collect_logs_rejects_empty_command_sequence(
    service_components: dict[str, object]
) -> None:
    service: ToolkitService = service_components["service"]  # type: ignore[assignment]

    with pytest.raises(ValueError, match="Command must include an executable"):
        service.collect_logs(
            adapter_key=None,
            input_path=None,
            command=[],
            stdin_fallback=None,
            redact=False,
        )


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


def test_generate_report_combines_artifacts(service_components: dict[str, object]) -> None:
    service: ToolkitService = service_components["service"]  # type: ignore[assignment]

    bundle = service.generate_report(adapter_key=None, raw_text="payload", redact=False)

    assert bundle.summary == "summary"
    assert "Tool: pytest" in bundle.explanation
    assert bundle.guardrails["dangerous_mode"] is False
    assert bundle.collected_text == "payload"
    assert bundle.redacted_text is None
    assert bundle.normalized.summary == "all good"


def test_generate_report_applies_redaction(service_components: dict[str, object]) -> None:
    service: ToolkitService = service_components["service"]  # type: ignore[assignment]
    redactor: RecordingRedactor = service_components["redactor"]  # type: ignore[assignment]

    bundle = service.generate_report(adapter_key=None, raw_text="payload", redact=True)

    assert bundle.summary.startswith("redacted:")
    assert bundle.explanation.startswith("redacted:")
    assert bundle.redacted_text == "redacted:payload"
    # Summary, explanation, and source payload should each be redacted once.
    raw_explanation = bundle.explanation.removeprefix("redacted:")
    assert redactor.calls == ["summary", raw_explanation, "payload"]
