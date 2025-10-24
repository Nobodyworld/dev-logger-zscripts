"""Command line interface for the zscripts toolkit."""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from collections.abc import Callable, Sequence
from pathlib import Path

from zscripts import get_default_config
from zscripts.application.services import ToolkitService
from zscripts.infrastructure import build_toolkit_service
from zscripts.infrastructure.adapters import AdapterRegistry


class _HelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    """Pretty-print help text while preserving manual newlines."""


def main(argv: list[str] | None = None) -> None:
    """Run the zscripts CLI."""

    registry = AdapterRegistry()
    parser = _build_parser(registry.available())
    args = parser.parse_args(argv)

    config = get_default_config()
    config.dangerous_mode = bool(args.dangerous)
    if args.adapter:
        config.default_adapter = args.adapter

    service = build_toolkit_service(config, adapter_registry=registry)

    handler: Callable[[argparse.Namespace, ToolkitService], None] = args.func
    handler(args, service)


def _build_parser(adapter_choices: Sequence[str]) -> argparse.ArgumentParser:
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
    parser.add_argument(
        "--adapter",
        help="Adapter to use when parsing logs.",
        choices=adapter_choices,
    )
    parser.add_argument(
        "--dangerous",
        action="store_true",
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

    return parser


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
