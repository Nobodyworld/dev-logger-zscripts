"""Command line interface for the zscripts toolkit."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from adapters import available_adapters, get_adapter
from adapters.base import LogAdapter
from scripts import SandboxRunner, SandboxSettings, redact_text
from zscripts import get_default_config
from zscripts.schemas import NormalizedLog, load_normalized_schema

try:  # pragma: no cover - optional dependency
    import jsonschema
except ImportError:  # pragma: no cover - fallback when jsonschema missing
    jsonschema = None


def main(argv: list[str] | None = None) -> None:
    """Run the zscripts CLI.

    Args:
        argv: Optional list of command-line arguments. When ``None`` the
            arguments are read from :data:`sys.argv`.
    """

    args = _build_parser().parse_args(argv)
    config = get_default_config()
    config.dangerous_mode = bool(args.dangerous)
    config.default_adapter = args.adapter or config.default_adapter

    handler: Callable[[argparse.Namespace, SandboxSettings], None] = args.func
    sandbox_settings = SandboxSettings(
        allowed_paths=config.allowed_paths,
        timeout_seconds=config.timeout_seconds,
        dangerous_mode=config.dangerous_mode,
    )
    handler(args, sandbox_settings)


def _build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the CLI.

    Returns:
        argparse.ArgumentParser: Configured parser instance.
    """
    parser = argparse.ArgumentParser(description="Universal build log toolkit")
    parser.add_argument(
        "--adapter",
        help="Adapter to use when parsing logs.",
        choices=available_adapters(),
    )
    parser.add_argument(
        "--dangerous",
        action="store_true",
        help="Disable sandbox guardrails (use with caution).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="Collect log output")
    collect_parser.add_argument("--input", help="Path to existing log file")
    collect_parser.add_argument("--command", nargs=argparse.REMAINDER, help="Command to execute")
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


def _handle_collect(args: argparse.Namespace, sandbox: SandboxSettings) -> None:
    """Implementation of the ``collect`` subcommand.

    Args:
        args: Parsed arguments containing command configuration.
        sandbox: Sandbox settings derived from configuration.
    """
    config = get_default_config()
    adapter_key = args.adapter or config.default_adapter
    adapter = get_adapter(adapter_key)

    if args.command:
        runner = SandboxRunner(sandbox)
        result = runner.run(args.command)
        payload = "\n".join([result.stdout, result.stderr])
        if result.returncode != 0:
            payload += f"\nCommand exited with {result.returncode}"
    elif args.input:
        payload = adapter.collect(Path(args.input), sandbox)
    else:
        payload = sys.stdin.read()

    if args.redact:
        payload = redact_text(payload, config.redact_patterns)

    _write_output(payload, args.output)


def _handle_parse(args: argparse.Namespace, sandbox: SandboxSettings) -> None:
    """Implementation of the ``parse`` subcommand.

    Args:
        args: Parsed command-line arguments.
        sandbox: Sandbox settings (unused for parsing but provided for symmetry).
    """
    raw_text = _load_input(args.input)
    normalized, _ = _parse_with_adapter(args.adapter, raw_text)
    payload = json.dumps(normalized.to_dict(), indent=2)
    _write_output(payload, args.output)


def _handle_summarize(args: argparse.Namespace, sandbox: SandboxSettings) -> None:
    """Implementation of the ``summarize`` subcommand.

    Args:
        args: Parsed command-line arguments.
        sandbox: Sandbox settings (unused for summarizing).
    """
    raw_text = _load_input(args.input)
    normalized, adapter = _parse_with_adapter(args.adapter, raw_text)
    summary = adapter.summarize(normalized)
    print(summary)


def _handle_explain(args: argparse.Namespace, sandbox: SandboxSettings) -> None:
    """Implementation of the ``explain`` subcommand.

    Args:
        args: Parsed command-line arguments.
        sandbox: Sandbox settings (unused for explaining).
    """
    raw_text = _load_input(args.input)
    normalized, _ = _parse_with_adapter(args.adapter, raw_text)
    explanation = _build_explanation(normalized)
    print(explanation)


def _handle_guardrails(args: argparse.Namespace, sandbox: SandboxSettings) -> None:
    """Implementation of the ``guardrails`` subcommand.

    Args:
        args: Parsed command-line arguments.
        sandbox: Sandbox settings describing the current guardrails.
    """
    payload = {
        "allowed_paths": [str(path) for path in sandbox.allowed_paths],
        "timeout_seconds": sandbox.timeout_seconds,
        "dangerous_mode": sandbox.dangerous_mode,
    }
    print(json.dumps(payload, indent=2))


def _handle_redact(args: argparse.Namespace, sandbox: SandboxSettings) -> None:
    """Implementation of the ``redact`` subcommand.

    Args:
        args: Parsed command-line arguments.
        sandbox: Sandbox settings (unused for redaction).
    """
    config = get_default_config()
    text = _load_input(args.input)
    payload = redact_text(text, config.redact_patterns)
    _write_output(payload, args.output)


def _handle_examples(args: argparse.Namespace, sandbox: SandboxSettings) -> None:
    """Implementation of the ``examples`` subcommand.

    Args:
        args: Parsed command-line arguments.
        sandbox: Sandbox settings (unused for listing examples).
    """
    base = Path("examples")
    adapter_filter = args.adapter
    entries = []
    for adapter_dir in sorted(base.iterdir()):
        if adapter_dir.is_dir():
            if adapter_filter and adapter_dir.name != adapter_filter:
                continue
            for file in adapter_dir.glob("*.log"):
                entries.append(str(file))
    print("\n".join(entries))


def _parse_with_adapter(adapter_key: str | None, raw_text: str) -> tuple[NormalizedLog, LogAdapter]:
    """Parse raw log text using the requested adapter.

    Args:
        adapter_key: Optional adapter identifier.
        raw_text: Raw log text to parse.

    Returns:
        tuple[NormalizedLog, LogAdapter]: Parsed log and adapter used.
    """
    key = adapter_key or get_default_config().default_adapter
    adapter = get_adapter(key)
    normalized = adapter.parse(raw_text)
    _validate_normalized(normalized)
    return normalized, adapter


def _validate_normalized(normalized: NormalizedLog) -> None:
    """Validate normalized logs against the JSON schema.

    Args:
        normalized: Normalized log instance to validate.
    """
    schema = load_normalized_schema()
    if jsonschema:
        jsonschema.validate(instance=normalized.to_dict(), schema=schema)


def _load_input(input_path: str | None) -> str:
    """Load log text from a file or STDIN.

    Args:
        input_path: Optional path to a log file.

    Returns:
        str: Loaded log text.
    """
    if input_path:
        return Path(input_path).read_text(encoding="utf-8")
    return sys.stdin.read()


def _write_output(payload: str, output_path: str | None) -> None:
    """Write payload to a file or STDOUT.

    Args:
        payload: Text to write.
        output_path: Optional path to write the text to.
    """
    if output_path:
        Path(output_path).write_text(payload, encoding="utf-8")
    else:
        print(payload)


def _build_explanation(normalized: NormalizedLog) -> str:
    """Build a human-readable explanation for normalized logs.

    Args:
        normalized: Normalized log data.

    Returns:
        str: Explanation string suitable for LLM prompts.
    """
    lines = [
        f"Tool: {normalized.tool}",
        f"Ecosystem: {normalized.ecosystem}",
        f"Status: {normalized.status}",
        f"Summary: {normalized.summary}",
    ]
    if normalized.tests:
        lines.append(
            "Tests: "
            f"passed={normalized.tests.passed} failed={normalized.tests.failed} "
            f"skipped={normalized.tests.skipped}"
        )
    if normalized.errors:
        lines.append("Errors:")
        for issue in normalized.errors:
            lines.append(f"  - {issue.message} ({issue.file}:{issue.line})")
    if normalized.warnings:
        lines.append("Warnings:")
        for issue in normalized.warnings:
            lines.append(f"  - {issue.message} ({issue.file}:{issue.line})")
    if normalized.artifacts:
        lines.append("Artifacts:")
        for artifact in normalized.artifacts:
            lines.append(f"  - {artifact}")
    if normalized.metadata:
        lines.append("Metadata:")
        for key, value in normalized.metadata.items():
            lines.append(f"  - {key}: {value}")
    return "\n".join(lines)


__all__ = ["main"]
