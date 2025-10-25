"""Command-line interface entry point for the zscripts toolkit."""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from collections.abc import Callable, Sequence
from pathlib import Path

from zscripts import get_default_config
from zscripts.application.services import ToolkitService
from zscripts.config import ToolkitConfig
from zscripts.configuration import (
    ConfigurationError,
    load_toolkit_config,
    parse_override_pairs,
)
from zscripts.extensions import ExtensionContext, ExtensionLoadError, load_extensions
from zscripts.infrastructure import build_toolkit_service
from zscripts.infrastructure.adapters import AdapterRegistry
from zscripts.observability.logging import get_logger
from zscripts.observability.telemetry import TelemetryManager, TelemetrySettings


class _HelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    """Pretty-print help text while preserving manual newlines."""


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

    extension_context = ExtensionContext(
        config=config,
        adapter_registry=registry,
        telemetry=telemetry,
        logger=get_logger("extensions"),
    )
    try:
        extensions = load_extensions(config.extensions, context=extension_context)
    except ExtensionLoadError as exc:
        _fail(str(exc))

    parser = _build_parser(registry.available(), extensions, extension_context)
    args = parser.parse_args(raw_args)

    _merge_cli_toggles(config, args)
    if args.dangerous is True:
        config.dangerous_mode = True
    if args.adapter:
        config.default_adapter = args.adapter

    telemetry.start()

    args.extensions_loaded = extensions
    service = build_toolkit_service(
        config,
        adapter_registry=registry,
        telemetry=telemetry,
    )
    for extension in extensions:
        extension.after_service_ready(service, extension_context)

    handler: Callable[[argparse.Namespace, ToolkitService], None] = args.func
    handler(args, service)


def _build_parser(
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

    extensions_parser = subparsers.add_parser("extensions", help="List loaded extensions")
    extensions_parser.add_argument("--output", help="Destination for the extension list")
    extensions_parser.set_defaults(func=_handle_extensions)

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
    if args.command is not None:
        if not args.command:
            _fail("Provide at least one argument after --command.")
        command = args.command
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


def _handle_extensions(args: argparse.Namespace, service: ToolkitService) -> None:
    loaded = getattr(args, "extensions_loaded", [])
    if not loaded:
        payload = "No extensions configured."
    else:
        lines = [
            f"{getattr(ext, 'name', ext.__class__.__name__)}: "
            f"{getattr(ext, 'description', '').strip()}"
            for ext in loaded
        ]
        payload = "\n".join(lines)
    _write_output(payload, getattr(args, "output", None))


def _load_input(input_path: str | None) -> str:
    if input_path:
        return Path(input_path).read_text(encoding="utf-8")
    return sys.stdin.read()


def _write_output(payload: str, output_path: str | None) -> None:
    if output_path:
        Path(output_path).write_text(payload, encoding="utf-8")
    else:
        print(payload)


def _fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


__all__ = ["main"]
