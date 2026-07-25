"""Unified command-line interface for the zscripts toolkit."""

from __future__ import annotations

import argparse
import inspect
import json
import select
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from zscripts import get_default_config
from zscripts.application.io_utils import (
    OutputPathError,
    atomic_write_text,
    prepare_output_path,
)
from zscripts.application.report_formatters import get_report_formatter
from zscripts.application.repository_review import (
    RepositoryReviewService,
    public_repository,
    public_snapshot,
)
from zscripts.application.services import ToolkitService
from zscripts.config import ToolkitConfig, clone_config
from zscripts.configuration import (
    ConfigurationError,
    load_toolkit_config,
    parse_override_pairs,
)
from zscripts.extensions import (
    ExtensionContext,
    ExtensionHookRegistry,
    ExtensionManager,
    load_extensions,
    scaffold_extension,
)
from zscripts.infrastructure import build_toolkit_service
from zscripts.infrastructure.adapters import AdapterRegistry
from zscripts.infrastructure.repository_discovery import AnalysisCancelled
from zscripts.observability.diagnostics import (
    DiagnosticsSnapshot,
    collect_runtime_diagnostics,
)
from zscripts.observability.health_checks import HealthCheckRegistry
from zscripts.observability.instrumentation import InstrumentationManager
from zscripts.observability.logging import configure_logging, get_logger
from zscripts.observability.metrics import MetricsRegistry, default_registry
from zscripts.observability.telemetry import TelemetryManager, TelemetrySettings

_EXTENSIONS_COMMAND = "ex" + "tensions"

_GLOBAL_PARSER = argparse.ArgumentParser(add_help=False)
_GLOBAL_PARSER.add_argument("--config", metavar="PATH", help="Path to a TOML or JSON configuration file.")
_GLOBAL_PARSER.add_argument(
    "--set",
    dest="raw_overrides",
    action="append",
    help="Override configuration values using KEY=VALUE pairs (may be repeated).",
)
_GLOBAL_PARSER.add_argument("--adapter", help="Preferred adapter identifier for the current command run.")
_GLOBAL_PARSER.add_argument(
    "--enable-telemetry",
    dest="enable_telemetry",
    action=argparse.BooleanOptionalAction,
    help="Toggle telemetry regardless of configuration defaults.",
)
_GLOBAL_PARSER.add_argument(
    "--log-level", dest="log_level", help="Override logging level (e.g., INFO, DEBUG)."
)
_GLOBAL_PARSER.add_argument(
    "--log-format",
    dest="log_format",
    choices={"text", "json"},
    help="Override logging format for this run.",
)


@dataclass(slots=True)
class RuntimeState:
    """Aggregated state needed by command handlers."""

    config: ToolkitConfig
    adapter_override: str | None
    service: ToolkitService
    telemetry: TelemetryManager | None
    metrics: MetricsRegistry
    cli_instrumentation: InstrumentationManager
    extension_manager: ExtensionManager
    extension_context: ExtensionContext
    logger: Any


def _build_main_parser(
    *,
    extensions: ExtensionManager,
    context: ExtensionContext,
) -> tuple[argparse.ArgumentParser, argparse._SubParsersAction[argparse.ArgumentParser]]:
    parser = argparse.ArgumentParser(
        description="Cross-language log normalization and diagnostic CLI.",
        parents=[_GLOBAL_PARSER],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser(
        "collect",
        help="Collect raw logs from a file, command, or STDIN.",
    )
    collect_parser.add_argument("--input", metavar="PATH", help="Path to a log file to collect.")
    collect_parser.add_argument(
        "--command",
        nargs="+",
        metavar="ARG",
        help="Command to execute in the sandbox when capturing logs live.",
    )
    collect_parser.add_argument(
        "--redact",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Apply configured redaction patterns to the collected payload.",
    )
    collect_parser.set_defaults(handler=_handle_collect)

    parse_parser = subparsers.add_parser(
        "parse",
        help="Parse logs into the normalized schema and emit JSON.",
    )
    parse_parser.add_argument("--input", metavar="PATH", help="Path to a log file to parse.")
    parse_parser.add_argument(
        "--command",
        nargs="+",
        metavar="ARG",
        help="Command to execute when collecting logs for parsing.",
    )
    parse_parser.set_defaults(handler=_handle_parse)

    guardrails_parser = subparsers.add_parser(
        "guardrails",
        help="Display the sandbox configuration currently in effect.",
    )
    guardrails_parser.set_defaults(handler=_handle_guardrails)

    report_parser = subparsers.add_parser(
        "report",
        help="Generate a summarized report for build or test logs.",
    )
    report_parser.add_argument("--input", metavar="PATH", help="Path to a log file to report on.")
    report_parser.add_argument(
        "--command",
        nargs="+",
        metavar="ARG",
        help="Command to execute when collecting logs for reporting.",
    )
    report_parser.add_argument(
        "--format",
        choices={"json", "markdown"},
        help="Desired output format (defaults to configuration value).",
    )
    report_parser.add_argument(
        "--output",
        metavar="PATH",
        help="Optional file path to write the report (stdout is always populated).",
    )
    report_parser.add_argument(
        "--fail-on",
        choices={"never", "warnings", "errors"},
        help="Severity threshold that forces a non-zero exit code.",
    )
    report_parser.add_argument(
        "--redact",
        action=argparse.BooleanOptionalAction,
        help="Control whether report sections are redacted before emission.",
    )
    report_parser.set_defaults(handler=_handle_report)

    summarize_parser = subparsers.add_parser(
        "summarize",
        help="Produce a concise summary for collected logs.",
    )
    summarize_parser.add_argument("--input", metavar="PATH", help="Path to a log file to summarize.")
    summarize_parser.add_argument(
        "--command",
        nargs="+",
        metavar="ARG",
        help="Command to execute when capturing logs prior to summarizing.",
    )
    summarize_parser.add_argument(
        "--redact",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Apply redaction patterns to the generated summary.",
    )
    summarize_parser.set_defaults(handler=_handle_summarize)

    explain_parser = subparsers.add_parser(
        "explain",
        help="Generate a detailed explanation for collected logs.",
    )
    explain_parser.add_argument("--input", metavar="PATH", help="Path to a log file to explain.")
    explain_parser.add_argument(
        "--command",
        nargs="+",
        metavar="ARG",
        help="Command to execute when capturing logs before explaining results.",
    )
    explain_parser.add_argument(
        "--redact",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Apply redaction patterns to the explanation output.",
    )
    explain_parser.set_defaults(handler=_handle_explain)

    redact_parser = subparsers.add_parser(
        "redact",
        help="Redact sensitive data from log content.",
    )
    redact_parser.add_argument("--input", metavar="PATH", help="Path to a log file to redact.")
    redact_parser.add_argument(
        "--command",
        nargs="+",
        metavar="ARG",
        help="Command to execute when collecting logs to redact.",
    )
    redact_parser.set_defaults(handler=_handle_redact)

    examples_parser = subparsers.add_parser(
        "examples",
        help="List bundled example log files for adapters.",
    )
    examples_parser.add_argument(
        "--format",
        choices={"text", "json"},
        default="text",
        help="Output format for the example listing (default: text).",
    )
    examples_parser.set_defaults(handler=_handle_examples)

    adapters_parser = subparsers.add_parser(
        "adapters",
        help="Show supported log adapters, descriptions, and bundled examples.",
    )
    adapters_parser.add_argument(
        "--format",
        choices={"text", "json"},
        default="text",
        help="Output format for the adapter inventory (default: text).",
    )
    adapters_parser.set_defaults(handler=_handle_adapters)

    diagnostics_parser = subparsers.add_parser(
        "diagnostics",
        help="Collect runtime diagnostics including telemetry and extension metadata.",
    )
    diagnostics_parser.add_argument(
        "--format",
        choices={"json", "text"},
        default="json",
        help="Output format for diagnostics (default: json).",
    )
    diagnostics_parser.add_argument(
        "--output",
        metavar="PATH",
        help="Write diagnostics to the given file instead of stdout.",
    )
    diagnostics_parser.add_argument(
        "--include-metrics",
        action="store_true",
        help="Include Prometheus metrics text in the diagnostics payload.",
    )
    diagnostics_parser.set_defaults(handler=_handle_diagnostics)

    extensions_parser = subparsers.add_parser(
        "extensions",
        help="Inspect or scaffold toolkit extensions.",
    )
    extensions_parser.add_argument(
        "--output-format",
        choices={"text", "json"},
        default="text",
        help="Format for extension listings (default: text).",
    )
    extensions_subparsers = extensions_parser.add_subparsers(dest="extensions_command")
    extensions_parser.set_defaults(handler=_handle_extensions)

    scaffold_parser = extensions_subparsers.add_parser(
        "scaffold",
        help="Create a starter extension module in the target directory.",
    )
    scaffold_parser.add_argument("name", help="Module name for the generated extension.")
    scaffold_parser.add_argument(
        "--directory",
        metavar="PATH",
        type=Path,
        default=Path.cwd(),
        help="Directory to place the generated module (defaults to CWD).",
    )

    experimental_parser = subparsers.add_parser(
        "experimental",
        help="Use experimental repository-review commands.",
    )
    experimental_subparsers = experimental_parser.add_subparsers(
        dest="experimental_command",
        required=True,
    )
    analyze_parser = experimental_subparsers.add_parser(
        "analyze",
        help="Run a read-only metadata-only Python repository scan.",
    )
    analyze_parser.add_argument("repository", type=Path, help="Local repository directory.")
    analyze_parser.add_argument("--app-data-dir", type=Path, help="Override local application data.")
    analyze_parser.add_argument("--max-files", type=int, default=5_000)
    analyze_parser.add_argument("--max-file-size", type=int, default=1_000_000)
    analyze_parser.add_argument("--max-total-bytes", type=int, default=100_000_000)
    analyze_parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="Additional repository-relative exclusion glob (repeatable).",
    )
    analyze_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit deterministic normalized evidence as JSON.",
    )
    analyze_parser.set_defaults(handler=_handle_experimental_analyze)

    repositories_parser = experimental_subparsers.add_parser(
        "repositories",
        help="List repositories with completed local snapshots.",
    )
    repositories_parser.add_argument("--app-data-dir", type=Path)
    repositories_parser.add_argument("--json", action="store_true")
    repositories_parser.set_defaults(handler=_handle_experimental_repositories)

    snapshots_parser = experimental_subparsers.add_parser(
        "snapshots",
        help="List completed snapshots for a repository identity.",
    )
    snapshots_parser.add_argument("repository_id")
    snapshots_parser.add_argument("--app-data-dir", type=Path)
    snapshots_parser.add_argument("--json", action="store_true")
    snapshots_parser.set_defaults(handler=_handle_experimental_snapshots)

    workspace_parser = subparsers.add_parser(
        "workspace",
        help="Start the experimental localhost-only repository review workspace.",
    )
    workspace_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Binding host; the MVP accepts only 127.0.0.1.",
    )
    workspace_parser.add_argument("--port", type=int, default=8765)
    workspace_parser.add_argument("--app-data-dir", type=Path)
    workspace_parser.set_defaults(handler=_handle_workspace)

    for extension in extensions:
        try:
            extension.register_cli(subparsers, context)
        except Exception:  # pragma: no cover - defensive against misbehaving extensions
            context.logger.exception(
                "extension.cli.registration_failed",
                extra={"extension": getattr(extension, "name", extension.__class__.__name__)},
            )

    return parser, subparsers


def _compose_config(args: argparse.Namespace) -> ToolkitConfig:
    base = get_default_config()
    overrides = parse_override_pairs(args.raw_overrides)
    path = Path(args.config).expanduser() if args.config else None
    config = load_toolkit_config(path=path, overrides=overrides, base=base)
    if args.log_level:
        config.log_level = args.log_level.upper()
    if args.log_format:
        config.log_format = args.log_format
    return config


def _create_telemetry(config: ToolkitConfig, enabled: bool | None) -> TelemetryManager | None:
    telemetry_enabled = enabled if enabled is not None else config.telemetry_enabled
    settings = TelemetrySettings(
        enabled=telemetry_enabled,
        host=config.telemetry_host,
        port=config.telemetry_port,
        log_level=config.log_level,
        log_format=config.log_format,
    )
    if not settings.enabled:
        configure_logging(settings.log_level, settings.log_format)
        return None
    return TelemetryManager(settings)


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    try:
        global_args, _ = _GLOBAL_PARSER.parse_known_args(argv)
    except SystemExit as exc:  # pragma: no cover - argparse already wrote help
        return int(exc.code or 0)

    try:
        config = _compose_config(global_args)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    telemetry = _create_telemetry(config, global_args.enable_telemetry)
    metrics = telemetry.metrics if telemetry is not None else default_registry
    cli_instrumentation = InstrumentationManager(telemetry=telemetry, metrics=metrics, component="cli")
    extensions_instrumentation = InstrumentationManager(
        telemetry=telemetry, metrics=metrics, component="extensions"
    )
    hook_registry = ExtensionHookRegistry(extensions_instrumentation)
    adapter_registry = AdapterRegistry()
    extensions_logger = get_logger("extensions")
    health_registry = telemetry.health_checks if telemetry is not None else HealthCheckRegistry()
    extension_context = ExtensionContext(
        config=clone_config(config),
        adapter_registry=adapter_registry,
        telemetry=telemetry,
        instrumentation=extensions_instrumentation,
        logger=extensions_logger,
        hook_registry=hook_registry,
        health_checks=health_registry,
    )
    extension_manager = load_extensions(config.extensions, context=extension_context)

    parser, subparsers = _build_main_parser(extensions=extension_manager, context=extension_context)
    command_choices = set(subparsers.choices.keys())
    inferred_command = _infer_command_label(argv, command_choices)

    counter = metrics.counter(
        "zscripts_cli_invocations_total",
        "Total CLI invocations grouped by command and status.",
    )
    histogram = metrics.histogram(
        "zscripts_cli_duration_seconds",
        "Duration of CLI commands in seconds.",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        if telemetry is not None:
            telemetry.stop()
        counter.inc(labels={"command": inferred_command or "<none>", "status": "error"})
        histogram.observe(0.0, labels={"command": inferred_command or "<none>", "status": "error"})
        raise

    service_instrumentation = InstrumentationManager(
        telemetry=telemetry, metrics=metrics, component="service"
    )
    service = build_toolkit_service(
        config=config,
        adapter_registry=adapter_registry,
        telemetry=telemetry,
        instrumentation=service_instrumentation,
    )
    for extension in extension_manager:
        try:
            extension.after_service_ready(service, extension_context)
        except Exception:  # pragma: no cover - extension safety net
            extensions_logger.exception(
                "extension.service_ready.failed",
                extra={"extension": getattr(extension, "name", extension.__class__.__name__)},
            )
    extension_manager.emit("service_ready", service=service, context=extension_context)

    if telemetry is not None:
        telemetry.start()

    runtime = RuntimeState(
        config=config,
        adapter_override=args.adapter,
        service=service,
        telemetry=telemetry,
        metrics=metrics,
        cli_instrumentation=cli_instrumentation,
        extension_manager=extension_manager,
        extension_context=extension_context,
        logger=get_logger("cli"),
    )

    command_label = args.command
    if command_label == "extensions" and getattr(args, "extensions_command", None):
        command_label = f"extensions.{args.extensions_command}"

    start_time = time.perf_counter()
    status = "success"
    exit_code = 0
    try:
        exit_code = _dispatch_command(args, runtime)
        status = "success" if exit_code == 0 else "error"
    except OutputPathError as exc:
        status = "error"
        exit_code = 2
        print(exc, file=sys.stderr)
    except ValueError as exc:
        status = "error"
        exit_code = 2
        print(exc, file=sys.stderr)
    except Exception:  # pragma: no cover - ensures telemetry cleanup on unexpected errors
        status = "error"
        runtime.logger.exception("cli.command.failure", extra={"command": command_label})
        raise
    finally:
        duration = time.perf_counter() - start_time
        counter.inc(labels={"command": command_label or "<none>", "status": status})
        histogram.observe(duration, labels={"command": command_label or "<none>", "status": status})
        if telemetry is not None:
            telemetry.stop()

    return exit_code


def _infer_command_label(argv: Sequence[str], choices: set[str]) -> str | None:
    for index, token in enumerate(argv):
        if token in choices:
            if token == _EXTENSIONS_COMMAND:
                for candidate in argv[index + 1 :]:
                    if candidate in choices:
                        break
                    if candidate.startswith("-"):
                        continue
                    return f"extensions.{candidate}"
            return token
    return None


def _dispatch_command(args: argparse.Namespace, runtime: RuntimeState) -> int:
    handler = getattr(args, "handler", None)
    if handler is not None:
        result = handler(args, runtime)
        return int(result or 0)

    func = getattr(args, "func", None)
    if callable(func):
        if _handler_accepts_service(func):
            result = func(args, runtime.service)
        else:
            result = func(args)
        return int(result or 0)

    raise ValueError("No handler registered for the selected command.")


def _handler_accepts_service(callback: Callable[..., Any]) -> bool:
    signature = inspect.signature(callback)
    positional = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
    ]
    return len(positional) >= 2


def _handle_collect(args: argparse.Namespace, runtime: RuntimeState) -> int:
    payload = _collect_raw_logs(args, runtime, redact=getattr(args, "redact", False))
    print(payload)
    return 0


def _handle_experimental_analyze(args: argparse.Namespace, runtime: RuntimeState) -> int:
    from zscripts.domain.repository_review import ScanLimits

    limits = ScanLimits(
        max_files=args.max_files,
        max_file_size_bytes=args.max_file_size,
        max_total_bytes=args.max_total_bytes,
    )
    service = RepositoryReviewService(
        data_directory=args.app_data_dir,
        limits=limits,
        configured_excludes=args.exclude,
    )

    def progress(update: object) -> None:
        if args.json:
            return
        phase = getattr(update, "phase", "analysis")
        completed = getattr(update, "completed", 0)
        total = getattr(update, "total", 0)
        print(f"{phase}: {completed}/{total}", file=sys.stderr)

    try:
        evidence = service.analyze(args.repository, progress=progress)
    except AnalysisCancelled:
        print("Repository analysis was cancelled.", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Repository analysis failed: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(evidence.canonical_payload(), indent=2, sort_keys=True))
    else:
        print(f"Repository: {evidence.repository.display_name}")
        print(f"Snapshot: {evidence.snapshot.snapshot_id}")
        print(f"Files analyzed: {evidence.snapshot.included_file_count}")
        print(f"Symbols: {evidence.snapshot.symbol_count}")
        print(f"Parse gaps: {evidence.snapshot.parse_gap_count}")
        print(f"Truncated: {'yes' if evidence.snapshot.truncated else 'no'}")
    return 0


def _handle_experimental_repositories(args: argparse.Namespace, runtime: RuntimeState) -> int:
    service = RepositoryReviewService(data_directory=args.app_data_dir)
    records = [public_repository(item) for item in service.list_repositories()]
    if args.json:
        print(json.dumps({"repositories": records}, indent=2, sort_keys=True))
    else:
        for record in records:
            print(f"{record['repository_id']}  {record['display_name']}")
    return 0


def _handle_experimental_snapshots(args: argparse.Namespace, runtime: RuntimeState) -> int:
    service = RepositoryReviewService(data_directory=args.app_data_dir)
    snapshots = [public_snapshot(item) for item in service.list_snapshots(args.repository_id)]
    if args.json:
        print(json.dumps({"snapshots": snapshots}, indent=2, sort_keys=True))
    else:
        for snapshot in snapshots:
            print(
                f"{snapshot['snapshot_id']}  {snapshot['completed_at']}  {snapshot['symbol_count']} symbols"
            )
    return 0


def _handle_workspace(args: argparse.Namespace, runtime: RuntimeState) -> int:
    try:
        from zscripts.interfaces.workspace_api import run_workspace
    except ModuleNotFoundError as exc:
        if exc.name in {"fastapi", "pydantic", "starlette", "uvicorn"}:
            print(
                "The experimental workspace dependencies are not installed. "
                "Install them with: python -m pip install 'zscripts[workspace]'",
                file=sys.stderr,
            )
            return 2
        raise
    run_workspace(
        host=args.host,
        port=args.port,
        data_directory=args.app_data_dir,
    )
    return 0


def _handle_parse(args: argparse.Namespace, runtime: RuntimeState) -> int:
    raw_text = _collect_raw_logs(args, runtime, redact=False)
    normalized = runtime.service.parse_logs(adapter_key=runtime.adapter_override, raw_text=raw_text)
    print(json.dumps(normalized.to_dict(), indent=2, sort_keys=True))
    return 0


def _handle_guardrails(args: argparse.Namespace, runtime: RuntimeState) -> int:  # noqa: ARG001 - interface parity
    snapshot = runtime.service.guardrails_snapshot()
    print(json.dumps(snapshot, indent=2, sort_keys=True))
    return 0


def _handle_report(args: argparse.Namespace, runtime: RuntimeState) -> int:
    raw_text = _collect_raw_logs(args, runtime, redact=False)
    redact = args.redact if args.redact is not None else runtime.config.report_redact
    bundle = runtime.service.generate_report(
        adapter_key=runtime.adapter_override,
        raw_text=raw_text,
        redact=redact,
    )
    formatter_name = args.format or runtime.config.report_format
    formatter = get_report_formatter(formatter_name)
    rendered = formatter(bundle)
    print(rendered)
    if args.output:
        destination = prepare_output_path(Path(args.output))
        atomic_write_text(destination, rendered)
    policy = args.fail_on or runtime.config.report_fail_on
    return 1 if _should_fail(policy, bundle.severity) else 0


def _handle_summarize(args: argparse.Namespace, runtime: RuntimeState) -> int:
    raw_text = _collect_raw_logs(args, runtime, redact=False)
    summary = runtime.service.summarize_logs(
        adapter_key=runtime.adapter_override,
        raw_text=raw_text,
    )
    if getattr(args, "redact", False):
        summary = runtime.service.redact_text(summary)
    print(summary)
    return 0


def _handle_explain(args: argparse.Namespace, runtime: RuntimeState) -> int:
    raw_text = _collect_raw_logs(args, runtime, redact=False)
    explanation = runtime.service.explain_logs(
        adapter_key=runtime.adapter_override,
        raw_text=raw_text,
    )
    if getattr(args, "redact", False):
        explanation = runtime.service.redact_text(explanation)
    print(explanation)
    return 0


def _handle_redact(args: argparse.Namespace, runtime: RuntimeState) -> int:
    raw_text = _collect_raw_logs(args, runtime, redact=False)
    redacted = runtime.service.redact_text(raw_text)
    print(redacted)
    return 0


def _handle_examples(args: argparse.Namespace, runtime: RuntimeState) -> int:
    examples = runtime.service.list_examples(adapter_filter=runtime.adapter_override)
    if args.format == "json":
        print(json.dumps(sorted(examples), indent=2, sort_keys=True))
        return 0
    if examples:
        print("\n".join(sorted(examples)))
    else:
        print("No examples available.")
    return 0


def _handle_adapters(args: argparse.Namespace, runtime: RuntimeState) -> int:
    inventory = _build_adapter_inventory(runtime)
    if args.format == "json":
        print(json.dumps(inventory, indent=2, sort_keys=True))
        return 0

    lines: list[str] = []
    for entry in inventory:
        examples = entry["examples"]
        examples_text = ", ".join(examples) if examples else "none"
        lines.append(
            f"{entry['identifier']} ({entry['ecosystem']}): {entry['description']}\n"
            f"  examples: {examples_text}"
        )
    print("\n".join(lines) if lines else "No adapters available.")
    return 0


def _build_adapter_inventory(runtime: RuntimeState) -> list[dict[str, object]]:
    registry = runtime.extension_context.adapter_registry
    identifiers = sorted(registry.available())
    if runtime.adapter_override:
        if runtime.adapter_override not in identifiers:
            msg = f"Unknown adapter: {runtime.adapter_override}"
            raise ValueError(msg)
        identifiers = [runtime.adapter_override]

    inventory: list[dict[str, object]] = []
    for identifier in identifiers:
        adapter = registry.resolve(identifier)
        inventory.append(
            {
                "identifier": adapter.identifier,
                "ecosystem": adapter.ecosystem,
                "description": adapter.description,
                "examples": sorted(runtime.service.list_examples(adapter_filter=identifier)),
            }
        )
    return inventory


def _handle_extensions(args: argparse.Namespace, runtime: RuntimeState) -> int:
    if getattr(args, "extensions_command", None) == "scaffold":
        target = scaffold_extension(args.name, args.directory)
        print(str(target))
        return 0

    manifests = runtime.extension_manager.manifests()
    if args.output_format == "json":
        payload = [
            {
                "name": manifest.name,
                "module": manifest.module,
                "entrypoint": manifest.entrypoint,
                "version": manifest.version,
                "capabilities": list(manifest.capabilities),
            }
            for manifest in manifests.values()
        ]
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    lines: list[str] = []
    for manifest in manifests.values():
        version = manifest.version or "0.0.0"
        capabilities = ", ".join(sorted(manifest.capabilities)) or "-"
        lines.append(f"{manifest.name} (v{version}) [{manifest.module}] capabilities: {capabilities}")
    print("\n".join(lines) if lines else "No extensions loaded.")
    return 0


def _handle_diagnostics(args: argparse.Namespace, runtime: RuntimeState) -> int:
    snapshot = collect_runtime_diagnostics(
        telemetry=runtime.telemetry or TelemetryManager(TelemetrySettings()),
        instrumentation=runtime.cli_instrumentation,
        extensions=runtime.extension_manager,
        include_metrics=args.include_metrics,
    )
    if args.format == "json":
        payload = json.dumps(snapshot.to_dict(), indent=2, sort_keys=True)
    else:
        payload = _format_diagnostics_text(snapshot)

    if args.output:
        destination = prepare_output_path(Path(args.output))
        atomic_write_text(destination, payload)
    else:
        print(payload)
    return 0


def _format_diagnostics_text(snapshot: DiagnosticsSnapshot) -> str:
    payload = snapshot.to_dict()
    telemetry = payload.get("telemetry")
    telemetry_mapping: Mapping[str, object] | None = telemetry if isinstance(telemetry, Mapping) else None
    extensions = payload.get("extensions")
    extensions_mapping: Mapping[str, object] | None = extensions if isinstance(extensions, Mapping) else None
    lines = [
        f"Generated: {payload.get('generated_at', 'unknown')}",
        f"Status: {telemetry_mapping.get('status', 'unknown') if telemetry_mapping else 'unknown'}",
        f"Telemetry enabled: {telemetry_mapping.get('telemetry_enabled', False) if telemetry_mapping else False}",
        f"Extensions loaded: {extensions_mapping.get('count', 0) if extensions_mapping else 0}",
    ]
    return "\n".join(lines)


def _collect_raw_logs(
    args: argparse.Namespace,
    runtime: RuntimeState,
    *,
    redact: bool,
) -> str:
    command = tuple(args.command) if getattr(args, "command", None) else None
    input_path = Path(args.input) if getattr(args, "input", None) else None
    stdin_text = _read_stdin_payload()
    return runtime.service.collect_logs(
        adapter_key=runtime.adapter_override,
        input_path=input_path,
        command=command,
        stdin_fallback=stdin_text,
        redact=redact,
    )


def _read_stdin_payload() -> str | None:
    if sys.stdin.closed:
        return None
    try:
        sys.stdin.fileno()
    except (OSError, ValueError):
        return None
    if sys.stdin.isatty():
        return None
    try:
        readable, _, _ = select.select([sys.stdin], [], [], 0)
    except OSError:
        return None
    if not readable:
        return None
    data = sys.stdin.read()
    return data if data else None


def _should_fail(policy: str, severity: str) -> bool:
    normalized_policy = policy.strip().lower()
    normalized_severity = severity.strip().lower()
    order = {"ok": 0, "warning": 1, "error": 2, "critical": 3}
    thresholds = {"never": 4, "warnings": 1, "errors": 2}
    severity_level = order.get(normalized_severity, 3)
    threshold = thresholds.get(normalized_policy, 4)
    return severity_level >= threshold


__all__ = ["main", "_should_fail"]
