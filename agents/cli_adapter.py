"""Structured metadata describing the zscripts CLI surface for agents."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CLIParameterSpec:
    """Describe a command-line parameter for agent tooling."""

    name: str
    type: str
    description: str
    required: bool = False
    default: str | bool | None = None
    choices: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        """Return a JSON-serialisable payload."""

        payload: dict[str, object] = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }
        if self.default is not None:
            payload["default"] = self.default
        if self.choices:
            payload["choices"] = list(self.choices)
        return payload


@dataclass(frozen=True, slots=True)
class CLICommandSpec:
    """Describe one CLI command including parameters and usage examples."""

    name: str
    summary: str
    parameters: tuple[CLIParameterSpec, ...]
    examples: tuple[str, ...]
    returns: str

    def to_payload(self) -> dict[str, object]:
        """Return a JSON-serialisable payload."""

        return {
            "name": self.name,
            "summary": self.summary,
            "parameters": [param.to_payload() for param in self.parameters],
            "examples": list(self.examples),
            "returns": self.returns,
        }


GLOBAL_PARAMETERS: tuple[CLIParameterSpec, ...] = (
    CLIParameterSpec(
        name="config",
        type="path",
        description="Path to a configuration file containing ToolkitConfig overrides.",
    ),
    CLIParameterSpec(
        name="set",
        type="string",
        description="Repeatable KEY=VALUE overrides applied on top of configuration files.",
    ),
    CLIParameterSpec(
        name="adapter",
        type="string",
        description="Preferred adapter identifier when multiple integrations are available.",
    ),
    CLIParameterSpec(
        name="enable_telemetry",
        type="boolean",
        description="Force-enable or disable telemetry for the current invocation.",
        default=False,
    ),
    CLIParameterSpec(
        name="log_level",
        type="string",
        description="Override the configured logging level (e.g., INFO, DEBUG).",
    ),
    CLIParameterSpec(
        name="log_format",
        type="string",
        description="Select structured JSON logging or plaintext output.",
        choices=("text", "json"),
    ),
)


def _collect_params() -> tuple[CLIParameterSpec, ...]:
    return (
        CLIParameterSpec(
            name="input",
            type="path",
            description="Optional path to a log file to ingest instead of executing a command.",
        ),
        CLIParameterSpec(
            name="command",
            type="string[]",
            description="Command to execute within the sandbox when capturing live output.",
        ),
        CLIParameterSpec(
            name="redact",
            type="boolean",
            description="Toggle automatic redaction for collected payloads.",
            default=False,
        ),
    )


def _parse_params() -> tuple[CLIParameterSpec, ...]:
    return (
        CLIParameterSpec(
            name="input",
            type="path",
            description="Path to the raw log file that should be parsed into the normalised schema.",
        ),
        CLIParameterSpec(
            name="command",
            type="string[]",
            description="Command to run when capturing logs prior to parsing.",
        ),
    )


def _report_params() -> tuple[CLIParameterSpec, ...]:
    return (
        CLIParameterSpec(
            name="input",
            type="path",
            description="Log file to summarize via the report generator.",
        ),
        CLIParameterSpec(
            name="command",
            type="string[]",
            description="Optional command executed to produce the report input inline.",
        ),
        CLIParameterSpec(
            name="format",
            type="string",
            description="Desired report format (defaults to configuration).",
            choices=("json", "markdown"),
        ),
        CLIParameterSpec(
            name="output",
            type="path",
            description="File destination for the rendered report (stdout always emits results).",
        ),
        CLIParameterSpec(
            name="fail_on",
            type="string",
            description="Severity threshold that forces a non-zero exit code.",
            choices=("never", "warnings", "errors"),
        ),
        CLIParameterSpec(
            name="redact",
            type="boolean",
            description="Control whether report sections are redacted prior to emission.",
        ),
    )


def _diagnostics_params() -> tuple[CLIParameterSpec, ...]:
    return (
        CLIParameterSpec(
            name="format",
            type="string",
            description="Diagnostics payload format (JSON for automation, text for humans).",
            default="json",
            choices=("json", "text"),
        ),
        CLIParameterSpec(
            name="output",
            type="path",
            description="Optional file path to write diagnostics output.",
        ),
        CLIParameterSpec(
            name="include_metrics",
            type="boolean",
            description="Include Prometheus text-format metrics in the diagnostics bundle.",
            default=False,
        ),
    )


def _extensions_params() -> tuple[CLIParameterSpec, ...]:
    return (
        CLIParameterSpec(
            name="output_format",
            type="string",
            description="Format for extension listings when inspecting installed hooks.",
            default="text",
            choices=("text", "json"),
        ),
        CLIParameterSpec(
            name="extensions_command",
            type="string",
            description="Sub-command executed under the extensions namespace (e.g., scaffold).",
        ),
    )


def _summarize_params() -> tuple[CLIParameterSpec, ...]:
    return (
        CLIParameterSpec(
            name="input",
            type="path",
            description="Optional path to a log file that should be summarized.",
        ),
        CLIParameterSpec(
            name="command",
            type="string[]",
            description="Command to execute in the sandbox before summarizing logs.",
        ),
        CLIParameterSpec(
            name="redact",
            type="boolean",
            description="Apply configured redaction rules to the generated summary.",
            default=False,
        ),
    )


def _explain_params() -> tuple[CLIParameterSpec, ...]:
    return (
        CLIParameterSpec(
            name="input",
            type="path",
            description="Optional path to a log file that should be explained.",
        ),
        CLIParameterSpec(
            name="command",
            type="string[]",
            description="Command to execute in the sandbox before generating an explanation.",
        ),
        CLIParameterSpec(
            name="redact",
            type="boolean",
            description="Apply configured redaction rules to the explanation output.",
            default=False,
        ),
    )


def _redact_params() -> tuple[CLIParameterSpec, ...]:
    return (
        CLIParameterSpec(
            name="input",
            type="path",
            description="Optional path to a log file that should be redacted.",
        ),
        CLIParameterSpec(
            name="command",
            type="string[]",
            description="Command to execute when capturing logs for redaction.",
        ),
    )


def _examples_params() -> tuple[CLIParameterSpec, ...]:
    return (
        CLIParameterSpec(
            name="format",
            type="string",
            description="Format for listing examples (text for humans, JSON for automation).",
            default="text",
            choices=("text", "json"),
        ),
    )


CLI_COMMANDS: tuple[CLICommandSpec, ...] = (
    CLICommandSpec(
        name="collect",
        summary="Collect raw logs from files or sandboxed commands.",
        parameters=_collect_params(),
        examples=(
            "python -m zscripts collect --input ./logs/latest.log",
            "python -m zscripts collect --command pytest --redact",
        ),
        returns="Exit code 0 on success; writes collected data to stdout or configured destinations.",
    ),
    CLICommandSpec(
        name="parse",
        summary="Parse logs into the normalised schema for downstream tooling.",
        parameters=_parse_params(),
        examples=(
            "python -m zscripts parse --input ./logs/latest.log",
            "python -m zscripts parse --command pytest -q",
        ),
        returns="Exit code 0 on success; emits JSON payloads to stdout or files.",
    ),
    CLICommandSpec(
        name="guardrails",
        summary="Display sandbox guardrail settings inferred from configuration.",
        parameters=(),
        examples=("python -m zscripts guardrails",),
        returns="Exit code 0 on success; prints guardrail configuration to stdout.",
    ),
    CLICommandSpec(
        name="report",
        summary="Generate build/test summaries with optional redaction and severity gating.",
        parameters=_report_params(),
        examples=(
            "python -m zscripts report --input ./logs/latest.log --format markdown",
            "python -m zscripts report --command pytest -q --fail-on errors",
        ),
        returns="Exit code 0 on success; writes reports to stdout and optionally disk.",
    ),
    CLICommandSpec(
        name="summarize",
        summary="Produce concise summaries for collected logs.",
        parameters=_summarize_params(),
        examples=(
            "python -m zscripts summarize --input ./logs/latest.log",
            "python -m zscripts summarize --command pytest --redact",
        ),
        returns="Exit code 0 on success; prints summaries to stdout for further use.",
    ),
    CLICommandSpec(
        name="explain",
        summary="Generate detailed explanations for collected logs.",
        parameters=_explain_params(),
        examples=(
            "python -m zscripts explain --input ./logs/latest.log",
            "python -m zscripts explain --command pytest --redact",
        ),
        returns="Exit code 0 on success; writes explanations to stdout for troubleshooting.",
    ),
    CLICommandSpec(
        name="redact",
        summary="Apply configured redaction rules to log content.",
        parameters=_redact_params(),
        examples=(
            "python -m zscripts redact --input ./logs/latest.log",
            "python -m zscripts redact --command pytest -q",
        ),
        returns="Exit code 0 on success; prints redacted log output to stdout.",
    ),
    CLICommandSpec(
        name="examples",
        summary="List bundled example log files for available adapters.",
        parameters=_examples_params(),
        examples=(
            "python -m zscripts examples",
            "python -m zscripts --adapter go examples --format json",
        ),
        returns="Exit code 0 on success; emits example paths for discovery workflows.",
    ),
    CLICommandSpec(
        name="diagnostics",
        summary="Collect runtime diagnostics including telemetry and extension metadata.",
        parameters=_diagnostics_params(),
        examples=(
            "python -m zscripts diagnostics --format text",
            "python -m zscripts diagnostics --include-metrics --output diagnostics.json",
        ),
        returns="Exit code 0 on success; emits diagnostics payloads for troubleshooting.",
    ),
    CLICommandSpec(
        name="extensions",
        summary="Inspect or scaffold toolkit extensions.",
        parameters=_extensions_params(),
        examples=(
            "python -m zscripts extensions --output-format json",
            "python -m zscripts extensions scaffold demo_extension --directory ./extensions",
        ),
        returns="Exit code 0 on success; prints extension inventory or scaffold results.",
    ),
)


def get_cli_command_specs() -> tuple[CLICommandSpec, ...]:
    """Return the structured metadata for the supported CLI commands."""

    return CLI_COMMANDS


def export_cli_metadata() -> dict[str, object]:
    """Return a payload suitable for publishing agent metadata documents."""

    return {
        "commands": [spec.to_payload() for spec in get_cli_command_specs()],
        "global_parameters": [parameter.to_payload() for parameter in GLOBAL_PARAMETERS],
    }
