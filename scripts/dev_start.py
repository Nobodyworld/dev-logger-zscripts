"""Run the full developer quality gate with optional skip flags."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

QUALITY_DIR = Path("artifacts/quality")
SUMMARY_FILE = QUALITY_DIR / "quality_gate.json"
COVERAGE_FILE = QUALITY_DIR / "coverage.json"
COVERAGE_THRESHOLD = float(os.environ.get("QUALITY_COVERAGE_MIN", "85"))

MYPY_TARGETS: tuple[str, ...] = (
    "zscripts/application",
    "zscripts/config.py",
    "zscripts/configuration.py",
    "zscripts/observability/logging.py",
    "zscripts/observability/metrics.py",
    "zscripts/observability/health.py",
    "zscripts/observability/instrumentation.py",
    "zscripts/extensions/scaffolding.py",
    "zscripts/schemas",
)


@dataclass
class Step:
    name: str
    command: Sequence[str]
    skip_env: str | None = None


STEPS: Sequence[Step] = (
    Step("lint", ("ruff", "check", "."), "ZSKIP_LINT"),
    Step("type", ("mypy", *MYPY_TARGETS), "ZSKIP_TYPE"),
    Step("security", ("bandit", "-q", "-r", "zscripts", "examples/sample_project"), "ZSKIP_SECURITY"),
    Step("tests", ("coverage", "run", "-m", "pytest"), "ZSKIP_TESTS"),
)


def main() -> None:
    QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict[str, object]] = {}
    coverage_path = shutil.which("coverage")
    if not coverage_path:
        summary["coverage"] = {"status": "failed", "reason": "coverage-missing"}
        _write_summary(summary, coverage=None)
        print("Missing required tool: coverage", file=sys.stderr)
        sys.exit(1)
    _run_command((coverage_path, "erase"))

    for step in STEPS:
        if step.skip_env and os.environ.get(step.skip_env):
            summary[step.name] = {"status": "skipped"}
            continue
        command = step.command
        executable = command[0]
        if shutil.which(executable) is None and not Path(executable).exists():
            summary[step.name] = {
                "status": "failed",
                "reason": f"{executable}-missing",
            }
            _write_summary(summary, coverage=None)
            print(f"Missing required tool: {executable}", file=sys.stderr)
            sys.exit(1)
        start = time.perf_counter()
        result = _run_command(command)
        duration = time.perf_counter() - start
        summary[step.name] = {
            "status": "passed" if result == 0 else "failed",
            "command": list(command),
            "duration_seconds": round(duration, 3),
        }
        if result != 0:
            _write_summary(summary, coverage=None)
            sys.exit(result)

    coverage_summary = _build_coverage_summary(summary, coverage_path)
    _write_summary(summary, coverage=coverage_summary)
    if summary.get("tests", {}).get("status") != "skipped" and coverage_summary["percent"] < COVERAGE_THRESHOLD:
        print(
            f"Coverage {coverage_summary['percent']:.1f}% below threshold {COVERAGE_THRESHOLD:.1f}%",
            file=sys.stderr,
        )
        sys.exit(1)


def _build_coverage_summary(summary: dict[str, dict[str, object]], coverage_path: str) -> dict[str, float]:
    if summary.get("tests", {}).get("status") != "passed":
        summary["coverage"] = {"status": "skipped"}
        return {"percent": 0.0}
    _run_command((coverage_path, "json", "-o", str(COVERAGE_FILE)))
    data = json.loads(COVERAGE_FILE.read_text(encoding="utf-8"))
    percent = float(data.get("totals", {}).get("percent_covered", 0.0))
    summary["coverage"] = {"status": "passed", "percent": percent}
    return {"percent": percent}


def _run_command(command: Sequence[str]) -> int:
    process = subprocess.run(command, check=False)
    return process.returncode


def _write_summary(summary: dict[str, dict[str, object]], *, coverage: dict[str, float] | None) -> None:
    payload = {
        "steps": summary,
        "coverage": coverage,
        "threshold": COVERAGE_THRESHOLD,
    }
    SUMMARY_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
