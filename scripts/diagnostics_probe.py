"""Automation helper that collects diagnostics snapshots for CI agents."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from zscripts import get_default_config
from zscripts.application.io_utils import OutputPathError, atomic_write_text
from zscripts.configuration import ConfigurationError, load_toolkit_config, parse_override_pairs
from zscripts.extensions import (
    ExtensionContext,
    ExtensionHookRegistry,
    ExtensionLoadError,
    load_extensions,
)
from zscripts.infrastructure.adapters import AdapterRegistry
from zscripts.observability.diagnostics import collect_runtime_diagnostics
from zscripts.observability.logging import get_logger
from zscripts.observability.telemetry import TelemetryManager, TelemetrySettings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect a diagnostics snapshot for automation workflows.")
    parser.add_argument("--config", help="Optional configuration file path.")
    parser.add_argument("--output", help="Write diagnostics JSON to this file.")
    parser.add_argument(
        "--include-metrics",
        action="store_true",
        help="Embed Prometheus text in the diagnostics payload.",
    )
    parser.add_argument(
        "--set",
        dest="override_pairs",
        action="append",
        metavar="KEY=VALUE",
        help="Override configuration values.",
    )
    parser.add_argument(
        "--fail-on-status",
        default="degraded",
        choices=("never", "degraded", "inactive", "always"),
        help="Exit non-zero when telemetry status meets or exceeds this threshold.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    base_config = get_default_config()
    overrides = parse_override_pairs(args.override_pairs)
    config_path = Path(args.config).expanduser() if args.config else None
    try:
        config = load_toolkit_config(path=config_path, overrides=overrides, base=base_config)
    except ConfigurationError as exc:  # pragma: no cover - validated via CLI tests
        parser.error(str(exc))
        raise SystemExit(2) from exc

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
    instrumentation = telemetry.create_instrumentation(component="diagnostics")
    hook_registry = ExtensionHookRegistry(instrumentation)
    context = ExtensionContext(
        config=config,
        adapter_registry=AdapterRegistry(),
        telemetry=telemetry,
        instrumentation=instrumentation,
        logger=get_logger("extensions"),
        hook_registry=hook_registry,
    )

    try:
        extensions = load_extensions(config.extensions, context=context)
    except ExtensionLoadError as exc:
        telemetry.stop()
        parser.error(str(exc))
        raise SystemExit(2) from exc

    snapshot = collect_runtime_diagnostics(
        telemetry=telemetry,
        instrumentation=instrumentation,
        extensions=extensions,
        include_metrics=bool(args.include_metrics),
    )
    payload = snapshot.to_dict()

    try:
        _write_payload(payload, args.output)
    except OutputPathError as exc:
        telemetry.stop()
        parser.error(str(exc))
        raise SystemExit(2) from exc

    status = str(payload.get("telemetry", {}).get("status", "unknown")).lower()
    exit_code = _determine_exit_code(status, args.fail_on_status)
    telemetry.stop()
    return exit_code


def _write_payload(payload: dict[str, object], output: str | None) -> None:
    serialized = json.dumps(payload, indent=2)
    if output:
        destination = Path(output)
        atomic_write_text(destination, serialized)
    else:
        print(serialized)


def _determine_exit_code(status: str, threshold: str) -> int:
    normalized = threshold.lower()
    if normalized == "never":
        return 0
    if normalized == "always":
        return 1 if status != "ok" else 0
    if normalized == "inactive":
        return 1 if status not in {"ok", "inactive"} else 0
    # default degraded threshold treats inactive as healthy but flags degraded/unknown states
    return 1 if status not in {"ok", "inactive"} else 0


if __name__ == "__main__":
    sys.exit(main())
