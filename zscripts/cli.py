"""Command-line interface entry point for the zscripts toolkit."""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from zscripts import get_default_config
from zscripts.application.io_utils import OutputPathError, atomic_write_text
from zscripts.application.report_formatters import get_report_formatter
from zscripts.application.services import ToolkitService
from zscripts.config import ToolkitConfig
from zscripts.configuration import (
    ConfigurationError,
    load_toolkit_config,
    parse_override_pairs,
)
from zscripts.extensions import (
    ExtensionContext,
    ExtensionHookRegistry,
    ExtensionLoadError,
    ExtensionManager,
    load_extensions,
)
from zscripts.extensions.scaffolding import scaffold_extension
from zscripts.infrastructure import build_toolkit_service
from zscripts.infrastructure.adapters import AdapterRegistry
from zscripts.observability.diagnostics import collect_runtime_diagnostics
from zscripts.observability.logging import bind_correlation_id, get_logger
from zscripts.observability.telemetry import TelemetryManager, TelemetrySettings

if TYPE_CHECKING:  # pragma: no cover - import for static typing only
    from zscripts.observability.instrumentation import InstrumentationManager, OperationResult


class _HelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    """Pretty-print help text while preserving manual newlines."""


_CLI_LOGGER = get_logger("cli")

_SEVERITY_ORDER: dict[str, int] = {"ok": 0, "warning": 1, "error": 2}


def _should_fail(policy: str, severity: str) -> bool:
    """Return True when ``severity`` meets or exceeds the ``policy`` threshold."""

    normalized_policy = policy.lower()
    normalized_severity = severity.lower()
    rank = _SEVERITY_ORDER.get(normalized_severity, _SEVERITY_ORDER["error"])
    if normalized_policy == "never":
        return False
    if normalized_policy == "warnings":
        return rank >= _SEVERITY_ORDER["warning"]
    if normalized_policy == "errors":
        return rank >= _SEVERITY_ORDER["error"]
    # Unknown policy values are guarded earlier, but default to failure for safety.
    return True


@dataclass(slots=True)
class _CliRuntime:
    """Aggregate telemetry dependencies for CLI command execution."""

    telemetry: TelemetryManager
    instrumentation: InstrumentationManager
    correlation_id: str


def _build_global_parser() -> argparse.ArgumentParser:
    """Parser capturing global options before extension registration."""

    parser = argparse.ArgumentParser(add_help=False)
    _add_global_arguments(parser)
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the zscripts CLI."""

    raw_args = argv if argv is not None else sys.argv[1:]
    registry = AdapterRegistry()

    global_parser = _build_global_parser()
    global_args, _ = global_parser.parse_known_args(raw_args)

    base_config = get_default_config()
    try:
        overrides = parse_override_pairs(global_args.override_pairs)
        config_path = Path(global_args.config).expanduser() if global_args.config else None
        config = load_toolkit_config(
            path=config_path,
            overrides=overrides,
            base=base_config,
        )
    except ConfigurationError as exc:
        _fail(str(exc))

    _merge_cli_toggles(config, global_args)

    telemetry = TelemetryManager(
        TelemetrySettings(
            enabled=config.telemetry_enabled,
            host=config.telemetry_host,
            port=config.telemetry_port,
            log_level=config.log_level,
            log_format=config.log_format,
        )
    )
    telemetry.start()
    cli_instrumentation = telemetry.create_instrumentation(component="cli")
    extension_instrumentation = telemetry.create_instrumentation(component="extensions")

    correlation_id = uuid.uuid4().hex
    runtime = _CliRuntime(
        telemetry=telemetry,
        instrumentation=cli_instrumentation,
        correlation_id=correlation_id,
    )
    try:
        with bind_correlation_id(correlation_id):
            hook_registry = ExtensionHookRegistry(extension_instrumentation)
            extension_context = ExtensionContext(
                config=config,
                adapter_registry=registry,
                telemetry=telemetry,
                instrumentation=extension_instrumentation,
                logger=get_logger("extensions"),
                hook_registry=hook_registry,
            )
            try:
                extensions = load_extensions(config.extensions, context=extension_context)
            except ExtensionLoadError as exc:
                _fail(str(exc))

            _prepare_and_execute(
                raw_args,
                runtime,
                extension_context,
                extensions,
            )
    finally:
        telemetry.stop()


def _build_parser(  # noqa: PLR0915 - parser assembly is intentionally verbose
    adapter_choices: Sequence[str],
    extensions: Sequence[object],
    extension_context: ExtensionContext,
) -> argparse.ArgumentParser:
    """Construct the argument parser for the CLI."""

    parser = argparse.ArgumentParser(
        description="Universal build log toolkit",
        formatter_class=_HelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples:
              python cli.py collect --command pytest --redact
              python cli.py parse --adapter python --input examples/python/sample.log
            """
        ).strip(),
    )
    _add_global_arguments(parser)
    parser.add_argument(
        "--adapter",
        help="Adapter to use when parsing logs.",
        choices=adapter_choices,
    )
    parser.add_argument(
        "--dangerous",
        action="store_true",
        default=None,
        help="Disable sandbox guardrails (use with caution).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="Collect log output")
    collect_parser.add_argument("--input", help="Path to existing log file")
    collect_parser.add_argument(
        "--command",
        dest="command_args",
        nargs=argparse.REMAINDER,
        help="Command to execute inside the sandbox (e.g. pytest -q)",
    )
    collect_parser.add_argument("--output", help="Write collected logs to this path")
    collect_parser.add_argument(
        "--redact",
        action="store_true",
        help="Apply default redaction patterns to collected logs.",
    )
    collect_parser.set_defaults(func=_handle_collect)

    parse_parser = subparsers.add_parser("parse", help="Parse raw logs into JSON")
    parse_parser.add_argument("--input", help="Path to the log file (defaults to STDIN)")
    parse_parser.add_argument("--output", help="Destination for normalized JSON")
    parse_parser.set_defaults(func=_handle_parse)

    summarize_parser = subparsers.add_parser("summarize", help="Produce a compact summary")
    summarize_parser.add_argument("--input", help="Path to the log file (defaults to STDIN)")
    summarize_parser.set_defaults(func=_handle_summarize)

    diagnostics_parser = subparsers.add_parser(
        "diagnostics",
        help="Capture a telemetry and extension diagnostics snapshot.",
    )
    diagnostics_parser.add_argument(
        "--include-metrics",
        action="store_true",
        help="Embed Prometheus metrics text in the JSON payload.",
    )
    diagnostics_parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format for the diagnostics snapshot.",
    )
    diagnostics_parser.add_argument(
        "--output",
        help="Optional file to write diagnostics to (defaults to STDOUT).",
    )
    diagnostics_parser.set_defaults(func=_handle_diagnostics)

    explain_parser = subparsers.add_parser("explain", help="Produce a detailed explanation")
    explain_parser.add_argument("--input", help="Path to the log file (defaults to STDIN)")
    explain_parser.set_defaults(func=_handle_explain)

    guardrails_parser = subparsers.add_parser("guardrails", help="Inspect sandbox guardrails")
    guardrails_parser.set_defaults(func=_handle_guardrails)

    redact_parser = subparsers.add_parser("redact", help="Redact secrets from logs")
    redact_parser.add_argument("--input", help="Path to the log file (defaults to STDIN)")
    redact_parser.add_argument("--output", help="Destination for redacted logs")
    redact_parser.set_defaults(func=_handle_redact)

    examples_parser = subparsers.add_parser("examples", help="List bundled example logs")
    examples_parser.add_argument("--adapter", help="Filter examples by adapter")
    examples_parser.set_defaults(func=_handle_examples)

    extensions_parser = subparsers.add_parser("extensions", help="Manage extensions")
    extensions_parser.add_argument("--output", help="Destination for the extension list")
    extensions_parser.add_argument(
        "--output-format",
        dest="output_format",
        choices=("table", "json"),
        default="table",
        help="Format for listing extension metadata.",
    )
    extensions_parser.set_defaults(func=_handle_extensions_list)
    extensions_subparsers = extensions_parser.add_subparsers(
        dest="extensions_subcommand",
        required=False,
    )
    list_parser = extensions_subparsers.add_parser("list", help="List loaded extensions")
    list_parser.add_argument(
        "--output-format",
        dest="output_format_override",
        choices=("table", "json"),
        default=None,
        help="Override the list output format (defaults to the parent command value).",
    )
    list_parser.set_defaults(func=_handle_extensions_list)
    scaffold_parser = extensions_subparsers.add_parser(
        "scaffold",
        help="Generate a starter extension module.",
    )
    scaffold_parser.add_argument("name", help="Extension module name (snake_case)")
    scaffold_parser.add_argument(
        "--directory",
        default="zscripts/extensions",
        help="Directory where the extension module should be created.",
    )
    scaffold_parser.set_defaults(func=_handle_extensions_scaffold)

    report_parser = subparsers.add_parser("report", help="Generate a comprehensive report")
    report_parser.add_argument("--input", help="Path to the log file (defaults to STDIN)")
    report_parser.add_argument("--output", help="Destination for the rendered report")
    report_parser.add_argument(
        "--format",
        dest="report_format",
        choices=("json", "markdown"),
        help="Report output format (defaults to configuration).",
    )
    report_parser.add_argument(
        "--redact",
        dest="report_redact",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable redaction of textual fields (defaults to configuration).",
    )
    report_parser.add_argument(
        "--fail-on",
        dest="report_fail_on",
        choices=("never", "warnings", "errors"),
        help="Exit with status 1 when severity meets or exceeds this threshold.",
    )
    report_parser.set_defaults(func=_handle_report)

    for extension in extensions:
        register = getattr(extension, "register_cli", None)
        if callable(register):
            register(subparsers, extension_context)

    return parser


def _add_global_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        help="Path to a TOML or JSON configuration file.",
    )
    parser.add_argument(
        "--set",
        dest="override_pairs",
        action="append",
        metavar="KEY=VALUE",
        help="Override configuration values (repeatable).",
    )
    parser.add_argument(
        "--enable-telemetry",
        action="store_true",
        default=None,
        help="Expose the HTTP health and metrics server.",
    )
    parser.add_argument(
        "--telemetry-host",
        help="Host/interface for the telemetry server.",
    )
    parser.add_argument(
        "--telemetry-port",
        type=int,
        help="Port for the telemetry server.",
    )
    parser.add_argument(
        "--log-level",
        help="Structured log level (e.g. INFO, DEBUG).",
    )
    parser.add_argument(
        "--log-format",
        choices=("text", "json"),
        help="Structured log format.",
    )


def _merge_cli_toggles(config: ToolkitConfig, args: argparse.Namespace) -> None:
    """Apply global CLI options to the active configuration object."""

    enable_flag = getattr(args, "enable_telemetry", None)
    if enable_flag is True:
        config.telemetry_enabled = True
    host = getattr(args, "telemetry_host", None)
    if host:
        config.telemetry_host = host
    port = getattr(args, "telemetry_port", None)
    if port is not None:
        config.telemetry_port = port
    level = getattr(args, "log_level", None)
    if level:
        config.log_level = level.upper()
    fmt = getattr(args, "log_format", None)
    if fmt:
        config.log_format = fmt.lower()


def _handle_collect(args: argparse.Namespace, service: ToolkitService) -> None:
    input_path = Path(args.input) if args.input else None
    command: Sequence[str] | None = None
    command_tokens = getattr(args, "command_args", None)
    if command_tokens is not None:
        if not command_tokens:
            _fail("Provide at least one argument after --command.")
        command = command_tokens
    stdin_payload = None
    if not command and not input_path:
        stdin_payload = sys.stdin.read()

    try:
        payload = service.collect_logs(
            adapter_key=args.adapter,
            input_path=input_path,
            command=command,
            stdin_fallback=stdin_payload,
            redact=bool(args.redact),
        )
    except ValueError as exc:
        _fail(str(exc))
    _write_output(payload, args.output)


def _handle_parse(args: argparse.Namespace, service: ToolkitService) -> None:
    raw_text = _load_input(args.input)
    normalized = service.parse_logs(adapter_key=args.adapter, raw_text=raw_text)
    payload = json.dumps(normalized.to_dict(), indent=2)
    _write_output(payload, args.output)


def _handle_summarize(args: argparse.Namespace, service: ToolkitService) -> None:
    raw_text = _load_input(args.input)
    summary = service.summarize_logs(adapter_key=args.adapter, raw_text=raw_text)
    print(summary)


def _handle_explain(args: argparse.Namespace, service: ToolkitService) -> None:
    raw_text = _load_input(args.input)
    explanation = service.explain_logs(adapter_key=args.adapter, raw_text=raw_text)
    print(explanation)


def _handle_guardrails(args: argparse.Namespace, service: ToolkitService) -> None:
    snapshot = service.guardrails_snapshot()
    print(json.dumps(snapshot, indent=2))


def _handle_redact(args: argparse.Namespace, service: ToolkitService) -> None:
    text = _load_input(args.input)
    payload = service.redact_text(text)
    _write_output(payload, args.output)


def _handle_examples(args: argparse.Namespace, service: ToolkitService) -> None:
    entries = service.list_examples(args.adapter)
    print("\n".join(entries))


def _handle_diagnostics(args: argparse.Namespace, service: ToolkitService) -> None:  # noqa: ARG001
    namespace = vars(args)
    runtime = cast(_CliRuntime, namespace["runtime"])
    manager = cast(ExtensionManager | None, namespace.get("extension_manager"))
    snapshot = collect_runtime_diagnostics(
        telemetry=runtime.telemetry,
        instrumentation=runtime.instrumentation,
        extensions=manager,
        include_metrics=bool(namespace.get("include_metrics", False)),
    )
    payload = snapshot.to_dict()
    if namespace.get("format", "json") == "text":
        rendered = _format_diagnostics_text(payload)
    else:
        rendered = json.dumps(payload, indent=2)
    _write_output(rendered, namespace.get("output"))


def _handle_extensions_list(args: argparse.Namespace, service: ToolkitService) -> None:
    loaded = getattr(args, "extensions_loaded", [])
    manifests = getattr(args, "extensions_manifest", {})
    output_format = (
        getattr(args, "output_format_override", None)
        or getattr(args, "output_format", "table")
    )
    if not loaded:
        payload = "[]" if output_format == "json" else "No extensions configured."
    elif output_format == "json":
        entries = []
        for extension in loaded:
            extension_name = getattr(extension, "name", extension.__class__.__name__)
            manifest = manifests.get(extension_name)
            if manifest is not None:
                entries.append(manifest.to_dict())
            else:
                entries.append(
                    {
                        "name": extension_name,
                        "module": extension.__class__.__module__,
                        "description": getattr(extension, "description", ""),
                        "entrypoint": f"{extension.__class__.__module__}:{extension.__class__.__name__}",
                        "version": getattr(extension, "version", None),
                        "capabilities": list(getattr(extension, "capabilities", ())),
                        "config_keys": list(getattr(extension, "config_keys", ())),
                    }
                )
        payload = json.dumps(entries, indent=2)
    else:
        lines = []
        for extension in loaded:
            extension_name = getattr(extension, "name", extension.__class__.__name__)
            manifest = manifests.get(extension_name)
            module_path = (
                manifest.module if manifest is not None else extension.__class__.__module__
            )
            description = (
                manifest.description
                if manifest is not None and manifest.description
                else getattr(extension, "description", "").strip()
            )
            version = (
                manifest.version
                if manifest is not None
                else getattr(extension, "version", None)
            )
            suffix = f" (v{version})" if version else ""
            lines.append(
                f"{extension_name}{suffix} [{module_path}]: "
                f"{description or 'No description provided.'}"
            )
        payload = "\n".join(lines)
    _write_output(payload, getattr(args, "output", None))


def _handle_extensions_scaffold(args: argparse.Namespace, service: ToolkitService) -> None:
    directory = Path(getattr(args, "directory", "zscripts/extensions")).expanduser()
    try:
        module_path = scaffold_extension(args.name, directory)
    except (ValueError, FileExistsError) as exc:
        _fail(str(exc))
    _CLI_LOGGER.info(
        "extensions.scaffold.created",
        extra={"path": str(module_path)},
    )
    print(module_path)


def _handle_report(args: argparse.Namespace, service: ToolkitService) -> None:
    raw_text = _load_input(args.input)
    bundle = service.generate_report(
        adapter_key=args.adapter,
        raw_text=raw_text,
        redact=getattr(args, "resolved_report_redact", False),
    )
    formatter_name = getattr(args, "resolved_report_format", "json")
    try:
        formatter = get_report_formatter(formatter_name)
    except ValueError as exc:
        _fail(str(exc))
    payload = formatter(bundle)
    _write_output(payload, getattr(args, "output", None))
    policy = getattr(args, "resolved_report_fail_on", "never")
    if _should_fail(policy, bundle.severity):
        _CLI_LOGGER.info(
            "cli.report.failure_policy_triggered",
            extra={"severity": bundle.severity, "policy": policy},
        )
        raise SystemExit(1)


def _load_input(input_path: str | None) -> str:
    if input_path:
        return Path(input_path).read_text(encoding="utf-8")
    return sys.stdin.read()


def _write_output(payload: str, output_path: str | None) -> None:
    if not output_path:
        print(payload)
        return

    destination = Path(output_path)
    try:
        atomic_write_text(destination, payload)
    except OutputPathError as exc:
        _CLI_LOGGER.error(
            "cli.output.write_failed",
            extra={"path": str(exc.path)},
        )
        _fail(str(exc))


def _format_diagnostics_text(snapshot: dict[str, object]) -> str:
    telemetry_obj = snapshot.get("telemetry", {})
    extensions_obj = snapshot.get("extensions", {})
    if isinstance(telemetry_obj, dict):
        telemetry = telemetry_obj
    else:
        telemetry = {}
    if isinstance(extensions_obj, dict):
        extensions = extensions_obj
    else:
        extensions = {}
    metrics_candidate = telemetry.get("metrics")
    metrics_info = metrics_candidate if isinstance(metrics_candidate, Mapping) else None
    count_value = extensions.get("count")
    count = int(count_value) if isinstance(count_value, int) else 0
    lines = [
        f"Generated: {snapshot.get('generated_at', 'unknown')}",
        f"Status: {telemetry.get('status', 'unknown')}",
        f"Extensions: {count}",
    ]
    names_value = extensions.get("names")
    if isinstance(names_value, list):
        names = ", ".join(str(name) for name in names_value)
        lines.append(f"Extension Names: {names}")
    hooks_candidate = extensions.get("hooks")
    if isinstance(hooks_candidate, Mapping):
        hook_pairs = ", ".join(
            f"{str(name)}={int(count)}" for name, count in sorted(hooks_candidate.items())
        )
        lines.append(f"Hooks: {hook_pairs}")
    if metrics_info:
        line_count = metrics_info.get("line_count", 0)
        lines.append(f"Metrics Lines: {line_count}")
    health_url = telemetry.get("health_endpoint")
    if isinstance(health_url, str) and health_url:
        lines.append(f"Health URL: {health_url}")
    metrics_url = telemetry.get("metrics_endpoint")
    if isinstance(metrics_url, str) and metrics_url:
        lines.append(f"Metrics URL: {metrics_url}")
    component = snapshot.get("component")
    if isinstance(component, str) and component:
        lines.append(f"Component: {component}")
    return "\n".join(lines)


def _record_cli_metrics(
    instrumentation: InstrumentationManager,
    labels: dict[str, str],
    status: str,
    duration_seconds: float,
) -> None:
    # agent-safe-task: extend metrics without affecting CLI control flow
    enriched = {**labels, "status": status}
    safe_duration = duration_seconds if duration_seconds >= 0 else 0.0
    instrumentation.counter(
        "zscripts_cli_invocations_total",
        "CLI invocations processed by zscripts.",
    ).inc(labels=enriched)
    instrumentation.histogram(
        "zscripts_cli_duration_seconds",
        "Duration of zscripts CLI commands in seconds.",
    ).observe(safe_duration, labels=enriched)


def _fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def _prepare_and_execute(
    raw_args: Sequence[str],
    runtime: _CliRuntime,
    extension_context: ExtensionContext,
    extensions: Sequence[object],
) -> None:
    registry = extension_context.adapter_registry
    config = extension_context.config
    parser = _build_parser(registry.available(), extensions, extension_context)
    args = parser.parse_args(raw_args)

    _merge_cli_toggles(config, args)
    if args.dangerous is True:
        config.dangerous_mode = True
    if args.adapter:
        config.default_adapter = args.adapter

    args.extensions_loaded = list(extensions)
    args.extensions_manifest = dict(extension_context.manifests)
    args.extension_manager = extensions
    args.runtime = runtime
    service = build_toolkit_service(
        config,
        adapter_registry=registry,
        telemetry=runtime.telemetry,
    )
    for extension in extensions:
        extension.after_service_ready(service, extension_context)
    extensions.emit(
        "service_ready",
        service=service,
        context=extension_context,
    )

    handler: Callable[[argparse.Namespace, ToolkitService], None] = args.func

    if hasattr(args, "report_format"):
        if args.report_format:
            config.report_format = args.report_format
        args.resolved_report_format = config.report_format
    if hasattr(args, "report_redact"):
        if args.report_redact is not None:
            config.report_redact = args.report_redact
        args.resolved_report_redact = config.report_redact
    if hasattr(args, "report_fail_on"):
        if args.report_fail_on:
            config.report_fail_on = args.report_fail_on
        args.resolved_report_fail_on = config.report_fail_on

    _execute_command(args, handler, service, runtime)


def _resolve_command_labels(args: argparse.Namespace) -> tuple[str, dict[str, str]]:
    """Return a stable command label tuple for metrics and logging."""

    command_name = getattr(args, "command", None) or "unknown"
    labels = {"command": command_name}
    if command_name == "extensions":
        subcommand = getattr(args, "extensions_subcommand", None)
        if subcommand:
            command_name = f"extensions.{subcommand}"
            labels["command"] = command_name
    return command_name, labels


def _execute_command(
    args: argparse.Namespace,
    handler: Callable[[argparse.Namespace, ToolkitService], None],
    service: ToolkitService,
    runtime: _CliRuntime,
) -> None:
    command_name, labels = _resolve_command_labels(args)
    op_result: OperationResult | None = None
    try:
        # agent-entrypoint: centralized automation hook for CLI command execution
        with runtime.instrumentation.operation(
            command_name,
            attributes=labels,
            correlation_id=runtime.correlation_id,
        ) as result:
            op_result = result
            try:
                handler(args, service)
            except SystemExit as exc:
                result.status = "success" if exc.code in (None, 0) else "error"
                raise
    except SystemExit:
        raise
    except Exception:
        _CLI_LOGGER.exception(
            "cli.command.failure",
            extra={"command": command_name},
        )
        raise
    finally:
        final_status = op_result.status if op_result is not None else "error"
        final_duration = op_result.duration_seconds if op_result is not None else 0.0
        _record_cli_metrics(runtime.instrumentation, labels, final_status, final_duration)


__all__ = ["main"]
